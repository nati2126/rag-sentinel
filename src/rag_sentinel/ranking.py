"""Temporal + authority-aware evidence ranking.

Not "newest wins": a newer *draft* or a not-yet-effective revision does not displace the approved version
that is in force at the as-of date, and a low-authority FAQ does not beat an official policy just by being
recent. Every factor is reported so the choice can be explained.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from rag_sentinel.config import RankingWeights
from rag_sentinel.db import Document
from rag_sentinel.ingest.versioning import Lineage, valid_from

APPROVAL_SCORE = {"approved": 1.0, "pending": 0.5, "unknown": 0.4, "draft": 0.2, "withdrawn": 0.0}
UNKNOWN_AUTHORITY = 0.4

PRESETS: dict[str, RankingWeights] = {
    "default": RankingWeights(),
    # Ablation: the naive strategy RAG Sentinel argues against.
    "newest_wins": RankingWeights(
        relevance=0.5, authority=0.0, approval=0.0, recency=0.5,
        superseded_factor=1.0, not_yet_effective_factor=1.0, withdrawn_factor=1.0, unapproved_factor=1.0,
    ),
    "relevance_only": RankingWeights(
        relevance=1.0, authority=0.0, approval=0.0, recency=0.0,
        superseded_factor=1.0, not_yet_effective_factor=1.0, withdrawn_factor=1.0, unapproved_factor=1.0,
    ),
}  # fmt: skip


@dataclass
class DocStanding:
    doc_id: str
    in_force: bool
    status: str  # in_force | superseded | not_yet_effective | withdrawn | unapproved
    authority: float
    approval: float
    factor: float
    superseded_by: str | None = None
    reasons: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Source standing independent of the question (used for conflict resolution)."""
        return round(((self.authority * 0.625) + (self.approval * 0.375)) * self.factor, 4)


def authority_score(doc: Document) -> float:
    return doc.authority_level / 5 if doc.authority_level else UNKNOWN_AUTHORITY


def standing(doc: Document, as_of: date, lineage: Lineage, w: RankingWeights) -> DocStanding:
    auth = authority_score(doc)
    appr = APPROVAL_SCORE.get(doc.approval_status, 0.4)
    reasons = [
        f"authority {doc.authority_level or 'unknown'}/5",
        f"approval: {doc.approval_status}",
    ]
    start = valid_from(doc)
    superseded, by = lineage.superseded_at(doc.id, as_of)
    if doc.approval_status == "withdrawn":
        status, factor = "withdrawn", w.withdrawn_factor
        reasons.append("document withdrawn")
    elif superseded:
        status, factor = "superseded", w.superseded_factor
        succ = lineage.docs[by]
        reasons.append(f"superseded by {succ.filename} (effective {valid_from(succ) or 'unknown'})")
    elif start and start > as_of:
        status, factor = "not_yet_effective", w.not_yet_effective_factor
        reasons.append(f"not yet effective (starts {start}, as-of {as_of})")
    elif doc.approval_status in ("draft", "pending"):
        status, factor = "unapproved", w.unapproved_factor
        reasons.append(f"{doc.approval_status} - not an approved source")
    else:
        status, factor = "in_force", 1.0
        reasons.append(f"in force at {as_of}" + (f" (effective {start})" if start else " (effective date unknown)"))
    in_force = status == "in_force"
    return DocStanding(doc.id, in_force, status, auth, appr, factor, by, reasons)


@dataclass
class ScoredEvidence:
    chunk_id: str
    doc_id: str
    relevance: float
    score: float
    standing: DocStanding
    factors: dict[str, float]
    explanation: str


def recency_scores(docs: list[Document]) -> dict[str, float]:
    dated = {d.id: valid_from(d) for d in docs if valid_from(d)}
    if not dated:
        return {d.id: 0.5 for d in docs}
    lo, hi = min(dated.values()), max(dated.values())
    span = (hi - lo).days or 1
    return {d.id: ((dated[d.id] - lo).days / span if d.id in dated else 0.5) if hi != lo else 1.0 for d in docs}


def rank_evidence(
    hits: list,  # retrieval Hits (need chunk_id, doc_id, relevance)
    docs: dict[str, Document],
    lineage: Lineage,
    as_of: date,
    w: RankingWeights,
) -> list[ScoredEvidence]:
    cand_docs = [docs[h.doc_id] for h in hits if h.doc_id in docs]
    rec = recency_scores(list({d.id: d for d in cand_docs}.values()))
    total = (w.relevance + w.authority + w.approval + w.recency) or 1.0
    out: list[ScoredEvidence] = []
    for h in hits:
        doc = docs.get(h.doc_id)
        if doc is None:
            continue
        st = standing(doc, as_of, lineage, w)
        factors = {
            "relevance": round(h.relevance, 4),
            "authority": round(st.authority, 4),
            "approval": round(st.approval, 4),
            "recency": round(rec.get(doc.id, 0.5), 4),
            "in_force_factor": st.factor,
        }
        base = (
            w.relevance * h.relevance + w.authority * st.authority + w.approval * st.approval + w.recency * factors["recency"]
        ) / total
        score = round(base * st.factor, 4)
        explanation = "; ".join(st.reasons) + f"; relevance {h.relevance:.2f}"
        out.append(ScoredEvidence(h.chunk_id, h.doc_id, h.relevance, score, st, factors, explanation))
    out.sort(key=lambda e: -e.score)
    return out
