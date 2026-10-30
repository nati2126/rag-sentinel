"""Deterministic value normalization and comparison.

Values that can be parsed (quantities, money, percentages, dates, required/prohibited rules) are compared
without the LLM. `values_equivalent` returns None when the values cannot be compared reliably.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rag_sentinel.ingest.metadata import parse_date

_NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "eighteen": 18, "twenty": 20, "twenty-five": 25, "thirty": 30, "forty": 40,
    "forty-five": 45, "fifty": 50, "sixty": 60, "seventy": 70, "ninety": 90, "hundred": 100,
}  # fmt: skip

_UNIT_ALIASES = {
    "calendar day": "day", "day": "day",
    "working day": "workday", "business day": "workday", "workday": "workday",
    "week": "week", "month": "month", "year": "year", "hour": "hour", "hr": "hour", "h": "hour",
    "minute": "minute", "min": "minute", "second": "second",
    "character": "character", "char": "character", "digit": "digit",
    "gb": "gb", "mb": "mb", "tb": "tb", "attempt": "attempt", "device": "device", "employee": "employee",
}  # fmt: skip

# Convertible time units (calendar based). Working days are deliberately not convertible.
_TO_HOURS = {"minute": 1 / 60, "hour": 1, "day": 24, "week": 168}
_TO_MONTHS = {"month": 1, "year": 12}

_CURRENCY = {"$": "usd", "usd": "usd", "dollar": "usd", "dollars": "usd", "€": "eur", "eur": "eur",
             "euro": "eur", "euros": "eur", "£": "gbp", "gbp": "gbp", "etb": "etb", "birr": "etb"}  # fmt: skip

_MODAL = [
    ("prohibited", r"\b(prohibited|forbidden|not (?:allowed|permitted)|must not|may not|banned|disallowed)\b"),
    ("optional", r"\b(not required|optional|not mandatory|no longer required)\b"),
    ("required", r"\b(required|mandatory|must|shall|compulsory|enforced)\b"),
    ("allowed", r"\b(allowed|permitted|may|supported|enabled)\b"),
    ("no", r"^(no|false|none|never|disabled)$"),
    ("yes", r"^(yes|true)$"),
]

_NUM = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)"
_MONEY = re.compile(
    rf"(?:([$€£]|\b(?:usd|eur|gbp|etb))\s*{_NUM})|(?:{_NUM}\s*(usd|eur|gbp|etb|dollars?|euros?|birr)\b)", re.I
)
_PERCENT = re.compile(rf"{_NUM}\s*(%|percent\b)", re.I)
_QTY = re.compile(rf"{_NUM}\s*([a-z][a-z\-]*(?:\s+(?:day|days))?)?", re.I)
_DATE_LIKE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b"
    r"|\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b"
    r"|\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}\b",
    re.I,
)
_FILLER = {"or", "and", "to", "of", "per", "a", "up", "at", "least", "most", "than", "from", "in", "the", "is", "by",
           "version", "v", "release", "minimum", "maximum", "max", "min"}  # fmt: skip
_VERSIONISH = re.compile(r"\b([a-z][a-z+#]*)\s*v?(\d+\.\d+(?:\.\d+)?)\b", re.I)


@dataclass(frozen=True)
class NormalizedValue:
    kind: str  # quantity | money | percent | date | modal | text
    num: float | None
    unit: str | None
    norm: str


def _to_float(s: str) -> float:
    return float(s.replace(",", ""))


def _words_to_digits(text: str) -> str:
    def repl(m: re.Match) -> str:
        return str(_NUMBER_WORDS[m.group(0).lower()])

    pattern = r"\b(" + "|".join(sorted(map(re.escape, _NUMBER_WORDS), key=len, reverse=True)) + r")\b"
    return re.sub(pattern, repl, text, flags=re.I)


def _unit(raw: str | None) -> str:
    if not raw:
        return ""
    u = raw.lower().strip().replace("-", " ")
    u = re.sub(r"\s+", " ", u)
    if u.endswith("s") and u[:-1] in _UNIT_ALIASES:
        u = u[:-1]
    if u.endswith("days"):
        u = u[:-1]
    return _UNIT_ALIASES.get(u, u)


def normalize_text(text: str) -> str:
    t = re.sub(r"[^\w\s.%$-]", " ", text.lower())
    return re.sub(r"\s+", " ", t).strip()


def normalize_value(raw: str) -> NormalizedValue:
    text = raw.strip()
    low = text.lower()

    if m := _MONEY.search(text):
        if m.group(1):
            cur, num = _CURRENCY.get(m.group(1).lower(), m.group(1).lower()), _to_float(m.group(2))
        else:
            cur, num = _CURRENCY.get(m.group(4).lower(), m.group(4).lower()), _to_float(m.group(3))
        return NormalizedValue("money", num, cur, f"{num:g} {cur}")

    if m := _PERCENT.search(text):
        num = _to_float(m.group(1))
        return NormalizedValue("percent", num, "%", f"{num:g}%")

    if _DATE_LIKE.search(text) and (d := parse_date(_DATE_LIKE.search(text).group(0))):
        return NormalizedValue("date", None, None, d.isoformat())

    converted = _words_to_digits(text)
    qty = _QTY.search(converted)
    unit = _unit(qty.group(2)) if qty else ""
    if unit in _FILLER:
        unit = ""
    if qty and unit:
        num = _to_float(qty.group(1))
        return NormalizedValue("quantity", num, unit, f"{num:g} {unit}")

    vm = _VERSIONISH.search(text)  # "TLS 1.2", "Python 3.12": a named version, compared as text
    if vm and vm.group(1).lower() not in _FILLER:
        return NormalizedValue("text", None, None, f"{vm.group(1).lower()} {vm.group(2)}")

    if qty:
        num = _to_float(qty.group(1))
        return NormalizedValue("quantity", num, None, f"{num:g}")

    for label, pattern in _MODAL:
        if re.search(pattern, low):
            return NormalizedValue("modal", None, None, label)

    return NormalizedValue("text", None, None, normalize_text(text))


def _same_magnitude(a: NormalizedValue, b: NormalizedValue) -> bool | None:
    if a.unit == b.unit:
        return abs((a.num or 0) - (b.num or 0)) < 1e-9
    if a.unit in _TO_HOURS and b.unit in _TO_HOURS:
        return abs(a.num * _TO_HOURS[a.unit] - b.num * _TO_HOURS[b.unit]) < 1e-6
    if a.unit in _TO_MONTHS and b.unit in _TO_MONTHS:
        return abs(a.num * _TO_MONTHS[a.unit] - b.num * _TO_MONTHS[b.unit]) < 1e-6
    if not a.unit or not b.unit:  # "12" vs "12 characters": the number is what matters
        return abs((a.num or 0) - (b.num or 0)) < 1e-9
    return None  # e.g. working days vs weeks


def values_equivalent(a: NormalizedValue, b: NormalizedValue) -> bool | None:
    """True/False when deterministic comparison is possible, None when it is not."""
    if a.kind != b.kind:
        return None
    if a.kind == "quantity":
        return _same_magnitude(a, b)
    if a.kind == "money":
        return abs(a.num - b.num) < 1e-9 if a.unit == b.unit else None
    if a.kind in ("percent", "date", "modal"):
        return a.norm == b.norm
    return True if a.norm == b.norm else None


_ANY_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def numbers_in(text: str) -> set[str]:
    """Numbers mentioned in a text (number words converted), used for grounding checks."""
    out = set()
    for n in _ANY_NUMBER.findall(_words_to_digits(text)):
        try:
            out.add(f"{_to_float(n):g}")
        except ValueError:
            continue
    return out
