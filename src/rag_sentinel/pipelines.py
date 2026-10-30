"""Experiment configurations: baselines B0-B4 and ablations. One code path, components toggled by flags."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class Pipeline:
    name: str
    description: str
    retrieval_mode: str = "hybrid"  # dense | bm25 | hybrid
    rerank: bool = True
    temporal_ranking: bool = False  # version/authority-aware evidence ranking
    ranking_preset: str = "default"
    metadata_in_prompt: bool = False  # show version/effective/approval/status to the generator
    conflict_detection: bool = False
    gating: bool = False  # explicit evidence rules decide VERIFIED / NEEDS_REVIEW / INSUFFICIENT_EVIDENCE
    answer_check: bool = False  # LLM check that the draft answers the question and is backed (R9, R10)

    def to_dict(self) -> dict:
        return asdict(self)


B0 = Pipeline("B0", "Basic vector RAG (dense retrieval only)", retrieval_mode="dense", rerank=False)
B1 = Pipeline("B1", "Hybrid RAG (dense + BM25, RRF)", rerank=False)
B2 = Pipeline("B2", "Hybrid RAG + cross-encoder reranking")
B3 = Pipeline("B3", "B2 + temporal & authority-aware evidence ranking", temporal_ranking=True, metadata_in_prompt=True)
B4 = Pipeline("B4", "B3 + contradiction detection + evidence gating + answer check (RAG Sentinel)",
              temporal_ranking=True, metadata_in_prompt=True, conflict_detection=True, gating=True,
              answer_check=True)  # fmt: skip

ABLATIONS = [
    replace(B4, name="B4-no-rerank", description="B4 without reranking (no calibrated relevance gate)", rerank=False),
    replace(B4, name="B4-relevance-ranking", description="B4 with evidence ranked by relevance only",
            ranking_preset="relevance_only"),
    replace(B4, name="B4-newest-wins", description="B4 with naive newest-document-wins ranking",
            ranking_preset="newest_wins"),
    replace(B4, name="B4-no-conflicts", description="B4 without contradiction detection", conflict_detection=False),
    replace(B4, name="B4-no-gating", description="B4 without the verification gate", gating=False),
    replace(B4, name="B4-no-answer-check", description="B4 without the answer check (R9, R10)", answer_check=False),
]  # fmt: skip

PIPELINES: dict[str, Pipeline] = {p.name: p for p in [B0, B1, B2, B3, B4, *ABLATIONS]}
BASELINES = ["B0", "B1", "B2", "B3", "B4"]
