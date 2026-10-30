"""Dense / hybrid retrieval with optional cross-encoder reranking. Every stage's score is kept on the hit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from rag_sentinel.retrieval.bm25 import BM25Index
from rag_sentinel.retrieval.embedder import Embedder
from rag_sentinel.retrieval.fusion import reciprocal_rank_fusion
from rag_sentinel.retrieval.reranker import Reranker
from rag_sentinel.retrieval.vector_store import VectorStore


@dataclass
class RetrievalConfig:
    mode: str = "hybrid"  # dense | bm25 | hybrid
    rerank: bool = True
    dense_k: int = 20
    bm25_k: int = 20
    rrf_k: int = 60
    rerank_candidates: int = 20
    final_k: int = 10


@dataclass
class Hit:
    chunk_id: str
    doc_id: str
    text: str
    page: int | None
    rank: int = 0
    dense_score: float | None = None
    dense_rank: int | None = None
    bm25_score: float | None = None
    bm25_rank: int | None = None
    fused_score: float | None = None
    rerank_score: float | None = None
    relevance: float = 0.0  # stage-appropriate relevance in [0, 1] used downstream
    extra: dict = field(default_factory=dict)


ChunkLookup = Callable[[list[str]], dict[str, tuple[str, str, int | None]]]  # id -> (doc_id, text, page)


class Retriever:
    def __init__(
        self,
        embedder: Embedder,
        vectors: VectorStore,
        bm25: Callable[[], BM25Index],
        lookup: ChunkLookup,
        reranker: Reranker | None = None,
        doc_titles: Callable[[], dict[str, str]] | None = None,
    ):
        self.embedder = embedder
        self.vectors = vectors
        self.bm25 = bm25
        self.lookup = lookup
        self.reranker = reranker
        self.doc_titles = doc_titles

    def retrieve(self, query: str, cfg: RetrievalConfig) -> list[Hit]:
        dense: list[tuple[str, float]] = []
        sparse: list[tuple[str, float]] = []
        if cfg.mode in ("dense", "hybrid"):
            dense = self.vectors.search(self.embedder.embed_query(query), cfg.dense_k)
        if cfg.mode in ("bm25", "hybrid"):
            sparse = self.bm25().search(query, cfg.bm25_k)

        if cfg.mode == "dense":
            order = [(c, s) for c, s in dense]
        elif cfg.mode == "bm25":
            order = [(c, s) for c, s in sparse]
        else:
            order = reciprocal_rank_fusion([[c for c, _ in dense], [c for c, _ in sparse]], k=cfg.rrf_k)

        info = self.lookup([c for c, _ in order])
        dense_map = {c: (s, r) for r, (c, s) in enumerate(dense, 1)}
        sparse_map = {c: (s, r) for r, (c, s) in enumerate(sparse, 1)}
        hits: list[Hit] = []
        for cid, score in order:
            if cid not in info:  # stale vector for a deleted chunk
                continue
            doc_id, text, page = info[cid]
            h = Hit(chunk_id=cid, doc_id=doc_id, text=text, page=page)
            if cid in dense_map:
                h.dense_score, h.dense_rank = dense_map[cid]
            if cid in sparse_map:
                h.bm25_score, h.bm25_rank = sparse_map[cid]
            if cfg.mode == "hybrid":
                h.fused_score = score
            hits.append(h)

        if cfg.rerank and self.reranker is not None and hits:
            cands = hits[: cfg.rerank_candidates]
            titles = self.doc_titles() if self.doc_titles else {}
            passages = [f"{titles.get(h.doc_id, '')}\n{h.text}".strip() for h in cands]
            scores = self.reranker.score(query, passages)
            for h, s in zip(cands, scores, strict=True):
                h.rerank_score = float(s)
                h.relevance = float(s)
            hits = sorted(cands, key=lambda h: -(h.rerank_score or 0.0))
        else:
            top = max((self._raw(h, cfg) for h in hits), default=0.0) or 1.0
            for h in hits:
                h.relevance = self._raw(h, cfg) / top
        hits = hits[: cfg.final_k]
        for i, h in enumerate(hits, 1):
            h.rank = i
        return hits

    @staticmethod
    def _raw(h: Hit, cfg: RetrievalConfig) -> float:
        if cfg.mode == "dense":
            return max(h.dense_score or 0.0, 0.0)
        if cfg.mode == "bm25":
            return h.bm25_score or 0.0
        return h.fused_score or 0.0
