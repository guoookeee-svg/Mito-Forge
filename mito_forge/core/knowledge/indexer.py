"""
Knowledge indexer - builds vector indices from source documents.

Orchestrates the full ingestion pipeline:
  Source → Loader → Chunker → Enricher → VectorStore
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import (
    Document, Chunk,
    COLLECTION_TOOL_MANUALS,
    COLLECTION_DOMAIN_KNOWLEDGE,
    COLLECTION_RUN_EXPERIENCE,
    ALL_COLLECTIONS,
)
from .loader import auto_load
from .chunker import get_chunker
from .enricher import MetadataEnricher
from .store import VectorStore

SOURCES_DIR = Path(__file__).parent / "sources"


class KnowledgeIndexer:
    def __init__(self, store: Optional[VectorStore] = None):
        self.store = store or VectorStore()
        self.enricher = MetadataEnricher()

    def index_sources(self, sources_dir: Optional[Path] = None) -> Dict[str, int]:
        sources_dir = sources_dir or SOURCES_DIR
        counts: Dict[str, int] = {}
        tool_manuals_dir = sources_dir / "tool_manuals"
        if tool_manuals_dir.exists():
            counts[COLLECTION_TOOL_MANUALS] = self._index_directory(
                tool_manuals_dir, COLLECTION_TOOL_MANUALS
            )
        domain_dir = sources_dir / "domain_knowledge"
        if domain_dir.exists():
            counts[COLLECTION_DOMAIN_KNOWLEDGE] = self._index_directory(
                domain_dir, COLLECTION_DOMAIN_KNOWLEDGE
            )
        faq_file = sources_dir / "error_faq.yaml"
        if faq_file.exists():
            n = self._index_file(faq_file, COLLECTION_DOMAIN_KNOWLEDGE)
            counts[COLLECTION_DOMAIN_KNOWLEDGE] = counts.get(COLLECTION_DOMAIN_KNOWLEDGE, 0) + n
        return counts

    def _index_directory(self, directory: Path, collection: str) -> int:
        total = 0
        for fp in sorted(directory.rglob("*")):
            if fp.is_file() and fp.suffix.lower() in (".md", ".markdown", ".yaml", ".yml", ".json"):
                n = self._index_file(fp, collection)
                total += n
        return total

    def _index_file(self, file_path: Path, collection: str) -> int:
        try:
            docs = auto_load(file_path)
        except Exception as e:
            return 0
        all_chunks: List[Chunk] = []
        for doc in docs:
            format_hint = doc.metadata.get("format", "markdown")
            chunker = get_chunker(format_hint)
            chunks = chunker.chunk(doc)
            for chunk in chunks:
                enriched = self.enricher.enrich(chunk)
                all_chunks.append(enriched)
        if not all_chunks:
            return 0
        try:
            n = self.store.add_chunks(collection, all_chunks)
            return n
        except Exception:
            return 0

    def index_experience(self, experience_dir: Optional[Path] = None) -> int:
        if experience_dir is None:
            experience_dir = Path.home() / ".mito-forge" / "experience"
        if not experience_dir.exists():
            return 0
        total = 0
        for fp in sorted(experience_dir.rglob("*.json")):
            try:
                n = self._index_file(fp, COLLECTION_RUN_EXPERIENCE)
                total += n
            except Exception:
                continue
        return total

    def get_stats(self) -> Dict[str, Any]:
        stats = {}
        for coll in ALL_COLLECTIONS:
            stats[coll] = {
                "count": self.store.count(coll),
            }
        stats["embedding_level"] = self.store.embedding_level
        stats["persist_dir"] = str(self.store.persist_dir)
        return stats


def write_experience(event: Dict[str, Any], experience_dir: Optional[Path] = None):
    if experience_dir is None:
        experience_dir = Path.home() / ".mito-forge" / "experience"
    experience_dir.mkdir(parents=True, exist_ok=True)
    agent_name = event.get("agent_name", "unknown")
    ts = int(time.time())
    filename = f"{agent_name}_{ts}.json"
    fp = experience_dir / filename
    record = {
        "timestamp": ts,
        **event,
    }
    fp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def run_indexing(sources_dir: Optional[Path] = None, embedding_level: str = "auto") -> Dict[str, int]:
    store = VectorStore(embedding_level=embedding_level)
    indexer = KnowledgeIndexer(store)
    counts = indexer.index_sources(sources_dir)
    exp_count = indexer.index_experience()
    if exp_count > 0:
        counts[COLLECTION_RUN_EXPERIENCE] = exp_count
    return counts
