"""
Knowledge base management CLI command.

Provides commands for:
- Indexing knowledge sources into the vector store
- Querying the knowledge base
- Evaluating retrieval quality
- Showing knowledge base statistics
"""

import click
from pathlib import Path


@click.group("knowledge")
def knowledge_group():
    pass


@knowledge_group.command("index")
@click.option("--sources-dir", type=click.Path(), default=None, help="Custom sources directory")
@click.option("--embedding-level", type=click.Choice(["auto", "hash", "sentence_transformer", "ollama"]), default="auto")
@click.option("--rebuild", is_flag=True, default=False, help="Rebuild all collections from scratch")
def index_cmd(sources_dir, embedding_level, rebuild):
    from mito_forge.core.knowledge.indexer import run_indexing, KnowledgeIndexer
    from mito_forge.core.knowledge.store import VectorStore
    from mito_forge.core.knowledge import ALL_COLLECTIONS

    if rebuild:
        store = VectorStore(embedding_level=embedding_level)
        for coll in ALL_COLLECTIONS:
            click.echo(f"  Deleting collection: {coll}")
            store.rebuild_collection(coll)

    src = Path(sources_dir) if sources_dir else None
    counts = run_indexing(src, embedding_level)
    total = sum(counts.values())
    click.echo(f"Indexing complete. Total chunks indexed: {total}")
    for coll, n in counts.items():
        click.echo(f"  {coll}: {n} chunks")


@knowledge_group.command("stats")
@click.option("--embedding-level", type=click.Choice(["auto", "hash", "sentence_transformer", "ollama"]), default="auto")
def stats_cmd(embedding_level):
    from mito_forge.core.knowledge.indexer import KnowledgeIndexer
    from mito_forge.core.knowledge.store import VectorStore

    store = VectorStore(embedding_level=embedding_level)
    indexer = KnowledgeIndexer(store)
    stats = indexer.get_stats()
    click.echo("Knowledge Base Statistics:")
    for key, val in stats.items():
        if isinstance(val, dict):
            click.echo(f"  {key}:")
            for k2, v2 in val.items():
                click.echo(f"    {k2}: {v2}")
        else:
            click.echo(f"  {key}: {val}")


@knowledge_group.command("query")
@click.argument("query_text")
@click.option("--top-k", default=5, help="Number of results")
@click.option("--collection", default=None, help="Specific collection to search")
@click.option("--embedding-level", type=click.Choice(["auto", "hash", "sentence_transformer", "ollama"]), default="auto")
def query_cmd(query_text, top_k, collection, embedding_level):
    from mito_forge.core.knowledge.store import VectorStore
    from mito_forge.core.knowledge.retriever import create_retriever
    from mito_forge.core.knowledge import ALL_COLLECTIONS

    store = VectorStore(embedding_level=embedding_level)
    retriever, reranker, assembler = create_retriever(store)
    collections = [collection] if collection else ALL_COLLECTIONS
    from mito_forge.core.knowledge import RetrievalContext
    context = RetrievalContext(agent_name="cli")
    results = retriever.retrieve(query_text, context, top_k=top_k, collections=collections)
    results = reranker.rerank(query_text, results, context, top_k=top_k)
    if not results:
        click.echo("No results found.")
        return
    for i, r in enumerate(results, 1):
        click.echo(f"\n[{i}] Score: {r.score:.4f} | Collection: {r.collection}")
        click.echo(f"    Source: {r.metadata.get('source_file', 'unknown')}")
        click.echo(f"    Content: {r.content[:200]}...")


@knowledge_group.command("evaluate")
@click.option("--embedding-level", type=click.Choice(["auto", "hash", "sentence_transformer", "ollama"]), default="auto")
def evaluate_cmd(embedding_level):
    from mito_forge.core.knowledge.store import VectorStore
    from mito_forge.core.knowledge.evaluator import run_evaluation

    store = VectorStore(embedding_level=embedding_level)
    results = run_evaluation(store)
    click.echo(f"Evaluation Results ({results['num_queries']} queries):")
    click.echo(f"  Mean Hit Rate: {results['mean_hit_rate']:.3f}")
    click.echo(f"  Mean MRR: {results['mean_mrr']:.3f}")
    click.echo(f"  Mean Latency: {results['mean_latency_ms']:.1f}ms")
    click.echo("\nPer-query results:")
    for qr in results.get("per_query", []):
        hit_str = "HIT" if qr["hit_rate"] > 0 else "MISS"
        click.echo(f"  [{hit_str}] MRR={qr['mrr']:.3f} | {qr['query'][:60]}")
