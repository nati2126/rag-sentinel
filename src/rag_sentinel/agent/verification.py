"""Explicit, testable evidence rules that decide VERIFIED / NEEDS_REVIEW / INSUFFICIENT_EVIDENCE.

The generator's own confidence is never used. Rules, in order:
  R1 no evidence, or the best passage is below the relevance threshold      -> INSUFFICIENT_EVIDENCE
  R2 no retrieved evidence is in force at the as-of date                     -> INSUFFICIENT_EVIDENCE
  R3 the generator declined to answer                                       -> INSUFFICIENT_EVIDENCE
  R4 the answer has no valid citation                                        -> INSUFFICIENT_EVIDENCE
  R5 the answer states numbers that none of its cited passages contain       -> NEEDS_REVIEW
  R6 every cited source is superseded / draft / not yet effective            -> NEEDS_REVIEW
  R7 an unresolved contradiction exists for a fact the answer relies on      -> NEEDS_REVIEW
  R8 the answer cites an outdated source but not the preferred one           -> NEEDS_REVIEW
  R9 the answer check finds the draft does not answer the question           -> INSUFFICIENT_EVIDENCE
  R10 the answer check finds statements the cited passages do not support   -> NEEDS_REVIEW
  otherwise                                                                  -> VERIFIED (with warnings)
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from rag_sentinel.claims.canonical import humanize
from rag_sentinel.claims.normalize import numbers_in
from rag_sentinel.retrieval.bm25 import tokenize

VERIFIED = "VERIFIED"
NEEDS_REVIEW = "NEEDS_REVIEW"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"
ANSWERED = "ANSWERED"  # baselines without verification

_LABEL = re.compile(r"\[(E\d+)\]")


@dataclass
class Verification:
    status: str
    rules_fired: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    valid_citations: list[str] = field(default_factory=list)
    invalid_citations: list[str] = field(default_factory=list)
    unsupported_values: list[str] = field(default_factory=list)
    blocking_conflicts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def citations_in(answer: str, listed: list[str]) -> list[str]:
    found = _LABEL.findall(answer)
    out: list[str] = []
    for lbl in found + [c.strip("[] ") for c in listed]:
        if lbl and lbl not in out:
            out.append(lbl)
    return out


_YEAR = re.compile(r"\b(19|20)\d\d\b")


def unsupported_numbers(
    answer: str, cited_texts: list[str], question: str = "", cited_meta: list[str] = ()
) -> list[str]:
    """Numbers in the answer that no cited passage contains.

    Also accepted: numbers in the cited documents' title / version / effective date ("Password Standard v1.0"),
    and years the question itself mentions ("in 2025"). Other question numbers are not accepted, so echoing
    a premise like "30 days" from the question still needs evidence.
    """
    text = _LABEL.sub(" ", answer)
    supported = set().union(*(numbers_in(t) for t in [*cited_texts, *cited_meta])) if cited_texts else set()
    supported |= {f"{float(m.group()):g}" for m in _YEAR.finditer(question)}
    return sorted(n for n in numbers_in(text) if n not in supported)


def relevant_keys(question: str, answer: str, cited_chunks: set[str], claims: list[dict]) -> set[str]:
    """Predicate keys of claims in cited passages that the answer actually relies on."""
    q = set(tokenize(question))
    nums = numbers_in(_LABEL.sub(" ", answer))
    keys = set()
    for c in claims:
        if c["chunk_id"] not in cited_chunks:
            continue
        ptoks = set(tokenize(humanize(c["predicate_key"]))) | set(tokenize(humanize(c["predicate"])))
        num = c.get("value_num")
        if (num is not None and f"{num:g}" in nums) or (ptoks & q):
            keys.add(c["predicate_key"])
    return keys


def states_conflict_value(conflict: dict, answer_nums: set[str]) -> bool | None:
    """Whether the answer states a numeric value of either conflicting claim (None: claims are not numeric)."""
    nums = [(conflict.get(side) or {}).get("value_num") for side in ("claim_a", "claim_b")]
    nums = [n for n in nums if n is not None]
    if not nums:
        return None
    return any(f"{n:g}" in answer_nums for n in nums)


def verify(
    *,
    question: str,
    generation: dict | None,
    evidence: list[dict],
    claims: list[dict],
    conflicts: list[dict],
    gating: bool,
    use_relevance_gate: bool,
    min_relevance: float,
    use_temporal: bool,
    use_conflicts: bool,
    as_of: str = "",
    answer_check: dict | None = None,
) -> Verification:
    if not gating:
        if not evidence or generation is None or generation.get("cannot_answer"):
            return Verification(INSUFFICIENT, ["baseline"], ["generator declined or no evidence"])
        labels = {e["label"] for e in evidence}
        cites = citations_in(generation["answer"], generation.get("citations", []))
        return Verification(ANSWERED, ["baseline"], valid_citations=[c for c in cites if c in labels],
                            invalid_citations=[c for c in cites if c not in labels])  # fmt: skip

    v = Verification(VERIFIED)
    if not evidence:
        return _fail(v, INSUFFICIENT, "R1", "No relevant evidence was retrieved.")
    top = max(e["relevance"] for e in evidence)
    if use_relevance_gate and top < min_relevance:
        return _fail(
            v, INSUFFICIENT, "R1", f"Best evidence relevance {top:.3f} is below the threshold {min_relevance}."
        )
    if use_temporal and not any(e.get("standing_status") == "in_force" for e in evidence):
        return _fail(v, INSUFFICIENT, "R2", "None of the retrieved sources is approved and in force at the as-of date.")
    if generation is None or generation.get("cannot_answer"):
        why = (generation or {}).get("reason") or "the evidence does not contain the answer"
        return _fail(v, INSUFFICIENT, "R3", f"Generator could not answer: {why}")

    by_label = {e["label"]: e for e in evidence}
    cites = citations_in(generation["answer"], generation.get("citations", []))
    v.valid_citations = [c for c in cites if c in by_label]
    v.invalid_citations = [c for c in cites if c not in by_label]
    if v.invalid_citations:
        v.warnings.append(f"Ignored citations to non-existent evidence: {', '.join(v.invalid_citations)}")
    if not v.valid_citations:
        return _fail(v, INSUFFICIENT, "R4", "The answer has no valid citation to the provided evidence.")

    if answer_check and not answer_check.get("answers_question", True):
        missing = answer_check.get("missing") or "the specific information asked for"
        return _fail(
            v, INSUFFICIENT, "R9", f"The evidence-based draft does not answer the question (missing: {missing})."
        )
    if answer_check and not answer_check.get("supported", True):
        why = (
            f"answer check failed: {answer_check['error']}"
            if answer_check.get("error")
            else "some statements are not in the cited evidence"
        )
        _flag(v, "R10", f"Answer check: {why}.")

    cited = [by_label[c] for c in v.valid_citations]
    # the as-of date is given to the generator, so "as of 2026-10-01" is not an unsupported value
    meta = [" ".join(str(e.get(k) or "") for k in ("title", "version", "effective_date")) for e in cited] + [as_of]
    v.unsupported_values = unsupported_numbers(generation["answer"], [e["text"] for e in cited], question, meta)
    if v.unsupported_values:
        _flag(v, "R5", f"Answer states values not found in the cited evidence: {', '.join(v.unsupported_values)}.")

    if use_temporal:
        if not any(e.get("standing_status") == "in_force" for e in cited):
            _flag(v, "R6", "Every cited source is superseded, unapproved or not yet effective at the as-of date.")
        for e in cited:
            if e.get("standing_status") not in ("in_force", None):
                v.warnings.append(f"{e['label']} ({e['filename']}) is {e['standing_status'].replace('_', ' ')}.")

    if use_conflicts:
        cited_chunks = {e["chunk_id"] for e in cited}
        cited_docs = {e["doc_id"] for e in cited}
        keys = relevant_keys(question, generation["answer"], cited_chunks, claims)
        answer_nums = numbers_in(_LABEL.sub(" ", generation["answer"]))
        for c in conflicts:
            if c["predicate_key"] not in keys or c["status"] == "dismissed":
                continue
            if states_conflict_value(c, answer_nums) is False:
                continue  # e.g. the answer gives the CFO threshold; the conflict is about the director threshold
            pair = {c["doc_a_id"], c["doc_b_id"]}
            if c["kind"] == "contradiction" and not c.get("preferred_doc_id") and c["status"] == "open":
                v.blocking_conflicts.append(c["id"])
                _flag(v, "R7", f"Unresolved contradiction: {c['explanation']}")
            elif c["kind"] in ("outdated", "contradiction") and c.get("preferred_doc_id"):
                preferred = c["preferred_doc_id"]
                loser = (pair - {preferred}).pop() if len(pair) == 2 else None
                if loser in cited_docs and preferred not in cited_docs:
                    v.blocking_conflicts.append(c["id"])
                    _flag(v, "R8", f"Answer relies on an outdated source. {c['explanation']}")
                else:
                    v.warnings.append(f"Conflict noted ({c['kind']}): {c['explanation']}")
            elif c["kind"] == "insufficient_evidence":
                v.warnings.append(
                    f"Possible inconsistency that could not be compared automatically: {c['explanation']}"
                )
    return v


def _fail(v: Verification, status: str, rule: str, reason: str) -> Verification:
    v.status = status
    v.rules_fired.append(rule)
    v.reasons.append(reason)
    return v


def _flag(v: Verification, rule: str, reason: str) -> None:
    if v.status == VERIFIED:
        v.status = NEEDS_REVIEW
    if rule not in v.rules_fired:
        v.rules_fired.append(rule)
    v.reasons.append(reason)
