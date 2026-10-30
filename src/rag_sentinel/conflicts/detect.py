"""Claim-level conflict detection.

For every pair of claims that share a canonical predicate (from different documents):

1. Context check (subject + qualifier) and value check (deterministic normalization). Equal values -> no
   finding. The rules then either decide or say they cannot:
   - definite: same subject (or one contains the other) and qualifiers, comparable values that differ, and
     neither document states several values for the attribute;
   - undecided: qualifiers differ, values are not comparable, a document states several values for the
     attribute (a scope the extractor missed, e.g. "$500 needs a director, $10,000 the CFO"), or the
     subjects share no words but a judge is available ("new hire" vs "employee").
2. Arbitration. Undecided pairs go to the LLM judge (without it: insufficient_evidence, or different_context
   for disjoint subjects). For definite pairs the judge only gives a second opinion: agreement is recorded
   (detected_by "rule+llm"), disagreement is stored as `judge_opinion` and shown for review, but the LLM
   never erases or downgrades a rule finding.
3. Same fact, different values -> temporal/authority analysis:
   - same lineage (version family or supersession chain)          -> historical
     (or pending_change when the differing version is a newer draft / not yet effective)
   - the losing doc is itself superseded or withdrawn              -> historical (nothing to update)
   - the losing doc is a draft / not yet effective                 -> pending_change
   - lower-standing doc repeats a superseded value of the winner  -> outdated (confirmed)
   - clear standing margin, loser is older                        -> outdated (possible, needs review)
   - clear standing margin, loser is newer                        -> contradiction (resolvable: preferred source)
   - no clear margin                                              -> contradiction (unresolved)

Different values alone never make a contradiction.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field

from rag_sentinel.claims.normalize import NormalizedValue, values_equivalent
from rag_sentinel.config import RankingWeights
from rag_sentinel.db import Claim, Document
from rag_sentinel.ingest.versioning import Lineage, valid_from
from rag_sentinel.llm import LLM, LLMOutputError
from rag_sentinel.ranking import standing

CONTRADICTION = "contradiction"
OUTDATED = "outdated"
HISTORICAL = "historical"
PENDING_CHANGE = "pending_change"
DIFFERENT_CONTEXT = "different_context"
COMPLEMENTARY = "complementary"
INSUFFICIENT = "insufficient_evidence"
ACTIONABLE = (CONTRADICTION, OUTDATED)

_SYNONYMS = {
    "employees": "employee", "staff": "employee", "personnel": "employee", "worker": "employee",
    "workers": "employee", "people": "employee", "colleague": "employee", "colleagues": "employee",
    "hire": "employee", "hires": "employee", "starter": "employee", "starters": "employee", "joiner": "employee",
    "joiners": "employee", "newcomer": "employee", "newcomers": "employee",
    "contractors": "contractor", "consultant": "contractor", "consultants": "contractor", "vendors": "vendor",
    "passwords": "password", "accounts": "account", "users": "user", "laptops": "laptop", "devices": "device",
    "fulltime": "full-time", "parttime": "part-time",
}  # fmt: skip
_CTX_STOP = {"all", "the", "a", "an", "of", "for", "each", "every", "any", "our", "company", "regular", "standard",
             "general", "eligible", "new", "and", "or", "to", "in", "on", "with", "is", "are", "be"}  # fmt: skip


def context_tokens(text: str | None) -> frozenset[str]:
    if not text:
        return frozenset()
    toks = re.findall(
        r"[a-z0-9][a-z0-9\-]*", text.lower().replace("full time", "full-time").replace("part time", "part-time")
    )
    out = set()
    for t in toks:
        t = _SYNONYMS.get(t, t)
        if t in _CTX_STOP:
            continue
        if t.endswith("s") and len(t) > 4 and not t.endswith("ss"):
            t = t[:-1]
        out.add(t)
    return frozenset(out)


def context_relation(a: Claim, b: Claim) -> str:
    """'same' | 'different' | 'ambiguous'."""
    sa, sb = context_tokens(a.subject), context_tokens(b.subject)
    qa, qb = context_tokens(a.qualifier), context_tokens(b.qualifier)
    if sa and sb and not (sa & sb):
        return "different"
    subject_same = sa == sb or sa <= sb or sb <= sa
    if qa != qb:
        return "ambiguous"
    return "same" if subject_same else "ambiguous"


class PairVerdict(BaseModel):
    relation: str  # same_fact_conflict | equivalent | different_context | complementary | unrelated
    reason: str = Field(max_length=400)


JUDGE_SYSTEM = "You compare factual claims from different documents. Output JSON only."
JUDGE_TEMPLATE = """Claim A (from "{da}"): "{qa}"
  extracted as: subject="{sa}", attribute="{pa}", value="{va}", condition="{ca}"
Claim B (from "{db}"): "{qb}"
  extracted as: subject="{sb}", attribute="{pb}", value="{vb}", condition="{cb}"

Classify the relation between A and B. Use exactly one of:
- "same_fact_conflict": same attribute, same subject and scope, but the values disagree.
- "equivalent": they state the same value (possibly worded differently).
- "different_context": they apply to different subjects, groups, conditions or scopes, so both can be true.
  (A group that is part of another counts as the same subject: new hires are employees.)
- "complementary": they describe related but different aspects; no disagreement.
- "unrelated": they are not about the same thing.
Do not answer "same_fact_conflict" just because the numbers differ: check subject and conditions first."""

_VERDICT_KINDS = {"same_fact_conflict", "equivalent", "different_context", "complementary", "unrelated"}


def make_pair_judge(
    llm: LLM, docs: dict[str, Document], cache_get=None, cache_set=None
) -> Callable[[Claim, Claim], str]:
    def judge(a: Claim, b: Claim) -> str:
        key = "pair:" + hashlib.sha256(f"{llm.name}|{min(a.id, b.id)}|{max(a.id, b.id)}|v3".encode()).hexdigest()
        if cache_get and (hit := cache_get(key)) is not None:
            return hit
        prompt = JUDGE_TEMPLATE.format(
            da=docs[a.doc_id].title or docs[a.doc_id].filename, qa=a.source_quote, sa=a.subject, pa=a.predicate,
            va=a.value, ca=a.qualifier or "none",
            db=docs[b.doc_id].title or docs[b.doc_id].filename, qb=b.source_quote, sb=b.subject, pb=b.predicate,
            vb=b.value, cb=b.qualifier or "none",
        )  # fmt: skip
        verdict = llm.chat_json(JUDGE_SYSTEM, prompt, PairVerdict)
        rel = verdict.relation if verdict.relation in _VERDICT_KINDS else "unrelated"
        if cache_set:
            cache_set(key, rel)
        return rel

    return judge


@dataclass
class Finding:
    id: str
    predicate_key: str
    claim_a: Claim
    claim_b: Claim
    kind: str
    confirmed: bool
    preferred_doc_id: str | None
    margin: float | None
    explanation: str
    detected_by: str
    judge_opinion: str | None = None  # set when the LLM judge disagrees with a rule finding


def finding_id(a: Claim, b: Claim) -> str:
    x, y = sorted((a.id, b.id))
    return hashlib.sha256(f"{x}|{y}".encode()).hexdigest()[:20]


def _nv(c: Claim) -> NormalizedValue:
    return NormalizedValue(c.value_kind, c.value_num, c.value_unit, c.value_norm)


def _label(d: Document) -> str:
    v = f" v{d.version_label}" if d.version_label else ""
    return f"'{d.title or d.filename}{v}'"


class ConflictDetector:
    def __init__(
        self,
        docs: dict[str, Document],
        claims: list[Claim],
        lineage: Lineage,
        as_of: date,
        weights: RankingWeights | None = None,
        margin_threshold: float = 0.12,
        judge: Callable[[Claim, Claim], str] | None = None,
    ):
        self.docs = docs
        self.claims = [c for c in claims if c.doc_id in docs]
        self.lineage = lineage
        self.as_of = as_of
        self.w = weights or RankingWeights()
        self.margin_threshold = margin_threshold
        self.judge = judge
        self._standing = {d: standing(doc, as_of, lineage, self.w) for d, doc in docs.items()}
        self.by_key: dict[str, list[Claim]] = defaultdict(list)
        for c in self.claims:
            self.by_key[c.predicate_key].append(c)
        values: dict[tuple[str, str], set[str]] = defaultdict(set)
        for c in self.claims:
            values[(c.doc_id, c.predicate_key)].add(c.value_norm)
        # (doc, key) pairs where one document states several values: the claims carry a scope we did not extract
        self._multi_valued = {k for k, v in values.items() if len(v) > 1}

    def detect(self, keys: set[str] | None = None) -> list[Finding]:
        out: list[Finding] = []
        for key, group in sorted(self.by_key.items()):
            if keys is not None and key not in keys:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    f = self.classify(group[i], group[j])
                    if f is not None:
                        out.append(f)
        return out

    # -- pair classification ------------------------------------------------
    def classify(self, a: Claim, b: Claim) -> Finding | None:
        if a.doc_id == b.doc_id:
            return None
        ctx = context_relation(a, b)
        eq = values_equivalent(_nv(a), _nv(b))
        if eq is True and ctx != "different":
            return None
        if ctx == "different" and self.judge is not None and eq is not True:
            ctx = "ambiguous"  # disjoint subject words ("new hire" vs "employee") may still be the same group
        if ctx == "different":
            if eq is True:
                return None
            return self._make(a, b, DIFFERENT_CONTEXT, f"Different subjects: '{a.subject}' vs '{b.subject}'.", "rule")
        hidden_scope = (a.doc_id, a.predicate_key) in self._multi_valued or (
            b.doc_id,
            b.predicate_key,
        ) in self._multi_valued
        if ctx == "ambiguous" or eq is None or hidden_scope:
            return self._judge_led(a, b, ctx, eq, hidden_scope)
        finding = self._temporal(a, b, "rule")
        if self.judge is not None and finding.kind in ACTIONABLE:
            self._second_opinion(finding)
        return finding

    def _judge_led(self, a: Claim, b: Claim, ctx: str, eq: bool | None, hidden_scope: bool) -> Finding | None:
        """The rules cannot decide; the LLM judge classifies the pair (or, without one, flag it for review)."""
        if self.judge is None:
            why = (
                "conditions differ"
                if ctx == "ambiguous"
                else "values are not directly comparable"
                if eq is None
                else "a document states several values for this attribute"
            )
            return self._make(a, b, INSUFFICIENT, f"Cannot compare reliably ({why}); semantic judge disabled.", "rule")
        try:
            rel = self.judge(a, b)
        except LLMOutputError as exc:
            # recorded as a finding for review, never silently dropped or guessed
            return self._make(a, b, INSUFFICIENT, f"Semantic judge failed on this pair: {str(exc)[:200]}", "llm_error")
        if rel in ("equivalent", "unrelated"):
            return None
        if rel == "different_context":
            return self._make(a, b, DIFFERENT_CONTEXT, "Judged to apply to different contexts.", "llm")
        if rel == "complementary":
            return self._make(a, b, COMPLEMENTARY, "Judged complementary (different aspects).", "llm")
        return self._temporal(a, b, "llm")

    def _second_opinion(self, f: Finding) -> None:
        """Ask the judge about a rule finding. Agreement raises confidence; disagreement is recorded, not applied."""
        try:
            rel = self.judge(f.claim_a, f.claim_b)
        except LLMOutputError:
            f.explanation += " (Semantic second opinion unavailable.)"
            return
        if rel == "same_fact_conflict":
            f.detected_by = "rule+llm"
            return
        f.judge_opinion = rel
        f.explanation += (
            f" The semantic judge considers these claims {rel.replace('_', ' ')}; the finding is kept for review "
            "because subject, attribute and values match by rule."
        )

    def _temporal(self, a: Claim, b: Claim, detected_by: str) -> Finding:
        da, db = self.docs[a.doc_id], self.docs[b.doc_id]
        sa, sb = self._standing[da.id], self._standing[db.id]
        if self.lineage.same_lineage(da.id, db.id):
            if self.lineage.is_ancestor(db.id, da.id) or (sa.score > sb.score):
                cur, old, cc, oc = da, db, a, b
            else:
                cur, old, cc, oc = db, da, b, a
            cur_st, old_st = self._standing[cur.id], self._standing[old.id]
            note = "in force" if cur_st.in_force else cur_st.status.replace("_", " ")
            other_newer = self.lineage.is_ancestor(cur.id, old.id) or (
                valid_from(old) is not None and valid_from(cur) is not None and valid_from(old) > valid_from(cur)
            )
            if cur_st.in_force and other_newer and old_st.status in ("unapproved", "not_yet_effective"):
                return self._make(
                    a, b, PENDING_CHANGE,
                    f"{_label(old)} ({old_st.status.replace('_', ' ')}) would change '{cc.value}' to '{oc.value}'; "
                    f"{_label(cur)} remains in force at {self.as_of}.",
                    detected_by, preferred=cur.id, confirmed=True,
                )  # fmt: skip
            return self._make(
                a, b, HISTORICAL,
                f"Version difference within one document lineage: {_label(cur)} states '{cc.value}' "
                f"({note} at {self.as_of}); {_label(old)} states '{oc.value}' ({old_st.status.replace('_', ' ')}).",
                detected_by, preferred=cur.id if cur_st.in_force else None, confirmed=True,
            )  # fmt: skip

        (win, wc, ws), (lose, lc, ls) = sorted(((da, a, sa), (db, b, sb)), key=lambda t: -t[2].score)
        margin = round(ws.score - ls.score, 4)
        if ls.status in ("superseded", "withdrawn"):
            return self._make(
                a, b, HISTORICAL,
                f"{_label(lose)} ('{lc.value}') is {ls.status} at {self.as_of}; {_label(win)} states '{wc.value}'. "
                "No update needed.",
                detected_by, preferred=win.id if ws.in_force else None, margin=margin, confirmed=True,
            )  # fmt: skip
        if ws.in_force and ls.status in ("unapproved", "not_yet_effective"):
            return self._make(
                a, b, PENDING_CHANGE,
                f"{_label(lose)} ({ls.status.replace('_', ' ')}) states '{lc.value}'; {_label(win)} ('{wc.value}') "
                f"is in force at {self.as_of}.",
                detected_by, preferred=win.id, margin=margin, confirmed=True,
            )  # fmt: skip
        old_values = self._superseded_values(win, a.predicate_key)
        if lc.value_norm in old_values:
            src = old_values[lc.value_norm]
            return self._make(
                a, b, OUTDATED,
                f"{_label(lose)} still states '{lc.value}', the value from superseded {_label(src)}. "
                f"Current authoritative value: '{wc.value}' in {_label(win)}.",
                detected_by, preferred=win.id, margin=margin, confirmed=True,
            )  # fmt: skip
        if margin >= self.margin_threshold:
            lose_start, win_start = valid_from(lose), valid_from(win)
            if lose_start is None or win_start is None or lose_start <= win_start:
                return self._make(
                    a, b, OUTDATED,
                    f"{_label(lose)} ('{lc.value}') is older and has lower standing than {_label(win)} "
                    f"('{wc.value}'). Possibly outdated: confirm and update.",
                    detected_by, preferred=win.id, margin=margin, confirmed=False,
                )  # fmt: skip
            return self._make(
                a, b, CONTRADICTION,
                f"{_label(lose)} ('{lc.value}') is newer but has lower standing than {_label(win)} ('{wc.value}'). "
                f"Prefer {_label(win)}; review the newer document.",
                detected_by, preferred=win.id, margin=margin, confirmed=True,
            )  # fmt: skip
        return self._make(
            a, b, CONTRADICTION,
            f"Unresolved: {_label(da)} states '{a.value}' and {_label(db)} states '{b.value}'; "
            f"neither source clearly outranks the other (standing {sa.score:.2f} vs {sb.score:.2f}).",
            detected_by, preferred=None, margin=margin, confirmed=True,
        )  # fmt: skip

    def _superseded_values(self, doc: Document, key: str) -> dict[str, Document]:
        """Values for `key` stated by superseded/older members of doc's lineage."""
        out: dict[str, Document] = {}
        for member in self.lineage.lineage_members(doc.id):
            if member.id == doc.id or member.id not in self.docs:
                continue
            if not (self.lineage.is_ancestor(member.id, doc.id) or not self._standing[member.id].in_force):
                continue
            for c in self.by_key.get(key, []):
                if c.doc_id == member.id:
                    out.setdefault(c.value_norm, member)
        return out

    def _make(
        self, a: Claim, b: Claim, kind: str, explanation: str, detected_by: str,
        preferred: str | None = None, margin: float | None = None, confirmed: bool = True,
    ) -> Finding:  # fmt: skip
        return Finding(
            finding_id(a, b), a.predicate_key, a, b, kind, confirmed, preferred, margin, explanation, detected_by
        )


def naive_value_conflicts(claims: list[Claim]) -> list[tuple[Claim, Claim]]:
    """Baseline for H3: any two claims with the same predicate key and different values are 'conflicts'."""
    by_key: dict[str, list[Claim]] = defaultdict(list)
    for c in claims:
        by_key[c.predicate_key].append(c)
    pairs = []
    for group in by_key.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                if a.doc_id != b.doc_id and a.value_norm != b.value_norm:
                    pairs.append((a, b))
    return pairs
