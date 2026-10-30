"""Metadata merging with provenance.

Precedence: user-provided > sidecar/front matter > file container. Missing fields stay missing.
Dates found by scanning the text are returned as *suggestions* and never written into trusted fields.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from dateutil import parser as dateparser
from pydantic import BaseModel, field_validator

APPROVAL_STATUSES = ("approved", "pending", "draft", "withdrawn", "unknown")
_APPROVAL_ALIASES = {
    "final": "approved",
    "active": "approved",
    "published": "approved",
    "in review": "pending",
    "under review": "pending",
    "proposed": "pending",
    "retired": "withdrawn",
    "obsolete": "withdrawn",
    "superseded": "withdrawn",
}


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return dateparser.parse(str(value), default=datetime(2000, 1, 1)).date()
    except (ValueError, OverflowError):
        return None


def normalize_approval(value: Any) -> str:
    v = str(value or "").strip().lower()
    v = _APPROVAL_ALIASES.get(v, v)
    return v if v in APPROVAL_STATUSES else "unknown"


class DocumentMetadata(BaseModel):
    """Trusted metadata fields. All optional: absent means unknown."""

    title: str | None = None
    family: str | None = None
    version: str | None = None
    created_date: date | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    last_modified: date | None = None
    source_org: str | None = None
    authority_level: int | None = None
    approval_status: str | None = None
    supersedes: str | None = None

    @field_validator("created_date", "publication_date", "effective_date", "last_modified", mode="before")
    @classmethod
    def _dates(cls, v: Any) -> date | None:
        return parse_date(v)

    @field_validator("approval_status", mode="before")
    @classmethod
    def _approval(cls, v: Any) -> str | None:
        return None if v in (None, "") else normalize_approval(v)

    @field_validator("authority_level", mode="before")
    @classmethod
    def _authority(cls, v: Any) -> int | None:
        if v in (None, ""):
            return None
        level = int(v)
        if not 1 <= level <= 5:
            raise ValueError("authority_level must be between 1 and 5")
        return level

    @field_validator("version", "title", "family", "source_org", "supersedes", mode="before")
    @classmethod
    def _strings(cls, v: Any) -> str | None:
        return None if v in (None, "") else str(v).strip()


def merge_metadata(layers: list[tuple[str, dict[str, Any]]]) -> tuple[DocumentMetadata, dict[str, str]]:
    """Merge metadata layers given lowest-precedence first. Returns merged values and field -> source."""
    merged: dict[str, Any] = {}
    sources: dict[str, str] = {}
    known = set(DocumentMetadata.model_fields)
    for source, layer in layers:
        clean = DocumentMetadata.model_validate({k: v for k, v in (layer or {}).items() if k in known})
        for key, value in clean.model_dump(exclude_none=True).items():
            merged[key] = value
            sources[key] = source
    return DocumentMetadata.model_validate(merged), sources


def load_sidecar(path: Path) -> dict[str, Any]:
    """Optional `<file>.meta.yaml` next to a PDF/DOCX, used for batch ingestion."""
    sidecar = path.with_name(path.name + ".meta.yaml")
    if not sidecar.exists():
        return {}
    data = yaml.safe_load(sidecar.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


_SUGGEST_PATTERNS = {
    "effective_date": re.compile(
        r"\beffective\s+(?:from|as of|on|date[:\s])?\s*([A-Z][a-z]+\.? \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2}|\d{1,2} [A-Z][a-z]+ \d{4})"
    ),
    "publication_date": re.compile(
        r"\b(?:published|issued|dated)\s*(?:on|:)?\s*([A-Z][a-z]+\.? \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2}|\d{1,2} [A-Z][a-z]+ \d{4})"
    ),
    "version": re.compile(r"\b[Vv]ersion[:\s]+(\d+(?:\.\d+)*)"),
}


def suggest_metadata(text: str) -> dict[str, str]:
    """Regex-based hints for a human to confirm. These are never used for ranking."""
    out: dict[str, str] = {}
    head = text[:4000]
    for key, pattern in _SUGGEST_PATTERNS.items():
        m = pattern.search(head)
        if not m:
            continue
        raw = m.group(1)
        if key == "version":
            out[key] = raw
        elif (d := parse_date(raw)) is not None:
            out[key] = d.isoformat()
    return out
