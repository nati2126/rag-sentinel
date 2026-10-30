"""Affected-document detection: when a document changes a value, find other documents still using the old one.

- confirmed: another active document (outside the lineage) has an extracted claim with the same canonical
  predicate and exactly the old value.
- possible: a chunk outside the lineage mentions the old value literally and shares vocabulary with the
  predicate, but no matching claim was extracted. These need human review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rag_sentinel.claims.canonical import humanize
from rag_sentinel.db import Chunk, Claim, Document
from rag_sentinel.ingest.versioning import Lineage
from rag_sentinel.retrieval.bm25 import tokenize


@dataclass
class ValueChange:
    predicate_key: str
    old_value: str
    new_value: str
    old_value_norm: str
    previous_doc_id: str


@dataclass
class AffectedReference:
    doc_id: str
    chunk_id: str
    predicate_key: str
    old_value: str
    quote: str
    confirmed: bool
    reason: str


@dataclass
class AffectedReport:
    doc_id: str
    changes: list[ValueChange] = field(default_factory=list)
    references: list[AffectedReference] = field(default_factory=list)


def _value_pattern(value: str) -> re.Pattern | None:
    nums = re.findall(r"\d+(?:\.\d+)?", value)
    if not nums:
        return None
    # "20 days" -> \b20\s*(?:-\s*)?day ; "$50" -> \$?\s*50\b
    unit = re.findall(r"[a-zA-Z]{3,}", value)
    if unit:
        return re.compile(rf"\b{re.escape(nums[0])}\s*-?\s*{re.escape(unit[0][:4].lower())}", re.I)
    return re.compile(rf"(?<![\d.]){re.escape(nums[0])}(?![\d.])")


def find_affected(
    doc_id: str,
    docs: dict[str, Document],
    claims: list[Claim],
    chunks: list[Chunk],
    lineage: Lineage,
) -> AffectedReport:
    report = AffectedReport(doc_id=doc_id)
    if doc_id not in docs:
        return report
    members = {m.id for m in lineage.lineage_members(doc_id)}
    previous = [m for m in members if m != doc_id and lineage.is_ancestor(m, doc_id)]
    new_claims = [c for c in claims if c.doc_id == doc_id]
    for nc in new_claims:
        for prev_id in previous:
            for oc in claims:
                if oc.doc_id == prev_id and oc.predicate_key == nc.predicate_key and oc.value_norm != nc.value_norm:
                    report.changes.append(ValueChange(nc.predicate_key, oc.value, nc.value, oc.value_norm, prev_id))
    seen_chunks: set[tuple[str, str]] = set()
    for ch in report.changes:
        for c in claims:
            if c.doc_id in members or c.doc_id not in docs:
                continue
            if c.predicate_key == ch.predicate_key and c.value_norm == ch.old_value_norm:
                seen_chunks.add((c.chunk_id, ch.predicate_key))
                report.references.append(
                    AffectedReference(
                        c.doc_id, c.chunk_id, ch.predicate_key, c.value, c.source_quote, True,
                        f"States the old value '{ch.old_value}' (now '{ch.new_value}').",
                    )
                )  # fmt: skip
        pattern = _value_pattern(ch.old_value)
        vocab = set(tokenize(humanize(ch.predicate_key))) - {"period", "length", "limit", "days", "number"}
        if pattern is None:
            continue
        for chunk in chunks:
            if chunk.doc_id in members or chunk.doc_id not in docs or (chunk.id, ch.predicate_key) in seen_chunks:
                continue
            m = pattern.search(chunk.text)
            if not m or not (vocab & set(tokenize(chunk.text))):
                continue
            start = max(0, m.start() - 120)
            quote = re.sub(r"\s+", " ", chunk.text[start : m.end() + 120]).strip()
            seen_chunks.add((chunk.id, ch.predicate_key))
            report.references.append(
                AffectedReference(
                    chunk.doc_id, chunk.id, ch.predicate_key, ch.old_value, quote, False,
                    f"Mentions '{ch.old_value}' near '{humanize(ch.predicate_key)}' terms; no matching claim. Review.",
                )
            )  # fmt: skip
    return report
