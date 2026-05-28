"""
Retrieval quality evaluation for the knowledge base.

Evaluates retrieval performance using Hit Rate, MRR, and NDCG metrics.
"""

import logging
from typing import Dict, Any, List, Optional

from . import SearchResult, RetrievalContext, COLLECTION_DOMAIN_KNOWLEDGE
from .store import VectorStore
from .retriever import MultiRecallRetriever, QueryRewriter, ReRanker

logger = logging.getLogger(__name__)

EVALUATION_QUERIES = [
    {
        "query": "SPAdes assembly out of memory error",
        "relevant_ids": ["faq_spades_oom"],
        "relevant_keywords": ["spades", "out of memory", "oom", "bad_alloc"],
        "context": {"tool": "spades", "category": "assembly"},
    },
    {
        "query": "Flye repeat resolution failed",
        "relevant_ids": ["faq_flye_repeat_resolution"],
        "relevant_keywords": ["flye", "repeat", "resolution"],
        "context": {"tool": "flye", "category": "assembly"},
    },
    {
        "query": "plant mitochondrial annotation low gene count",
        "relevant_ids": ["faq_plant_annotation_low_gene_count"],
        "relevant_keywords": ["plant", "annotation", "gene", "pmga", "mitofy"],
        "context": {"tool": "pmga", "category": "annotation", "kingdom": "plant"},
    },
    {
        "query": "Pilon Java heap space error",
        "relevant_ids": ["faq_pilon_java_heap"],
        "relevant_keywords": ["pilon", "java", "heap", "OutOfMemoryError"],
        "context": {"tool": "pilon", "category": "polish"},
    },
    {
        "query": "Racon no alignments zero overlaps",
        "relevant_ids": ["faq_racon_no_alignments"],
        "relevant_keywords": ["racon", "no alignments", "zero overlaps"],
        "context": {"tool": "racon", "category": "polish"},
    },
    {
        "query": "SPAdes K-mer parameters for mitochondrial assembly",
        "relevant_ids": [],
        "relevant_keywords": ["spades", "kmer", "k-mer", "parameters"],
        "context": {"tool": "spades", "category": "assembly"},
    },
    {
        "query": "GetOrganelle no seed sequences found",
        "relevant_ids": ["faq_getorganelle_no_seed"],
        "relevant_keywords": ["getorganelle", "seed", "baiting"],
        "context": {"tool": "getorganelle", "category": "assembly"},
    },
    {
        "query": "PMGA Singularity not found",
        "relevant_ids": ["faq_pmga_singularity_not_found"],
        "relevant_keywords": ["pmga", "singularity", "container"],
        "context": {"tool": "pmga", "category": "annotation"},
    },
]


class RetrievalEvaluator:
    def __init__(self, store: Optional[VectorStore] = None):
        self.store = store or VectorStore()
        self.rewriter = QueryRewriter()
        self.retriever = MultiRecallRetriever(self.store, self.rewriter)
        self.reranker = ReRanker()

    def evaluate(self, queries: Optional[List[Dict]] = None, top_k: int = 5) -> Dict[str, Any]:
        queries = queries or EVALUATION_QUERIES
        results = []
        for q in queries:
            result = self._evaluate_single(q, top_k)
            results.append(result)
        hit_rates = [r["hit_rate"] for r in results]
        mrrs = [r["mrr"] for r in results]
        latencies = [r["latency_ms"] for r in results]
        return {
            "num_queries": len(results),
            "mean_hit_rate": sum(hit_rates) / len(hit_rates) if hit_rates else 0.0,
            "mean_mrr": sum(mrrs) / len(mrrs) if mrrs else 0.0,
            "mean_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
            "per_query": results,
        }

    def _evaluate_single(self, query_spec: Dict, top_k: int) -> Dict[str, Any]:
        import time
        query = query_spec["query"]
        relevant_keywords = query_spec.get("relevant_keywords", [])
        relevant_ids = query_spec.get("relevant_ids", [])
        ctx_spec = query_spec.get("context", {})
        context = RetrievalContext(
            agent_name="evaluator",
            current_tool=ctx_spec.get("tool"),
            kingdom=ctx_spec.get("kingdom"),
            error_type=ctx_spec.get("category"),
        )
        start = time.time()
        results = self.retriever.retrieve(query, context, top_k=top_k)
        results = self.reranker.rerank(query, results, context, top_k=top_k)
        latency_ms = (time.time() - start) * 1000
        hit = 0
        first_relevant_rank = 0
        for rank, r in enumerate(results, 1):
            is_relevant = self._is_relevant(r, relevant_keywords, relevant_ids)
            if is_relevant:
                hit = 1
                if first_relevant_rank == 0:
                    first_relevant_rank = rank
                break
        mrr = 1.0 / first_relevant_rank if first_relevant_rank > 0 else 0.0
        return {
            "query": query,
            "hit_rate": hit,
            "mrr": mrr,
            "num_results": len(results),
            "latency_ms": latency_ms,
        }

    def _is_relevant(self, result: SearchResult, keywords: List[str], ids: List[str]) -> bool:
        content_lower = result.content.lower()
        meta_id = result.metadata.get("faq_id", "")
        for kid in ids:
            if kid in meta_id or kid in result.chunk_id:
                return True
        matched = sum(1 for kw in keywords if kw.lower() in content_lower)
        return matched >= len(keywords) * 0.5 if keywords else False


def run_evaluation(store: Optional[VectorStore] = None) -> Dict[str, Any]:
    evaluator = RetrievalEvaluator(store)
    return evaluator.evaluate()
