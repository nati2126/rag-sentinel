"""Document families, version numbering and supersession lineage."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

from sqlmodel import Session, func, select

from rag_sentinel.db import Document

_VERSION_TOKENS = re.compile(
    r"([_\-\s.]+(v|ver|version|rev|revision)[_\-\s.]?\d+([._]\d+)*"
    r"|[_\-\s.]+(19|20)\d{2}([_\-.]\d{2}){0,2}"
    r"|[_\-\s.]+(draft|final|copy|old|new|updated))+$",
    re.IGNORECASE,
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def family_from_filename(filename: str) -> str:
    """'Leave_Policy_v2.pdf' -> 'leave-policy'. Used only when no explicit family is given."""
    stem = re.sub(r"[()\[\]{}]", " ", Path(filename).stem).strip()
    stem = _VERSION_TOKENS.sub("", stem) or stem
    slug = re.sub(r"[^a-z0-9]+", "-", stem.lower()).strip("-")
    return slug or "document"


def find_duplicate(s: Session, sha: str) -> Document | None:
    return s.exec(select(Document).where(Document.sha256 == sha, Document.is_deleted == False)).first()  # noqa: E712


def next_version_number(s: Session, family_id: str) -> int:
    current = s.exec(select(func.max(Document.version_number)).where(Document.family_id == family_id)).one()
    return (current or 0) + 1


def resolve_reference(s: Session, ref: str | None) -> Document | None:
    """Resolve a supersedes reference given as document id, filename or family id (latest version)."""
    if not ref:
        return None
    doc = s.get(Document, ref)
    if doc and not doc.is_deleted:
        return doc
    stmt = (
        select(Document)
        .where(Document.is_deleted == False)  # noqa: E712
        .where((Document.filename == ref) | (Document.family_id == ref))
        .order_by(Document.version_number.desc())
    )
    return s.exec(stmt).first()


def valid_from(doc: Document) -> date | None:
    return doc.effective_date or doc.publication_date


class Lineage:
    """Who-supersedes-whom over all active documents, combining explicit links and family versions.

    Explicit: B.supersedes_id == A.id.
    Implicit: same family, B is a later *approved* version with a later (or equal, higher version number)
    start date. A draft or pending revision never implicitly supersedes the approved one.
    """

    def __init__(self, docs: list[Document]):
        self.docs = {d.id: d for d in docs}
        self.successors: dict[str, list[tuple[str, str]]] = {d.id: [] for d in docs}
        for d in docs:
            if d.supersedes_id and d.supersedes_id in self.docs:
                self.successors[d.supersedes_id].append((d.id, "explicit"))
        by_family: dict[str, list[Document]] = {}
        for d in docs:
            by_family.setdefault(d.family_id, []).append(d)
        for members in by_family.values():
            for a in members:
                for b in members:
                    if a.id == b.id or b.approval_status != "approved" or b.version_number <= a.version_number:
                        continue
                    va, vb = valid_from(a), valid_from(b)
                    if va and vb and vb < va:
                        continue
                    if (b.id, "explicit") not in self.successors[a.id]:
                        self.successors[a.id].append((b.id, "family"))
        # union-find for "same lineage" (family + explicit links)
        self._parent = {d.id: d.id for d in docs}
        for members in by_family.values():
            for m in members[1:]:
                self._union(members[0].id, m.id)
        for d in docs:
            if d.supersedes_id and d.supersedes_id in self.docs:
                self._union(d.id, d.supersedes_id)

    def _find(self, x: str) -> str:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def _union(self, a: str, b: str) -> None:
        self._parent[self._find(a)] = self._find(b)

    def same_lineage(self, a: str, b: str) -> bool:
        return a in self._parent and b in self._parent and self._find(a) == self._find(b)

    def lineage_members(self, doc_id: str) -> list[Document]:
        root = self._find(doc_id)
        return [d for i, d in self.docs.items() if self._find(i) == root]

    def superseded_at(self, doc_id: str, as_of: date) -> tuple[bool, str | None]:
        """Is the document superseded at `as_of`? Returns (flag, id of the superseding doc)."""
        for succ_id, _how in self.successors.get(doc_id, []):
            succ = self.docs[succ_id]
            if succ.approval_status != "approved":
                continue
            start = valid_from(succ)
            if start is None or start <= as_of:
                return True, succ_id
        return False, None

    def is_ancestor(self, older: str, newer: str) -> bool:
        """True if `newer` (transitively) supersedes `older`."""
        seen, stack = set(), [older]
        while stack:
            cur = stack.pop()
            for succ, _ in self.successors.get(cur, []):
                if succ == newer:
                    return True
                if succ not in seen:
                    seen.add(succ)
                    stack.append(succ)
        return False
