"""Deterministic temporal intent detection: current vs. historical (as of a date) vs. previous version."""

from __future__ import annotations

import calendar
import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta

from rag_sentinel.ingest.metadata import parse_date

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE_EXPR = re.compile(
    rf"\b(?P<prep>as of|as at|on|in|during|before|prior to|until|through|from|after|since)\s+"
    rf"(?:the start of |the end of |early |late )?"
    rf"(?P<date>{_MONTH}\s+\d{{1,2}},?\s+\d{{4}}|\d{{1,2}}\s+{_MONTH}\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}|{_MONTH}\s+\d{{4}}|\d{{4}})\b",
    re.IGNORECASE,
)
_PREVIOUS = re.compile(
    r"\b(previous(?:ly)?|prior (?:version|policy|rule|value|limit)|former(?:ly)?|original(?:ly)?|used to|"
    r"old (?:policy|rule|value|limit|version)|before the (?:latest |recent |most recent |last )?"
    r"(?:change|update|revision|version|policy change|increase|decrease))\b",
    re.IGNORECASE,
)
# "the 2024 to 2025 tax year", "2024-25", "2024/25": a UK tax year, 6 April to 5 April
_TAX_YEAR = re.compile(r"\b(?P<y1>(?:19|20)\d\d)\s*(?:to|-|–|/)\s*(?P<y2>(?:19|20)?\d\d)\b")
# "between March 2024 and June 2025": a comparison of two periods
_BETWEEN = re.compile(
    rf"\bbetween\s+(?:the\s+)?(?P<a>{_MONTH}\s+\d{{4}}|\d{{4}})\s+and\s+(?:the\s+)?(?P<b>{_MONTH}\s+\d{{4}}|\d{{4}})\b",
    re.IGNORECASE,
)
_FUTURE = re.compile(r"\b(will|going to|upcoming|next year|scheduled|planned)\b", re.IGNORECASE)


@dataclass
class QueryAnalysis:
    question: str
    mode: str  # current | historical | previous
    as_of: date
    reference_date: date
    temporal_phrase: str | None = None
    note: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["as_of"], d["reference_date"] = self.as_of.isoformat(), self.reference_date.isoformat()
        return d


def _resolve(prep: str, raw: str) -> date | None:
    raw = raw.strip()
    prep = prep.lower()
    if re.fullmatch(r"\d{4}", raw):
        y = int(raw)
        start, end = date(y, 1, 1), date(y, 12, 31)
    elif re.fullmatch(rf"{_MONTH}\s+\d{{4}}", raw, re.IGNORECASE):
        d = parse_date("1 " + raw)
        if d is None:
            return None
        start, end = d, d.replace(day=calendar.monthrange(d.year, d.month)[1])
    else:
        d = parse_date(raw)
        if d is None:
            return None
        start = end = d
    if prep in ("before", "prior to"):
        return start - timedelta(days=1)
    if prep in ("from", "after", "since"):
        return start
    return end


def _period_end(question: str) -> tuple[date, str] | None:
    """End of the latest tax year or 'between' period the question names (comparisons need the later one)."""
    ends: list[tuple[date, str]] = []
    for m in _TAX_YEAR.finditer(question):
        y1, y2 = int(m.group("y1")), int(m.group("y2"))
        if y2 < 100:
            y2 += y1 // 100 * 100
        if y2 == y1 + 1:
            ends.append((date(y2, 4, 5), m.group(0)))
    if m := _BETWEEN.search(question):
        if (end := _resolve("in", m.group("b"))) is not None:
            ends.append((end, m.group(0)))
    return max(ends) if ends else None


def analyze_query(question: str, reference: date) -> QueryAnalysis:
    if found := _period_end(question):
        end, phrase = found
        if end < reference:
            return QueryAnalysis(question, "historical", end, reference, phrase,
                                 "period named in the question ended before the reference date")  # fmt: skip
        if not _FUTURE.search(question):
            return QueryAnalysis(question, "current", reference, reference, phrase,
                                 "period covers the reference date: treated as current")  # fmt: skip
    if m := _DATE_EXPR.search(question):
        as_of = _resolve(m.group("prep"), m.group("date"))
        if as_of is not None:
            if as_of >= reference and not _FUTURE.search(question):
                return QueryAnalysis(question, "current", reference, reference, m.group(0),
                                     "date expression covers the reference date: treated as current")  # fmt: skip
            return QueryAnalysis(question, "historical", as_of, reference, m.group(0))
    if m := _PREVIOUS.search(question):
        return QueryAnalysis(question, "previous", reference, reference, m.group(0),
                             "as-of date is resolved from the current version's start date during ranking")  # fmt: skip
    return QueryAnalysis(question, "current", reference, reference)
