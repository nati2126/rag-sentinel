"""LLM claim extraction with grounding checks.

A claim is only kept if (1) its source_quote is actually present in the chunk (exactly or as a near-exact
match, after which the quote is replaced with the real chunk text) and (2) its value is stated in that quote.
This prevents hallucinated claims from entering the conflict detector.
"""

from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from rag_sentinel.claims.normalize import normalize_value, numbers_in
from rag_sentinel.db import Claim
from rag_sentinel.ingest.metadata import parse_date
from rag_sentinel.llm import LLM

PROMPT_VERSION = "claims-v4"

SYSTEM = (
    "You extract checkable factual claims from policy and technical documents. "
    "You copy quotes verbatim and never invent facts. Output JSON only."
)

USER_TEMPLATE = """Document: {title}
Passage:
\"\"\"
{text}
\"\"\"

Extract every specific, checkable fact stated in the passage: numeric limits, durations, amounts, deadlines,
dates, percentages, minimum/maximum values, required/prohibited/allowed rules, supported or removed versions.

For each claim:
- subject: who or what the rule applies to, e.g. "full-time employee", "contractor", "password", "TLS".
- predicate: short snake_case attribute name, general enough to match the same fact in other documents,
  e.g. "annual_leave_entitlement", "meal_per_diem", "password_min_length", "log_retention_period".
  Never put the value in the predicate.
- value: the value with its unit exactly as written, e.g. "25 days", "$60", "12 characters", "required", "TLS 1.2".
- qualifier: conditions or scope that limit the claim (e.g. "after 5 years of service", "international travel"),
  or "" if none. Always include:
  * the case of an enumerated list: "20.5 cents per mile ... (1) for medical care" -> qualifier "medical care";
  * the row and column of a table cell: "| Plan 2 | £29,385 | £2,448 |" under "Yearly | Monthly"
    -> one claim per cell, qualifier "Plan 2, yearly" and "Plan 2, monthly";
  * the period the value applies to, if stated: "calendar year 2026", "2025 to 2026 tax year".
- effective_date: YYYY-MM-DD only if the passage states when this specific value takes effect, otherwise "".
- source_quote: the exact sentence (or table row) from the passage that states the claim, copied character
  for character.
- confidence: 0 to 1, how explicitly the passage states the claim.

Skip the document title, the document's own version number, and section headings.
If the passage contains no such facts, return {{"claims": []}}."""


class ExtractedClaim(BaseModel):
    subject: str = Field(min_length=1, max_length=120)
    predicate: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=160)
    qualifier: str = Field(default="", max_length=200)
    effective_date: str = Field(default="", max_length=20)
    source_quote: str = Field(min_length=5, max_length=1200)
    confidence: float = Field(ge=0.0, le=1.0)


class ClaimList(BaseModel):
    claims: list[ExtractedClaim] = Field(default_factory=list, max_length=15)


@dataclass
class ExtractionReport:
    accepted: list[Claim] = field(default_factory=list)
    rejected: list[tuple[ExtractedClaim, str]] = field(default_factory=list)
    cached: bool = False


def snake(predicate: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", predicate.lower()).strip("_")


def _ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def locate_quote(quote: str, chunk_text: str, min_ratio: float = 0.9) -> str | None:
    """Return the chunk's own text for the quote, or None when the quote is not in the chunk."""
    q = _ws(quote).strip(" \"'")
    flat = _ws(chunk_text)
    if not q:
        return None
    idx = flat.lower().find(q.lower())
    if idx >= 0:
        return flat[idx : idx + len(q)]
    # Near-exact match against sentences / lines (models sometimes fix punctuation or drop a bullet char).
    candidates = re.split(r"(?<=[.!?])\s+|\n", chunk_text)
    best, best_ratio = None, 0.0
    for cand in candidates:
        c = _ws(cand)
        if not c:
            continue
        ratio = difflib.SequenceMatcher(None, q.lower(), c.lower()).ratio()
        if ratio > best_ratio:
            best, best_ratio = c, ratio
    return best if best_ratio >= min_ratio else None


def value_grounded(value: str, quote: str) -> bool:
    nums = numbers_in(value)
    if nums:
        return nums <= numbers_in(quote)
    tokens = [t for t in re.findall(r"[a-z0-9.]+", value.lower()) if len(t) > 2]
    q = quote.lower()
    return all(t in q for t in tokens) if tokens else False


def claim_id(chunk_id: str, subject: str, predicate: str, value: str) -> str:
    return hashlib.sha256(f"{chunk_id}|{subject.lower()}|{predicate}|{value.lower()}".encode()).hexdigest()[:20]


def cache_key(model: str, title: str, text: str) -> str:
    return "claims:" + hashlib.sha256(f"{model}|{PROMPT_VERSION}|{title}|{text}".encode()).hexdigest()


def to_claims(raw: ClaimList, chunk_id: str, doc_id: str, chunk_text: str, extractor: str) -> ExtractionReport:
    report = ExtractionReport()
    seen: set[str] = set()
    for c in raw.claims:
        quote = locate_quote(c.source_quote, chunk_text)
        if quote is None:
            report.rejected.append((c, "source_quote not found in passage"))
            continue
        if not value_grounded(c.value, quote):
            report.rejected.append((c, "value not stated in source_quote"))
            continue
        pred = snake(c.predicate)
        if not pred:
            report.rejected.append((c, "empty predicate"))
            continue
        cid = claim_id(chunk_id, c.subject, pred, c.value)
        if cid in seen:
            continue
        seen.add(cid)
        nv = normalize_value(c.value)
        report.accepted.append(
            Claim(
                id=cid,
                doc_id=doc_id,
                chunk_id=chunk_id,
                subject=c.subject.strip().lower(),
                predicate=pred,
                predicate_key=pred,
                value=c.value.strip(),
                value_kind=nv.kind,
                value_num=nv.num,
                value_unit=nv.unit,
                value_norm=nv.norm,
                qualifier=c.qualifier.strip() or None,
                effective_date=parse_date(c.effective_date) if c.effective_date else None,
                source_quote=quote,
                confidence=c.confidence,
                extractor=f"{extractor}/{PROMPT_VERSION}",
            )
        )
    return report


def extract_claims(
    llm: LLM, chunk_id: str, doc_id: str, title: str, text: str, cache_get=None, cache_set=None
) -> ExtractionReport:
    key = cache_key(llm.name, title, text)
    raw_json = cache_get(key) if cache_get else None
    cached = raw_json is not None
    if cached:
        raw = ClaimList.model_validate(raw_json)
    else:
        raw = llm.chat_json(SYSTEM, USER_TEMPLATE.format(title=title, text=text), ClaimList)
        if cache_set:
            cache_set(key, raw.model_dump())
    report = to_claims(raw, chunk_id, doc_id, text, llm.name)
    report.cached = cached
    return report
