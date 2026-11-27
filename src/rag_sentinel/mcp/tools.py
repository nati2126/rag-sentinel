"""Read-only RAG Sentinel operations shaped for tool use (MCP server, agents).

Every function returns plain JSON-serialisable data, trimmed so that a small model's context is not flooded:
passages are cut to `TEXT_CHARS` characters and lists are capped. Nothing here writes to the knowledge base.
The verification logic is the existing B4 pipeline; these functions only select and reshape its output.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from datetime import date
from typing import Any

from rag_sentinel.agent.graph import RANK_POOL, SentinelAgent
from rag_sentinel.claims.canonical import humanize
from rag_sentinel.claims.normalize import numbers_in
from rag_sentinel.conflicts.detect import ACTIONABLE
from rag_sentinel.db import Document
from rag_sentinel.kb import KnowledgeBase
from rag_sentinel.ranking import standing
from rag_sentinel.retrieval.bm25 import tokenize

TEXT_CHARS = 600
QUOTE_CHARS = 300
# share of the statement's words a sentence must contain to count as stating the statement's value
MATCH_OVERLAP = 0.5
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def _numeric_changes(changes: list) -> list:
    """Value changes where both values contain a number ("20 days" -> "25 days"). The change detector also
    pairs a number with every non-numeric statement on the same attribute; those pairs are left out."""
    return [c for c in changes if numbers_in(c.old_value) and numbers_in(c.new_value)]


class ToolInputError(ValueError):
    """A tool argument is invalid (unknown document, bad date...). The message is meant for the caller."""


def _iso(v: Any) -> Any:
    return v.isoformat() if isinstance(v, date) else v


def _trim(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


class SentinelTools:
    """The tool surface over one knowledge base. Calls are serialised: the embedded vector store is not
    safe for concurrent use, and the MCP server runs synchronous tools in worker threads."""

    def __init__(self, kb_factory: Callable[[], KnowledgeBase] | KnowledgeBase, pipeline: str = "B4"):
        self._factory = kb_factory if callable(kb_factory) else (lambda: kb_factory)
        self._kb: KnowledgeBase | None = None
        self._agent: SentinelAgent | None = None
        self._pipeline = pipeline
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ plumbing
    @property
    def kb(self) -> KnowledgeBase:
        with self._lock:
            if self._kb is None:
                self._kb = self._factory()  # loads embedder / reranker on first use, not at server start
            return self._kb

    @property
    def agent(self) -> SentinelAgent:
        with self._lock:
            if self._agent is None:
                self._agent = SentinelAgent(self.kb, self._pipeline)
            return self._agent

    def close(self) -> None:
        if self._kb is not None:
            self._kb.vectors.close()

    def _as_of(self, as_of: str | None) -> date:
        if not as_of:
            return self.kb.settings.reference_date()
        try:
            return date.fromisoformat(as_of)
        except ValueError as exc:
            raise ToolInputError(f"as_of must be a date in YYYY-MM-DD form, got {as_of!r}") from exc

    def _resolve(self, document: str) -> Document:
        """A document by id, exact filename, or a unique case-insensitive part of its filename or title."""
        docs = self.kb.list_documents()
        needle = document.strip()
        for d in docs:
            if needle in (d.id, d.filename):
                return d
        low = needle.lower()
        matches = [d for d in docs if low in d.filename.lower() or low in (d.title or "").lower()]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ToolInputError(f"No document matches {document!r}. Use list_documents to see the filenames.")
        names = ", ".join(sorted(d.filename for d in matches)[:10])
        raise ToolInputError(f"{document!r} matches several documents ({names}). Give the exact filename.")

    def _standing(self, d: Document, as_of: date, lineage=None) -> dict[str, Any]:
        lineage = lineage or self.kb.lineage()
        if d.id not in lineage.docs:
            return {"status": "deleted", "superseded_by": None}
        st = standing(d, as_of, lineage, self.kb.settings.ranking)
        by = lineage.docs[st.superseded_by].filename if st.superseded_by else None
        return {"status": st.status, "superseded_by": by}

    def _doc_row(self, d: Document, as_of: date, lineage) -> dict[str, Any]:
        st = self._standing(d, as_of, lineage)
        return {
            "doc_id": d.id, "filename": d.filename, "title": d.title, "family": d.family_id,
            "version": d.version_label, "effective_date": _iso(d.effective_date),
            "publication_date": _iso(d.publication_date), "authority_level": d.authority_level,
            "approval_status": d.approval_status, "standing": st["status"], "superseded_by": st["superseded_by"],
        }  # fmt: skip

    def _evidence(self, query: str, as_of: str | None, top_k: int) -> tuple[dict, list[dict]]:
        """Retrieval + temporal/authority ranking from the pipeline, without generation."""
        top_k = max(1, min(int(top_k), RANK_POOL))
        a = self.agent
        with self._lock:
            settings, a.settings = a.settings, a.settings.model_copy(update={"final_k": top_k})
            try:
                a._docs = self.kb.documents_map()
                state: dict[str, Any] = {"question": query, "as_of": _iso(self._as_of(as_of)), "trace": []}
                state |= a.analyze_query(state)
                state |= a.retrieve(state)
                state |= a.rank_evidence(state)
            finally:
                a.settings = settings
        return state["analysis"], state["evidence"]

    # ------------------------------------------------------------------ tools
    def search_documents(self, query: str, as_of: str | None = None, top_k: int = 5) -> dict[str, Any]:
        analysis, evidence = self._evidence(query, as_of, top_k)
        return {
            "as_of": analysis["as_of"],
            "mode": analysis["mode"],
            "results": [
                {"label": e["label"], "filename": e["filename"], "title": e["title"], "version": e["version"],
                 "standing": e["standing_status"], "effective_date": e["effective_date"],
                 "authority_level": e["authority_level"], "approval_status": e["approval_status"],
                 "relevance": e["relevance"], "page": e["page"], "text": _trim(e["text"], TEXT_CHARS)}
                for e in evidence
            ],
        }  # fmt: skip

    def ask_verified(self, question: str, as_of: str | None = None) -> dict[str, Any]:
        with self._lock:
            res = self.agent.ask(question, self._as_of(as_of) if as_of else None)
        return {
            "status": res["status"],
            "presented_as_reliable": res["presented_as_reliable"],
            "answer": res["answer"],
            "citations": [
                {"label": c["label"], "filename": c["filename"], "version": c["version"],
                 "standing": c["standing_status"], "effective_date": _iso(c["effective_date"]),
                 "quote": _trim(c["text"], QUOTE_CHARS)}
                for c in res["citations"]
            ],
            "reasons": res["reasons"],
            "warnings": res["warnings"][:6],
            "rules_fired": res["rules_fired"],
            "conflicts": [
                {"kind": c["kind"], "status": c["status"], "explanation": c["explanation"]}
                for c in res["conflicts"]
                if c["kind"] in ACTIONABLE and any(c["explanation"] in m for m in res["reasons"] + res["warnings"])
            ][:5],
            "as_of": res["analysis"]["as_of"],
            "mode": res["analysis"]["mode"],
            "latency_ms": res["latency_ms"],
        }  # fmt: skip

    def _conflict_flags(self, value: str, doc_ids: set[str]) -> dict[str, list[dict]]:
        """Contradiction / outdated findings (open or resolved) in which a document in `doc_ids` states
        `value` and is not the preferred side."""
        rows = [r for r in self.kb.conflicts() if r.kind in ACTIONABLE and r.status != "dismissed"]
        claims = self.kb.claims_by_id([r.claim_a_id for r in rows] + [r.claim_b_id for r in rows])
        names = {d.id: d.filename for d in self.kb.list_documents(True)}
        out: dict[str, list[dict]] = {}
        for r in rows:
            for mine, other, doc in (
                (r.claim_a_id, r.claim_b_id, r.doc_a_id),
                (r.claim_b_id, r.claim_a_id, r.doc_b_id),
            ):
                c, o = claims.get(mine), claims.get(other)
                if doc not in doc_ids or c is None or c.value_num is None or f"{c.value_num:g}" != value:
                    continue
                if r.preferred_doc_id == doc:
                    continue
                out.setdefault(doc, []).append({
                    "kind": r.kind, "attribute": humanize(r.predicate_key),
                    "preferred_document": names.get(r.preferred_doc_id) if r.preferred_doc_id else None,
                    "preferred_value": o.value if o else None,
                })  # fmt: skip
        return out

    def _old_value_flags(self, value: str, doc_ids: set[str], as_of: date) -> dict[str, list[dict]]:
        """Documents in `doc_ids` that still state `value` after a newer in-force version changed it."""
        lineage = self.kb.lineage()
        out: dict[str, list[dict]] = {}
        for d in lineage.docs.values():
            older = [m for m in lineage.lineage_members(d.id) if m.id != d.id and lineage.is_ancestor(m.id, d.id)]
            if not older or not standing(d, as_of, lineage, self.kb.settings.ranking).in_force:
                continue
            report = self.kb.affected_documents(d.id)
            new_values: dict[tuple[str, str], list[str]] = {}
            for c in _numeric_changes(report.changes):
                new_values.setdefault((c.predicate_key, c.old_value), []).append(c.new_value)
            for ref in report.references:
                if ref.doc_id in doc_ids and value in numbers_in(ref.old_value):
                    out.setdefault(ref.doc_id, []).append({
                        "kind": "value_changed_in_newer_version", "attribute": humanize(ref.predicate_key),
                        "preferred_document": d.filename,
                        "preferred_value": " / ".join(new_values.get((ref.predicate_key, ref.old_value), [])) or None,
                    })  # fmt: skip
        return out

    def _sources_stating(self, statement: str, value: str, evidence: list[dict]) -> list[dict]:
        """Evidence passages with a sentence that contains `value` and most of the statement's words."""
        words = {w for w in tokenize(statement) if not any(ch.isdigit() for ch in w)}
        out = []
        for e in evidence:
            for sentence in _SENTENCE.split(e["text"]):
                if value not in numbers_in(sentence):
                    continue
                if len(words & set(tokenize(sentence))) / max(1, len(words)) >= MATCH_OVERLAP:
                    out.append({"doc_id": e["doc_id"], "filename": e["filename"], "standing": e["standing_status"],
                                "sentence": _trim(sentence, QUOTE_CHARS)})  # fmt: skip
                    break
        return out

    def check_statement(self, statement: str, as_of: str | None = None) -> dict[str, Any]:
        """For each number in the statement: the retrieved sources whose sentence states it, their standing,
        and flags when a source is the outdated side of a detected conflict or still states a value that a
        newer in-force version changed. Findings per value:
          current   - stated by an in-force source with no outdated flag (and not only contested ones)
          disputed  - the in-force sources stating it are all in a contradiction with no preferred side
          outdated  - stated only by non-current sources or by flagged in-force sources
          not_found - no retrieved sentence states it
        The pipeline's verified answer is returned separately; the two are not merged."""
        when = self._as_of(as_of)
        analysis, evidence = self._evidence(statement, when.isoformat(), RANK_POOL)
        values = []
        for n in sorted(numbers_in(statement), key=float):
            sources = self._sources_stating(statement, n, evidence)
            ids = {s["doc_id"] for s in sources}
            flags = self._conflict_flags(n, ids)
            for doc, extra in self._old_value_flags(n, ids, when).items():
                flags.setdefault(doc, []).extend(extra)
            current, contested = [], []
            for s in sources:
                unique = {tuple(sorted(f.items())): f for f in flags.get(s["doc_id"], [])}
                s["flags"] = list(unique.values())[:4]
                if s["standing"] != "in_force" or any(f["preferred_document"] for f in s["flags"]):
                    continue
                (contested if s["flags"] else current).append(s["filename"])
            if current:
                finding = "current"
            elif contested:
                finding = "disputed"
            elif sources:
                finding = "outdated"
            else:
                finding = "not_found"
            values.append({"value": n, "finding": finding,
                           "sources": [{k: v for k, v in s.items() if k != "doc_id"} for s in sources]})  # fmt: skip
        verdict = self.ask_verified(
            f"Check this statement against the documents in force and give the correct value: {statement}",
            when.isoformat(),
        )
        return {"statement": statement, "as_of": analysis["as_of"], "values": values, "verified_answer": verdict}

    def list_documents(self, as_of: str | None = None, family: str | None = None) -> dict[str, Any]:
        when = self._as_of(as_of)
        lineage = self.kb.lineage()
        rows = [self._doc_row(d, when, lineage) for d in self.kb.list_documents()]
        if family:
            rows = [r for r in rows if family.lower() in (r["family"] or "").lower()]
        return {"as_of": when.isoformat(), "count": len(rows), "documents": rows}

    def get_document_versions(self, document: str, as_of: str | None = None) -> dict[str, Any]:
        when = self._as_of(as_of)
        doc = self._resolve(document)
        lineage = self.kb.lineage()
        names = {d.id: d.filename for d in self.kb.list_documents(True)}
        report = self.kb.affected_documents(doc.id)
        return {
            "document": doc.filename,
            "as_of": when.isoformat(),
            "versions": [self._doc_row(v, when, lineage) for v in self.kb.versions(doc.id)],
            "changes_from_previous_version": [
                {"attribute": humanize(c.predicate_key), "old_value": c.old_value, "new_value": c.new_value,
                 "previous_version": names.get(c.previous_doc_id)}
                for c in _numeric_changes(report.changes)
            ],
            "documents_still_using_old_values": [
                {"filename": names.get(r.doc_id), "attribute": humanize(r.predicate_key), "old_value": r.old_value,
                 "confirmed": r.confirmed, "quote": _trim(r.quote, QUOTE_CHARS)}
                for r in report.references
            ][:20],
        }  # fmt: skip

    def list_conflicts(
        self,
        kind: str | None = None,
        status: str | None = "open",
        document: str | None = None,
        actionable_only: bool = True,
        limit: int = 20,
    ) -> dict[str, Any]:
        rows = self.kb.conflicts(kind or None, status or None)
        if actionable_only and not kind:
            rows = [r for r in rows if r.kind in ACTIONABLE]
        if document:
            doc = self._resolve(document)
            rows = [r for r in rows if doc.id in (r.doc_a_id, r.doc_b_id)]
        claims = self.kb.claims_by_id([r.claim_a_id for r in rows] + [r.claim_b_id for r in rows])
        names = {d.id: d.filename for d in self.kb.list_documents(True)}
        limit = max(1, min(int(limit), 100))
        out = []
        for r in rows[:limit]:
            a, b = claims.get(r.claim_a_id), claims.get(r.claim_b_id)
            out.append({
                "id": r.id, "kind": r.kind, "status": r.status, "attribute": humanize(r.predicate_key),
                "document_a": names.get(r.doc_a_id), "value_a": a.value if a else None,
                "document_b": names.get(r.doc_b_id), "value_b": b.value if b else None,
                "preferred_document": names.get(r.preferred_doc_id) if r.preferred_doc_id else None,
                "explanation": r.explanation, "detected_by": r.detected_by,
            })  # fmt: skip
        return {"total": len(rows), "returned": len(out), "conflicts": out}
