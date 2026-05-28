"""
Retrieval pipeline for the knowledge base.

Implements:
- QueryRewriter: Rewrites queries for better retrieval
- MultiRecallRetriever: Multi-path recall with RRF fusion
- ReRanker: Re-ranks results by relevance
- ContextAssembler: Assembles structured context for LLM injection
"""

import re
import logging
from typing import Dict, Any, List, Optional

from . import SearchResult, RetrievalContext, ALL_COLLECTIONS
from .store import VectorStore

logger = logging.getLogger(__name__)


class QueryRewriter:
    SYNONYM_MAP = {
        "oom": "out of memory",
        "bad_alloc": "out of memory",
        "segfault": "segmentation fault",
        "seg fault": "segmentation fault",
        "timeout": "execution timeout",
        "\u6ce8\u91ca": "annotation",
        "\u7ec4\u88c5": "assembly",
        "\u5185\u5b58\u4e0d\u8db3": "out of memory",
        "\u8d28\u63a7": "quality control QC",
        "\u629b\u5149": "polishing",
    }

    NOISE_PATTERNS = [
        re.compile(r"/tmp/[^\s]+"),
        re.compile(r"/home/[^\s]+"),
        re.compile(r"line \d+"),
        re.compile(r"File \".*?\""),
        re.compile(r"Traceback[\s\S]*?(?=\n[A-Z])"),
    ]

    def rewrite(self, query: str, context: Optional[RetrievalContext] = None) -> str:
        rewritten = query
        for abbr, full in self.SYNONYM_MAP.items():
            rewritten = rewritten.replace(abbr, full)
        for pattern in self.NOISE_PATTERNS:
            rewritten = pattern.sub("", rewritten)
        parts = [rewritten]
        if context:
            if context.current_tool:
                parts.append(context.current_tool)
            if context.kingdom:
                parts.append(f"{context.kingdom} mitochondrial")
            if context.error_type:
                parts.append(context.error_type)
        rewritten = " ".join(parts)
        rewritten = re.sub(r"\s+", " ", rewritten).strip()
        return rewritten


class MultiRecallRetriever:
    def __init__(self, store: VectorStore, query_rewriter: Optional[QueryRewriter] = None):
        self.store = store
        self.query_rewriter = query_rewriter or QueryRewriter()

    def retrieve(self,
                 query: str,
                 context: Optional[RetrievalContext] = None,
                 top_k: int = 5,
                 collections: Optional[List[str]] = None) -> List[SearchResult]:
        rewritten = self.query_rewriter.rewrite(query, context)
        target_collections = collections or ALL_COLLECTIONS
        all_results: List[SearchResult] = []
        for coll_name in target_collections:
            count = self.store.count(coll_name)
            if count == 0:
                continue
            filter_meta = self._build_filter(context)
            n = min(top_k * 3, max(top_k, 10))
            results = self.store.query(
                collection_name=coll_name,
                query_text=rewritten,
                n_results=n,
                filter_metadata=filter_meta,
            )
            all_results.extend(results)
        if not all_results:
            broad_results: List[SearchResult] = []
            for coll_name in target_collections:
                count = self.store.count(coll_name)
                if count == 0:
                    continue
                results = self.store.query(
                    collection_name=coll_name,
                    query_text=rewritten,
                    n_results=top_k,
                )
                broad_results.extend(results)
            all_results = broad_results
        fused = self._rrf_fusion(all_results, k=60)
        return fused[:top_k]

    def _build_filter(self, context: Optional[RetrievalContext]) -> Optional[Dict]:
        if not context:
            return None
        filters = {}
        if context.current_tool:
            filters["tool_name"] = context.current_tool
        if context.kingdom:
            filters["kingdom"] = context.kingdom
        return filters if filters else None

    def _rrf_fusion(self, results: List[SearchResult], k: int = 60) -> List[SearchResult]:
        if not results:
            return []
        score_map: Dict[str, float] = {}
        result_map: Dict[str, SearchResult] = {}
        for rank, r in enumerate(sorted(results, key=lambda x: x.score, reverse=True)):
            cid = r.chunk_id or r.content[:100]
            if cid not in score_map:
                score_map[cid] = 0.0
            score_map[cid] += 1.0 / (k + rank + 1)
            if cid not in result_map:
                result_map[cid] = r
        fused = [(cid, score) for cid, score in score_map.items()]
        fused.sort(key=lambda x: x[1], reverse=True)
        final = []
        for cid, score in fused:
            r = result_map[cid]
            final.append(SearchResult(
                content=r.content,
                score=score,
                metadata=r.metadata,
                chunk_id=r.chunk_id,
                collection=r.collection,
            ))
        return final


class ReRanker:
    def rerank(self,
               query: str,
               results: List[SearchResult],
               context: Optional[RetrievalContext] = None,
               top_k: int = 5) -> List[SearchResult]:
        if not results:
            return results
        scored = []
        for r in results:
            boost = 0.0
            if context and context.current_tool:
                tool_meta = r.metadata.get("tool_name", "").lower()
                if tool_meta == context.current_tool.lower():
                    boost += 0.3
            if context and context.kingdom:
                kingdom_meta = r.metadata.get("kingdom", "").lower()
                if kingdom_meta == context.kingdom.lower():
                    boost += 0.2
            if context and context.error_type:
                cat_meta = r.metadata.get("category", "").lower()
                if cat_meta == context.error_type.lower():
                    boost += 0.2
            scored.append((r, r.score + boost))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored[:top_k]]


class ContextAssembler:
    def __init__(self, max_context_tokens: int = 2000, relevance_threshold: float = 0.0):
        self.max_context_tokens = max_context_tokens
        self.relevance_threshold = relevance_threshold

    def assemble(self,
                 query: str,
                 results: List[SearchResult],
                 max_context_tokens: Optional[int] = None) -> str:
        max_tokens = max_context_tokens or self.max_context_tokens
        filtered = [r for r in results if r.score >= self.relevance_threshold]
        if not filtered:
            return ""
        seen_contents = set()
        unique = []
        for r in filtered:
            key = r.content[:200]
            if key not in seen_contents:
                seen_contents.add(key)
                unique.append(r)
        lines = ["## Reference Materials", ""]
        char_budget = max_tokens * 4
        used = 0
        for i, r in enumerate(unique, 1):
            source = r.metadata.get("source_file", r.collection)
            title = r.metadata.get("title", r.metadata.get("faq_id", f"ref_{i}"))
            entry = f"[{i}] {title} (source: {source}, relevance: {r.score:.2f})\n{r.content[:500]}"
            if used + len(entry) > char_budget:
                break
            lines.append(entry)
            lines.append("")
            used += len(entry)
        return "\n".join(lines)


def create_retriever(store: Optional[VectorStore] = None) -> tuple:
    if store is None:
        store = VectorStore()
    rewriter = QueryRewriter()
    retriever = MultiRecallRetriever(store, rewriter)
    reranker = ReRanker()
    assembler = ContextAssembler()
    return retriever, reranker, assembler
