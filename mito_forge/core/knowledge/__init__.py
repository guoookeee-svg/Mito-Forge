"""
Knowledge base module for Mito-Forge RAG system.

Provides document loading, chunking, metadata enrichment, vector indexing,
and retrieval pipeline for domain-specific knowledge augmentation.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import hashlib


@dataclass
class Document:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    doc_id: str = ""

    def __post_init__(self):
        if not self.doc_id:
            raw = f"{self.source}:{self.content[:200]}"
            self.doc_id = hashlib.md5(raw.encode()).hexdigest()[:12]


@dataclass
class Chunk:
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: str = ""
    parent_doc_id: str = ""
    position: int = 0

    def __post_init__(self):
        if not self.chunk_id:
            raw = f"{self.parent_doc_id}:{self.position}:{self.content[:200]}"
            self.chunk_id = hashlib.md5(raw.encode()).hexdigest()[:12]


@dataclass
class SearchResult:
    content: str
    score: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    chunk_id: str = ""
    collection: str = ""


@dataclass
class RetrievalContext:
    agent_name: str = ""
    current_tool: Optional[str] = None
    kingdom: Optional[str] = None
    platform: Optional[str] = None
    error_type: Optional[str] = None
    task_description: Optional[str] = None


COLLECTION_TOOL_MANUALS = "tool_manuals"
COLLECTION_DOMAIN_KNOWLEDGE = "domain_knowledge"
COLLECTION_RUN_EXPERIENCE = "run_experience"

ALL_COLLECTIONS = [
    COLLECTION_TOOL_MANUALS,
    COLLECTION_DOMAIN_KNOWLEDGE,
    COLLECTION_RUN_EXPERIENCE,
]
