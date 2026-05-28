"""
Document chunking strategies for the knowledge base.

Supports heading-based chunking (for Markdown), fixed-size chunking,
and pass-through (for already-atomic documents like FAQ entries).
"""

import re
from typing import List, Optional
from . import Document, Chunk


class HeadingBasedChunker:
    def __init__(self, max_chunk_size: int = 1500, min_chunk_size: int = 50):
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size

    def chunk(self, doc: Document) -> List[Chunk]:
        text = doc.content
        if len(text) <= self.max_chunk_size:
            return [Chunk(
                content=text,
                metadata={**doc.metadata, "chunk_type": "heading"},
                parent_doc_id=doc.doc_id,
                position=0,
            )]
        sections = re.split(r"\n(?=#{1,6}\s)", text)
        chunks: List[Chunk] = []
        pos = 0
        current = ""
        for section in sections:
            section = section.strip()
            if not section:
                continue
            if len(current) + len(section) + 1 <= self.max_chunk_size:
                current = current + "\n" + section if current else section
            else:
                if current and len(current) >= self.min_chunk_size:
                    chunks.append(Chunk(
                        content=current,
                        metadata={**doc.metadata, "chunk_type": "heading"},
                        parent_doc_id=doc.doc_id,
                        position=pos,
                    ))
                    pos += 1
                current = section
        if current and len(current) >= self.min_chunk_size:
            chunks.append(Chunk(
                content=current,
                metadata={**doc.metadata, "chunk_type": "heading"},
                parent_doc_id=doc.doc_id,
                position=pos,
            ))
        elif current and chunks:
            last = chunks[-1]
            chunks[-1] = Chunk(
                content=last.content + "\n" + current,
                metadata=last.metadata,
                chunk_id=last.chunk_id,
                parent_doc_id=last.parent_doc_id,
                position=last.position,
            )
        return chunks if chunks else [Chunk(
            content=text[:self.max_chunk_size],
            metadata={**doc.metadata, "chunk_type": "heading_truncated"},
            parent_doc_id=doc.doc_id,
            position=0,
        )]


class FixedSizeChunker:
    def __init__(self, chunk_size: int = 512, overlap: int = 64, min_chunk_size: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size

    def chunk(self, doc: Document) -> List[Chunk]:
        text = doc.content
        if len(text) <= self.chunk_size:
            return [Chunk(
                content=text,
                metadata={**doc.metadata, "chunk_type": "fixed"},
                parent_doc_id=doc.doc_id,
                position=0,
            )]
        chunks: List[Chunk] = []
        pos = 0
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            piece = text[start:end]
            if len(piece) >= self.min_chunk_size:
                chunks.append(Chunk(
                    content=piece,
                    metadata={**doc.metadata, "chunk_type": "fixed", "offset": start},
                    parent_doc_id=doc.doc_id,
                    position=pos,
                ))
                pos += 1
            start = end - self.overlap
        return chunks


class PassThroughChunker:
    def chunk(self, doc: Document) -> List[Chunk]:
        return [Chunk(
            content=doc.content,
            metadata={**doc.metadata, "chunk_type": "passthrough"},
            parent_doc_id=doc.doc_id,
            position=0,
        )]


def get_chunker(format_hint: str = "markdown") -> object:
    if format_hint in ("markdown", "md"):
        return HeadingBasedChunker()
    elif format_hint in ("yaml_faq", "yaml", "yml"):
        return PassThroughChunker()
    elif format_hint in ("json", "json_experience"):
        return PassThroughChunker()
    else:
        return FixedSizeChunker()
