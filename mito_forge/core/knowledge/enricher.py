"""
Metadata enrichment for knowledge base chunks.

Adds structured metadata tags (tool_name, category, kingdom, platform)
based on content analysis.
"""

import re
from typing import Dict, Any, List, Optional
from . import Chunk


TOOL_KEYWORDS: Dict[str, List[str]] = {
    "spades": ["spades", "spades.py"],
    "flye": ["flye"],
    "mitoz": ["mitoz"],
    "getorganelle": ["getorganelle"],
    "novoplasty": ["novoplasty"],
    "pmga": ["pmga"],
    "mitofy": ["mitofy"],
    "blast": ["blastx", "blastn", "blastp", "makeblastdb", "blast+"],
    "pilon": ["pilon"],
    "racon": ["racon"],
    "medaka": ["medaka"],
    "trnascan": ["trnascan", "tRNAscan-SE", "trnascan-se"],
    "fastqc": ["fastqc"],
    "minimap2": ["minimap2"],
    "bwa": ["bwa", "bwa-mem"],
}

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "assembly": ["assemble", "contig", "scaffold", "N50", "kmer", "k-mer", "de novo", "genome size"],
    "annotation": ["annotate", "gene", "CDS", "tRNA", "rRNA", "GFF", "genbank", "protein-coding"],
    "qc": ["quality", "fastqc", "trim", "filter", "coverage", "base quality"],
    "polish": ["polish", "consensus", "correction", "pilon", "racon", "medaka"],
    "error_handling": ["error", "fail", "oom", "timeout", "crash", "bad_alloc", "not found"],
}

KINGDOM_KEYWORDS: Dict[str, List[str]] = {
    "plant": ["plant", "mitochondria", "pmga", "mitofy", "arabidopsis", "seed plant"],
    "animal": ["animal", "metazoan", "mitoz", "vertebrate", "human", "drosophila"],
}

PLATFORM_KEYWORDS: Dict[str, List[str]] = {
    "illumina": ["illumina", "short-read", "paired-end", "fastq", "pilon"],
    "nanopore": ["nanopore", "ont", "long-read", "minion", "promethion", "flye", "medaka", "racon"],
    "pacbio": ["pacbio", "hifi", "ccs", "hifiasm"],
}


class MetadataEnricher:
    def __init__(self):
        self._tool_patterns = {
            name: re.compile("|".join(re.escape(kw) for kw in kws), re.IGNORECASE)
            for name, kws in TOOL_KEYWORDS.items()
        }
        self._cat_patterns = {
            name: re.compile("|".join(re.escape(kw) for kw in kws), re.IGNORECASE)
            for name, kws in CATEGORY_KEYWORDS.items()
        }
        self._kingdom_patterns = {
            name: re.compile("|".join(re.escape(kw) for kw in kws), re.IGNORECASE)
            for name, kws in KINGDOM_KEYWORDS.items()
        }
        self._platform_patterns = {
            name: re.compile("|".join(re.escape(kw) for kw in kws), re.IGNORECASE)
            for name, kws in PLATFORM_KEYWORDS.items()
        }

    def enrich(self, chunk: Chunk) -> Chunk:
        text = chunk.content
        meta = dict(chunk.metadata)
        existing_tool = meta.get("tool")
        if existing_tool:
            meta.setdefault("tool_name", existing_tool)
        else:
            detected_tools = self._detect(text, self._tool_patterns)
            if detected_tools:
                meta["tool_name"] = detected_tools[0]
                if len(detected_tools) > 1:
                    meta["tool_names"] = detected_tools
        detected_cats = self._detect(text, self._cat_patterns)
        if detected_cats:
            meta.setdefault("category", detected_cats[0])
        detected_kingdoms = self._detect(text, self._kingdom_patterns)
        if detected_kingdoms:
            meta.setdefault("kingdom", detected_kingdoms[0])
        detected_platforms = self._detect(text, self._platform_patterns)
        if detected_platforms:
            meta.setdefault("platform", detected_platforms[0])
        return Chunk(
            content=chunk.content,
            metadata=meta,
            chunk_id=chunk.chunk_id,
            parent_doc_id=chunk.parent_doc_id,
            position=chunk.position,
        )

    def _detect(self, text: str, patterns: Dict[str, re.Pattern]) -> List[str]:
        results = []
        for name, pattern in patterns.items():
            if pattern.search(text):
                results.append(name)
        return results
