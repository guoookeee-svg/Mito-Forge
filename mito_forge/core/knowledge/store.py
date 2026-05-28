"""
Vector store and embedding functions for the knowledge base.

Supports progressive enhancement:
- Level 0: BM25 keyword search (zero dependencies)
- Level 1: sentence-transformers/all-MiniLM-L6-v2 (local, 80MB)
- Level 2: Ollama embedding API (nomic-embed-text)
"""

import os
import math
import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from . import (
    SearchResult,
    COLLECTION_TOOL_MANUALS,
    COLLECTION_DOMAIN_KNOWLEDGE,
    COLLECTION_RUN_EXPERIENCE,
    ALL_COLLECTIONS,
)

logger = logging.getLogger(__name__)


class SentenceTransformerEmbedding:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None

    def _ensure_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        self._ensure_model()
        return self._model.encode(texts, show_progress_bar=False, convert_to_numpy=True).tolist()

    def embed_query(self, text: str) -> List[float]:
        self._ensure_model()
        return self._model.encode([text], show_progress_bar=False, convert_to_numpy=True)[0].tolist()


class BM25Embedding:
    def __init__(self, n_features: int = 2048):
        self.n_features = n_features
        self._corpus_tokens: List[List[str]] = []
        self._corpus_texts: List[str] = []
        self._idf: Dict[str, float] = {}
        self._avg_dl: float = 0.0
        self._k1 = 1.5
        self._b = 0.75

    def _tokenize(self, text: str) -> List[str]:
        tokens = text.lower().split()
        refined = []
        for t in tokens:
            refined.append(t)
            for i in range(len(t)):
                for n in range(2, 5):
                    if i + n <= len(t):
                        refined.append(t[i:i + n])
        return refined

    def fit(self, texts: List[str]):
        self._corpus_texts = texts
        self._corpus_tokens = [self._tokenize(t) for t in texts]
        n_docs = len(texts)
        self._avg_dl = sum(len(t) for t in self._corpus_tokens) / max(n_docs, 1)
        df: Dict[str, int] = {}
        for tokens in self._corpus_tokens:
            for token in set(tokens):
                df[token] = df.get(token, 0) + 1
        self._idf = {
            token: math.log((n_docs - freq + 0.5) / (freq + 0.5) + 1.0)
            for token, freq in df.items()
        }

    def _bm25_score(self, query_tokens: List[str], doc_idx: int) -> float:
        doc_tokens = self._corpus_tokens[doc_idx]
        dl = len(doc_tokens)
        tf_map: Dict[str, int] = {}
        for t in doc_tokens:
            tf_map[t] = tf_map.get(t, 0) + 1
        score = 0.0
        for qt in query_tokens:
            tf = tf_map.get(qt, 0)
            idf = self._idf.get(qt, 0.0)
            numerator = tf * (self._k1 + 1)
            denominator = tf + self._k1 * (1 - self._b + self._b * dl / max(self._avg_dl, 1e-9))
            score += idf * numerator / max(denominator, 1e-9)
        return score

    def search(self, query: str, top_k: int = 5) -> List[tuple]:
        query_tokens = self._tokenize(query)
        scores = []
        for i in range(len(self._corpus_texts)):
            s = self._bm25_score(query_tokens, i)
            scores.append((i, s))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_vectorize(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._hash_vectorize(text)

    def _hash_vectorize(self, text: str) -> List[float]:
        vec = [0.0] * self.n_features
        if not text:
            return vec
        t = text.replace("\n", " ").replace("\r", " ")
        n = len(t)
        for ngram_len in range(2, 5):
            if ngram_len > n:
                continue
            for i in range(n - ngram_len + 1):
                g = t[i:i + ngram_len]
                h = hashlib.sha1(g.encode("utf-8")).digest()
                idx = int.from_bytes(h[:8], "big") % self.n_features
                vec[idx] += 1.0
        s = math.sqrt(sum(v * v for v in vec))
        if s > 0:
            vec = [v / s for v in vec]
        return vec


class HashEmbeddingFunction:
    def __init__(self, n_features: int = 2048):
        self.n_features = n_features
        self._bm25 = BM25Embedding(n_features)

    def name(self):
        return "local-hash-bm25"

    def is_legacy(self):
        return True

    def __call__(self, input):
        return self._bm25.embed_documents(input)

    def embed_documents(self, input):
        return self._bm25.embed_documents(input)

    def embed_query(self, input):
        if isinstance(input, str):
            return self._bm25.embed_query(input)
        return self._bm25.embed_documents(input)


def detect_embedding_level() -> str:
    try:
        import requests
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        resp = requests.get(f"{ollama_host}/api/tags", timeout=2)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            for m in models:
                if "embed" in m.get("name", "").lower():
                    return "ollama"
    except Exception:
        pass
    try:
        from sentence_transformers import SentenceTransformer
        return "sentence_transformer"
    except ImportError:
        pass
    return "hash"


def create_embedding_function(level: str = "auto"):
    if level == "auto":
        level = detect_embedding_level()
    if level == "sentence_transformer":
        return SentenceTransformerEmbedding()
    elif level == "ollama":
        return SentenceTransformerEmbedding()
    else:
        return HashEmbeddingFunction()


class VectorStore:
    def __init__(self, persist_dir: Optional[Path] = None, embedding_level: str = "auto"):
        if persist_dir is None:
            base = os.getenv("MITO_CHROMA_DIR")
            if base:
                persist_dir = Path(base)
            else:
                persist_dir = Path.home() / ".mito-forge" / "chroma"
        self.persist_dir = persist_dir
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_level = embedding_level
        self._emb_fn = None
        self._client = None
        self._collections: Dict[str, Any] = {}

    def _get_client(self):
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        return self._client

    def _get_emb_fn(self):
        if self._emb_fn is None:
            self._emb_fn = create_embedding_function(self.embedding_level)
        return self._emb_fn

    def _get_collection(self, name: str):
        if name not in self._collections:
            client = self._get_client()
            emb = self._get_emb_fn()
            self._collections[name] = client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=emb,
            )
        return self._collections[name]

    def add_chunks(self, collection_name: str, chunks: list) -> int:
        collection = self._get_collection(collection_name)
        if not chunks:
            return 0
        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = []
        for c in chunks:
            meta = {}
            for k, v in c.metadata.items():
                if isinstance(v, (str, int, float, bool)):
                    meta[k] = v
                elif isinstance(v, list):
                    meta[k] = ",".join(str(x) for x in v)
                else:
                    meta[k] = str(v)
            metadatas.append(meta)
        existing_ids = set()
        try:
            existing = collection.get(ids=ids)
            existing_ids = set(existing.get("ids", []))
        except Exception:
            pass
        new_ids, new_docs, new_metas = [], [], []
        for i, cid in enumerate(ids):
            if cid not in existing_ids:
                new_ids.append(cid)
                new_docs.append(documents[i])
                new_metas.append(metadatas[i])
        if not new_ids:
            return 0
        batch_size = 100
        total = 0
        for start in range(0, len(new_ids), batch_size):
            end = start + batch_size
            collection.add(
                ids=new_ids[start:end],
                documents=new_docs[start:end],
                metadatas=new_metas[start:end],
            )
            total += end - start
        return total

    def query(self,
              collection_name: str,
              query_text: str,
              n_results: int = 5,
              filter_metadata: Optional[Dict] = None) -> List[SearchResult]:
        collection = self._get_collection(collection_name)
        kwargs = {
            "query_texts": [query_text],
            "n_results": n_results,
        }
        if filter_metadata:
            where_clauses = []
            for k, v in filter_metadata.items():
                where_clauses.append({k: v})
            if len(where_clauses) == 1:
                kwargs["where"] = where_clauses[0]
            elif where_clauses:
                kwargs["where"] = {"$and": where_clauses}
        try:
            res = collection.query(**kwargs)
        except Exception as e:
            logger.warning(f"Query failed on {collection_name}: {e}")
            return []
        results: List[SearchResult] = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        ids = res.get("ids", [[]])[0]
        for i, doc in enumerate(docs):
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else 1.0
            cid = ids[i] if i < len(ids) else ""
            results.append(SearchResult(
                content=doc or "",
                score=1.0 - dist,
                metadata=meta,
                chunk_id=cid,
                collection=collection_name,
            ))
        return results

    def count(self, collection_name: str) -> int:
        try:
            collection = self._get_collection(collection_name)
            return collection.count()
        except Exception:
            return 0

    def delete_collection(self, collection_name: str):
        try:
            client = self._get_client()
            client.delete_collection(collection_name)
            self._collections.pop(collection_name, None)
        except Exception:
            pass

    def rebuild_collection(self, collection_name: str):
        self.delete_collection(collection_name)
