"""Predicate canonicalization: map 'annual_leave_days' and 'annual_leave_entitlement' to one key.

Identical snake_case names merge directly. Different names merge only when their label embeddings are
similar AND (if a judge is available) the LLM confirms they describe the same attribute. Without a judge
only very close names merge. The order is deterministic (frequency, then name), so the result does not
depend on ingestion order.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable

import numpy as np
from pydantic import BaseModel

from rag_sentinel.llm import LLM

STRICT_WITHOUT_JUDGE = 0.95


class SameAttribute(BaseModel):
    same_attribute: bool
    reason: str


JUDGE_SYSTEM = "You compare attribute names extracted from documents. Output JSON only."
JUDGE_TEMPLATE = """Two facts were extracted from different documents.

A: attribute "{a}", example: "{qa}"
B: attribute "{b}", example: "{qb}"

Do A and B describe the SAME attribute, so that their values could be directly compared
(for example both are "the number of annual leave days an employee gets")?
Answer false if one is a different aspect (e.g. carry-over vs entitlement, minimum vs maximum,
reporting deadline vs resolution deadline)."""


def humanize(predicate: str) -> str:
    return predicate.replace("_", " ")


def make_llm_judge(llm: LLM, cache_get=None, cache_set=None) -> Callable[[str, str, str, str], bool]:
    def judge(a: str, b: str, qa: str, qb: str) -> bool:
        key = f"same-attr:{llm.name}:{min(a, b)}|{max(a, b)}"
        if cache_get and (hit := cache_get(key)) is not None:
            return bool(hit)
        res = llm.chat_json(
            JUDGE_SYSTEM, JUDGE_TEMPLATE.format(a=humanize(a), b=humanize(b), qa=qa[:300], qb=qb[:300]), SameAttribute
        )
        if cache_set:
            cache_set(key, res.same_attribute)
        return res.same_attribute

    return judge


def canonicalize(
    predicates: list[str],
    examples: dict[str, str],
    embed_labels: Callable[[list[str]], np.ndarray],
    threshold: float = 0.86,
    judge: Callable[[str, str, str, str], bool] | None = None,
) -> dict[str, str]:
    """Return predicate -> canonical key."""
    counts = Counter(predicates)
    ordered = sorted(counts, key=lambda p: (-counts[p], p))
    if not ordered:
        return {}
    vecs = embed_labels([humanize(p) for p in ordered])
    reps: list[int] = []  # indices into ordered
    mapping: dict[str, str] = {}
    for i, p in enumerate(ordered):
        if reps:
            sims = vecs[reps] @ vecs[i]
            for j in np.argsort(-sims):
                sim = float(sims[j])
                if sim < threshold:
                    break
                rep = ordered[reps[j]]
                ok = judge(rep, p, examples.get(rep, ""), examples.get(p, "")) if judge else sim >= STRICT_WITHOUT_JUDGE
                if ok:
                    mapping[p] = rep
                    break
        if p not in mapping:
            reps.append(i)
            mapping[p] = p
    return mapping
