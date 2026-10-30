"""KnowledgeBase: the service layer used by the API, the agent and the evaluation harness."""

from __future__ import annotations

import shutil
import threading
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlmodel import col, delete, select

from rag_sentinel.chunking import chunk_pages
from rag_sentinel.claims.canonical import canonicalize, make_llm_judge
from rag_sentinel.claims.extract import extract_claims
from rag_sentinel.config import Settings
from rag_sentinel.conflicts.affected import AffectedReport, find_affected
from rag_sentinel.conflicts.detect import ACTIONABLE, ConflictDetector, make_pair_judge
from rag_sentinel.db import Chunk, Claim, Conflict, Database, Document, DocumentEvent, utcnow
from rag_sentinel.ingest.extract import ExtractionError, detect_type, extract
from rag_sentinel.ingest.metadata import DocumentMetadata, load_sidecar, merge_metadata, suggest_metadata
from rag_sentinel.ingest.versioning import (
    Lineage,
    family_from_filename,
    find_duplicate,
    next_version_number,
    resolve_reference,
    sha256_bytes,
)
from rag_sentinel.llm import LLM, LLMError
from rag_sentinel.log import get_logger
from rag_sentinel.retrieval.bm25 import BM25Index
from rag_sentinel.retrieval.embedder import Embedder
from rag_sentinel.retrieval.reranker import Reranker
from rag_sentinel.retrieval.retriever import Retriever
from rag_sentinel.retrieval.vector_store import VectorStore

log = get_logger(__name__)

IMPORTANT_FIELDS = ("effective_date", "authority_level", "approval_status")


@dataclass
class IngestResult:
    status: str  # created | new_version | duplicate
    document: Document
    previous_version_id: str | None = None
    warnings: list[str] = field(default_factory=list)
    chunks: int = 0
    claims: int = 0
    claims_rejected: int = 0


class KnowledgeBase:
    def __init__(
        self,
        settings: Settings,
        embedder: Embedder,
        llm: LLM | None,
        reranker: Reranker | None,
        db: Database | None = None,
        vectors: VectorStore | None = None,
    ):
        self.settings = settings
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.db = db or Database(settings.db_path)
        self.vectors = vectors or VectorStore(settings.qdrant_path)
        self.embedder = embedder
        self.llm = llm
        self.reranker = reranker
        self._bm25: BM25Index | None = None
        self._lock = threading.RLock()
        self.retriever = Retriever(embedder, self.vectors, self.bm25, self.lookup_chunks, reranker, self.doc_titles)

    @classmethod
    def from_settings(cls, settings: Settings) -> KnowledgeBase:
        from rag_sentinel.llm import OllamaLLM
        from rag_sentinel.retrieval.embedder import OllamaEmbedder
        from rag_sentinel.retrieval.reranker import CrossEncoderReranker

        settings.apply_hf_env()
        embedder = OllamaEmbedder(
            settings.ollama_url, settings.embed_model, settings.embed_query_prefix, settings.embed_doc_prefix,
            settings.embed_batch,
        )  # fmt: skip
        llm = OllamaLLM(
            settings.ollama_url, settings.llm_model, settings.llm_num_ctx, settings.llm_temperature, settings.llm_timeout_s
        )
        reranker = CrossEncoderReranker(settings.reranker_model, settings.reranker_device) if settings.reranker_model else None
        return cls(settings, embedder, llm, reranker)

    # ------------------------------------------------------------------ ingestion
    def ingest_path(
        self,
        path: Path,
        user_metadata: dict[str, Any] | None = None,
        filename: str | None = None,
        use_sidecar: bool = True,
        analyze: bool = True,
    ) -> IngestResult:
        filename = filename or path.name
        detect_type(filename)
        data = path.read_bytes()
        sha = sha256_bytes(data)
        with self._lock:
            with self.db.session() as s:
                dup = find_duplicate(s, sha)
                if dup is not None:
                    s.add(DocumentEvent(doc_id=dup.id, family_id=dup.family_id, event="duplicate",
                                        detail=f"Upload of '{filename}' is identical to '{dup.filename}' (SHA-256 match)."))  # fmt: skip
                    s.commit()
                    return IngestResult("duplicate", dup, warnings=["Identical file already indexed; nothing changed."])

            extracted = extract(path, filename)
            layers = [
                ("file", extracted.file_metadata),
                ("front_matter", extracted.embedded_metadata),
                ("sidecar", load_sidecar(path) if use_sidecar else {}),
                ("user", user_metadata or {}),
            ]
            meta, sources = merge_metadata(layers)
            family = meta.family or family_from_filename(filename)
            sources.setdefault("family", "filename")
            warnings = list(extracted.warnings)
            warnings += [f"{f} unknown (not in file or provided metadata)" for f in IMPORTANT_FIELDS if getattr(meta, f) is None]

            with self.db.session() as s:
                previous = s.exec(
                    select(Document).where(Document.family_id == family, Document.is_deleted == False)  # noqa: E712
                    .order_by(col(Document.version_number).desc())
                ).first()
                version_number = next_version_number(s, family)
                doc_id = sha[:16] if s.get(Document, sha[:16]) is None else f"{sha[:16]}-{version_number}"
                self.settings.files_dir.mkdir(parents=True, exist_ok=True)
                stored = self.settings.files_dir / f"{sha}{Path(filename).suffix.lower()}"
                if not stored.exists():
                    shutil.copyfile(path, stored)
                sup = resolve_reference(s, meta.supersedes)
                if meta.supersedes and sup is None:
                    warnings.append(f"supersedes '{meta.supersedes}' not found yet; will resolve when it is ingested")
                doc = Document(
                    id=doc_id,
                    family_id=family,
                    filename=filename,
                    title=meta.title or _guess_title(extracted.text, filename),
                    content_type=extracted.content_type,
                    sha256=sha,
                    version_label=meta.version,
                    version_number=version_number,
                    created_date=meta.created_date,
                    publication_date=meta.publication_date,
                    effective_date=meta.effective_date,
                    last_modified=meta.last_modified,
                    source_org=meta.source_org,
                    authority_level=meta.authority_level,
                    approval_status=meta.approval_status or "unknown",
                    supersedes_ref=meta.supersedes,
                    supersedes_id=sup.id if sup else None,
                    stored_path=str(stored),
                    page_count=len(extracted.pages) if extracted.content_type == "pdf" else None,
                    char_count=len(extracted.text),
                    metadata_sources=sources,
                    suggested_metadata=suggest_metadata(extracted.text),
                    extraction_warnings=warnings,
                )
                s.add(doc)
                status = "new_version" if previous else "created"
                detail = (
                    f"Version {version_number} of family '{family}' (previous: {previous.filename})"
                    if previous else f"New family '{family}'"
                )  # fmt: skip
                s.add(DocumentEvent(doc_id=doc_id, family_id=family, event="ingested", detail=detail))
                if previous:
                    s.add(DocumentEvent(doc_id=previous.id, family_id=family, event="new_version",
                                        detail=f"New version uploaded: {filename} (v{version_number})"))  # fmt: skip
                if sup:
                    s.add(DocumentEvent(doc_id=sup.id, family_id=sup.family_id, event="superseded",
                                        detail=f"Superseded by {filename}"))  # fmt: skip
                s.commit()

            n_chunks, n_claims, n_rej, idx_warn = self.index_document(doc_id)
            if idx_warn:
                self._add_warnings(doc_id, idx_warn)
                warnings += idx_warn
            if analyze:
                self.refresh_analysis()
            log.info("ingested", extra={"doc": filename, "status": status, "chunks": n_chunks, "claims": n_claims})
            return IngestResult(status, self.get_document(doc_id), previous.id if previous else None, warnings,
                                n_chunks, n_claims, n_rej)  # fmt: skip

    def ingest_directory(self, folder: Path, analyze: bool = True) -> list[IngestResult]:
        results = []
        files = sorted(p for p in folder.rglob("*") if p.is_file() and not p.name.endswith(".meta.yaml"))
        for p in files:
            try:
                detect_type(p.name)
            except ExtractionError:
                continue
            results.append(self.ingest_path(p, analyze=False))
        if analyze:
            self.refresh_analysis()
        return results

    def index_document(self, doc_id: str, extract_claims_: bool = True) -> tuple[int, int, int, list[str]]:
        """(Re)build chunks, vectors and claims for one document. Returns (chunks, claims, rejected, warnings)."""
        warnings: list[str] = []
        with self._lock:
            doc = self.get_document(doc_id)
            extracted = extract(Path(doc.stored_path), doc.filename)
            spans = chunk_pages(extracted.pages, doc.sha256, self.settings.chunk_size, self.settings.chunk_overlap)
            with self.db.session() as s:
                s.exec(delete(Claim).where(Claim.doc_id == doc_id))
                s.exec(delete(Chunk).where(Chunk.doc_id == doc_id))
                for sp in spans:
                    s.add(Chunk(id=sp.id, doc_id=doc_id, seq=sp.seq, page=sp.page, start_char=sp.start_char,
                                end_char=sp.end_char, text=sp.text))  # fmt: skip
                s.commit()
            self.vectors.delete_document(doc_id)
            if spans:
                vecs = self.embedder.embed_documents([f"{doc.title}\n{sp.text}" for sp in spans])
                self.vectors.upsert([sp.id for sp in spans], [doc_id] * len(spans), vecs)
            self._bm25 = None

            n_claims = n_rej = 0
            if extract_claims_ and self.llm is not None:
                for sp in spans:
                    try:
                        rep = extract_claims(self.llm, sp.id, doc_id, doc.title or doc.filename, sp.text,
                                             self.db.cache_get, self.db.cache_set)  # fmt: skip
                    except LLMError as exc:
                        warnings.append(f"claim extraction failed for chunk {sp.seq}: {exc}")
                        continue
                    n_rej += len(rep.rejected)
                    with self.db.session() as s:
                        for c in rep.accepted:
                            s.merge(c)
                        s.commit()
                    n_claims += len(rep.accepted)
            elif self.llm is None:
                warnings.append("no LLM configured: claims not extracted")
        return len(spans), n_claims, n_rej, warnings

    def _add_warnings(self, doc_id: str, warnings: list[str]) -> None:
        with self.db.session() as s:
            doc = s.get(Document, doc_id)
            doc.extraction_warnings = list(doc.extraction_warnings or []) + warnings
            s.add(doc)
            s.commit()

    # ------------------------------------------------------------------ analysis
    def refresh_analysis(self) -> dict[str, int]:
        """Resolve pending supersessions, canonicalize predicates, and re-detect conflicts corpus-wide."""
        with self._lock:
            self._resolve_pending_supersedes()
            with self.db.session() as s:
                docs = {d.id: d for d in self.db.active_documents(s)}
                claims = list(s.exec(select(Claim).where(col(Claim.doc_id).in_(list(docs)))).all())
            judge_llm = self.llm if (self.llm is not None and self.settings.use_llm_conflict_judge) else None
            examples = {}
            for c in claims:
                examples.setdefault(c.predicate, c.source_quote)
            mapping = canonicalize(
                [c.predicate for c in claims], examples, self.embedder.embed_labels, self.settings.predicate_similarity,
                make_llm_judge(judge_llm, self.db.cache_get, self.db.cache_set) if judge_llm else None,
            )  # fmt: skip
            with self.db.session() as s:
                for c in claims:
                    key = mapping.get(c.predicate, c.predicate)
                    if c.predicate_key != key:
                        c.predicate_key = key
                        s.add(c)
                s.commit()
            lineage = Lineage(list(docs.values()))
            detector = ConflictDetector(
                docs, claims, lineage, self.settings.reference_date(), self.settings.ranking,
                self.settings.authority_margin,
                make_pair_judge(judge_llm, docs, self.db.cache_get, self.db.cache_set) if judge_llm else None,
            )  # fmt: skip
            findings = detector.detect()
            with self.db.session() as s:
                existing = {c.id: c for c in s.exec(select(Conflict)).all()}
                keep = set()
                for f in findings:
                    keep.add(f.id)
                    row = existing.get(f.id) or Conflict(id=f.id, predicate_key=f.predicate_key, claim_a_id=f.claim_a.id,
                                                         claim_b_id=f.claim_b.id, doc_a_id=f.claim_a.doc_id,
                                                         doc_b_id=f.claim_b.doc_id, kind=f.kind)  # fmt: skip
                    row.predicate_key, row.kind, row.confirmed = f.predicate_key, f.kind, f.confirmed
                    row.margin, row.explanation, row.detected_by = f.margin, f.explanation, f.detected_by
                    if row.status == "open":
                        row.preferred_doc_id = f.preferred_doc_id
                    s.add(row)
                for cid, row in existing.items():
                    if cid not in keep:
                        s.delete(row)
                s.commit()
            counts = Counter(f.kind for f in findings)
            log.info("analysis refreshed", extra={"claims": len(claims), "keys": len(set(mapping.values())), **counts})
            return dict(counts)

    def _resolve_pending_supersedes(self) -> None:
        with self.db.session() as s:
            pending = s.exec(
                select(Document).where(Document.supersedes_ref != None, Document.supersedes_id == None,  # noqa: E711
                                       Document.is_deleted == False)  # noqa: E712
            ).all()  # fmt: skip
            for d in pending:
                target = resolve_reference(s, d.supersedes_ref)
                if target and target.id != d.id:
                    d.supersedes_id = target.id
                    s.add(d)
                    s.add(DocumentEvent(doc_id=target.id, family_id=target.family_id, event="superseded",
                                        detail=f"Superseded by {d.filename}"))  # fmt: skip
            s.commit()

    # ------------------------------------------------------------------ management
    def update_metadata(self, doc_id: str, fields: dict[str, Any]) -> Document:
        clean = DocumentMetadata.model_validate(fields).model_dump(exclude_none=True)
        mapping = {"version": "version_label", "family": "family_id", "supersedes": "supersedes_ref"}
        with self._lock, self.db.session() as s:
            doc = s.get(Document, doc_id)
            if doc is None:
                raise KeyError(doc_id)
            for k, v in clean.items():
                setattr(doc, mapping.get(k, k), v)
                doc.metadata_sources = {**doc.metadata_sources, k: "user"}
            if "supersedes" in clean:
                target = resolve_reference(s, clean["supersedes"])
                doc.supersedes_id = target.id if target else None
            s.add(doc)
            s.add(DocumentEvent(doc_id=doc_id, family_id=doc.family_id, event="metadata_updated",
                                detail=", ".join(f"{k}={v}" for k, v in clean.items())))  # fmt: skip
            s.commit()
        self.refresh_analysis()
        return self.get_document(doc_id)

    def mark_superseded(self, old_id: str, new_id: str) -> Document:
        with self._lock, self.db.session() as s:
            old, new = s.get(Document, old_id), s.get(Document, new_id)
            if old is None or new is None:
                raise KeyError(old_id if old is None else new_id)
            if old_id == new_id:
                raise ValueError("A document cannot supersede itself")
            new.supersedes_id, new.supersedes_ref = old_id, old.filename
            new.metadata_sources = {**new.metadata_sources, "supersedes": "user"}
            s.add(new)
            s.add(DocumentEvent(doc_id=old_id, family_id=old.family_id, event="superseded",
                                detail=f"Marked as superseded by {new.filename}"))  # fmt: skip
            s.commit()
        self.refresh_analysis()
        return self.get_document(old_id)

    def delete_document(self, doc_id: str) -> None:
        """Soft delete: the version row and history are kept; chunks, vectors and claims are removed."""
        with self._lock:
            with self.db.session() as s:
                doc = s.get(Document, doc_id)
                if doc is None:
                    raise KeyError(doc_id)
                doc.is_deleted = True
                s.add(doc)
                s.exec(delete(Claim).where(Claim.doc_id == doc_id))
                s.exec(delete(Chunk).where(Chunk.doc_id == doc_id))
                s.add(DocumentEvent(doc_id=doc_id, family_id=doc.family_id, event="deleted", detail=doc.filename))
                s.commit()
            self.vectors.delete_document(doc_id)
            self._bm25 = None
            self.refresh_analysis()

    def reindex_document(self, doc_id: str) -> tuple[int, int, int, list[str]]:
        res = self.index_document(doc_id)
        doc = self.get_document(doc_id)
        with self.db.session() as s:
            s.add(DocumentEvent(doc_id=doc_id, family_id=doc.family_id, event="reindexed",
                                detail=f"{res[0]} chunks, {res[1]} claims"))  # fmt: skip
            s.commit()
        self.refresh_analysis()
        return res

    def reindex_all(self, reset_vectors: bool = False) -> int:
        with self._lock:
            if reset_vectors:
                self.vectors.reset()
            with self.db.session() as s:
                ids = [d.id for d in self.db.active_documents(s)]
            for i in ids:
                self.index_document(i)
            self.refresh_analysis()
            return len(ids)

    def resolve_conflict(self, conflict_id: str, status: str, preferred_doc_id: str | None, note: str | None) -> Conflict:
        if status not in ("open", "resolved", "dismissed"):
            raise ValueError("status must be open, resolved or dismissed")
        with self.db.session() as s:
            row = s.get(Conflict, conflict_id)
            if row is None:
                raise KeyError(conflict_id)
            if preferred_doc_id and preferred_doc_id not in (row.doc_a_id, row.doc_b_id):
                raise ValueError("preferred_doc_id must be one of the two conflicting documents")
            row.status, row.resolution_note = status, note
            row.preferred_doc_id = preferred_doc_id or row.preferred_doc_id
            row.resolved_at = utcnow() if status != "open" else None
            s.add(row)
            s.commit()
            return row

    # ------------------------------------------------------------------ reads
    def get_document(self, doc_id: str) -> Document:
        with self.db.session() as s:
            doc = s.get(Document, doc_id)
            if doc is None:
                raise KeyError(doc_id)
            return doc

    def list_documents(self, include_deleted: bool = False) -> list[Document]:
        with self.db.session() as s:
            stmt = select(Document).order_by(Document.family_id, Document.version_number)
            if not include_deleted:
                stmt = stmt.where(Document.is_deleted == False)  # noqa: E712
            return list(s.exec(stmt).all())

    def documents_map(self) -> dict[str, Document]:
        with self.db.session() as s:
            return {d.id: d for d in self.db.active_documents(s)}

    def versions(self, doc_id: str) -> list[Document]:
        doc = self.get_document(doc_id)
        with self.db.session() as s:
            fam = list(s.exec(select(Document).where(Document.family_id == doc.family_id)
                              .order_by(Document.version_number)).all())  # fmt: skip
        lineage = Lineage([d for d in self.documents_map().values()])
        linked = {m.id for m in lineage.lineage_members(doc_id)} if doc_id in lineage.docs else set()
        extra = [d for d in self.documents_map().values() if d.id in linked and d.family_id != doc.family_id]
        return fam + extra

    def history(self, doc_id: str | None = None, limit: int = 50) -> list[DocumentEvent]:
        with self.db.session() as s:
            stmt = select(DocumentEvent).order_by(col(DocumentEvent.id).desc()).limit(limit)
            if doc_id:
                doc = s.get(Document, doc_id)
                stmt = stmt.where(DocumentEvent.family_id == doc.family_id) if doc else stmt
            return list(s.exec(stmt).all())

    def chunks_for(self, doc_id: str) -> list[Chunk]:
        with self.db.session() as s:
            return list(s.exec(select(Chunk).where(Chunk.doc_id == doc_id).order_by(Chunk.seq)).all())

    def claims(self, doc_id: str | None = None) -> list[Claim]:
        with self.db.session() as s:
            stmt = select(Claim)
            if doc_id:
                stmt = stmt.where(Claim.doc_id == doc_id)
            return list(s.exec(stmt).all())

    def claims_for_chunks(self, chunk_ids: list[str]) -> list[Claim]:
        with self.db.session() as s:
            return list(s.exec(select(Claim).where(col(Claim.chunk_id).in_(chunk_ids))).all())

    def conflicts(self, kind: str | None = None, status: str | None = None, keys: set[str] | None = None) -> list[Conflict]:
        with self.db.session() as s:
            stmt = select(Conflict)
            if kind:
                stmt = stmt.where(Conflict.kind == kind)
            if status:
                stmt = stmt.where(Conflict.status == status)
            if keys is not None:
                stmt = stmt.where(col(Conflict.predicate_key).in_(list(keys)))
            return list(s.exec(stmt).all())

    def claims_by_id(self, ids: list[str]) -> dict[str, Claim]:
        with self.db.session() as s:
            return {c.id: c for c in s.exec(select(Claim).where(col(Claim.id).in_(ids))).all()}

    def lineage(self) -> Lineage:
        return Lineage(list(self.documents_map().values()))

    def affected_documents(self, doc_id: str) -> AffectedReport:
        docs = self.documents_map()
        with self.db.session() as s:
            chunks = list(s.exec(select(Chunk).where(col(Chunk.doc_id).in_(list(docs)))).all())
        return find_affected(doc_id, docs, self.claims(), chunks, Lineage(list(docs.values())))

    def bm25(self) -> BM25Index:
        if self._bm25 is None:
            with self.db.session() as s:
                active = {d.id: d.title or "" for d in self.db.active_documents(s)}
                rows = s.exec(select(Chunk).where(col(Chunk.doc_id).in_(list(active)))).all()
                self._bm25 = BM25Index([(c.id, f"{active[c.doc_id]}\n{c.text}") for c in rows])
        return self._bm25

    def lookup_chunks(self, ids: list[str]) -> dict[str, tuple[str, str, int | None]]:
        if not ids:
            return {}
        with self.db.session() as s:
            rows = s.exec(select(Chunk).where(col(Chunk.id).in_(ids))).all()
            return {c.id: (c.doc_id, c.text, c.page) for c in rows}

    def doc_titles(self) -> dict[str, str]:
        return {d.id: d.title or d.filename for d in self.documents_map().values()}

    def stats(self) -> dict[str, Any]:
        with self.db.session() as s:
            all_docs = list(s.exec(select(Document)).all())
            active = [d for d in all_docs if not d.is_deleted]
            n_chunks = len(s.exec(select(Chunk.id)).all())
            n_claims = len(s.exec(select(Claim.id)).all())
            conflicts = list(s.exec(select(Conflict)).all())
        lineage = Lineage(active)
        as_of = self.settings.reference_date()
        superseded = sum(1 for d in active if lineage.superseded_at(d.id, as_of)[0])
        open_actionable = [c for c in conflicts if c.kind in ACTIONABLE and c.status == "open"]
        docs_with_issues = {c.doc_a_id for c in open_actionable} | {c.doc_b_id for c in open_actionable}
        completeness = {
            f: round(sum(1 for d in active if getattr(d, f) not in (None, "unknown")) / len(active), 3) if active else 0.0
            for f in IMPORTANT_FIELDS
        }
        return {
            "as_of": as_of.isoformat(),
            "documents": len(active),
            "document_versions": len(all_docs),
            "families": len({d.family_id for d in active}),
            "deleted": len(all_docs) - len(active),
            "superseded": superseded,
            "chunks": n_chunks,
            "claims": n_claims,
            "vectors": self.vectors.count(),
            "conflicts_by_kind": dict(Counter(c.kind for c in conflicts)),
            "open_contradictions": sum(1 for c in open_actionable if c.kind == "contradiction"),
            "outdated_references": sum(1 for c in conflicts if c.kind == "outdated" and c.status == "open"),
            "unresolved_contradictions": sum(1 for c in open_actionable if c.kind == "contradiction" and not c.preferred_doc_id),
            "documents_with_open_issues": len(docs_with_issues),
            "health_score": round(1 - len(docs_with_issues) / len(active), 3) if active else 1.0,
            "metadata_completeness": completeness,
        }


def _guess_title(text: str, filename: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if 3 <= len(line) <= 120:
            return line
    return Path(filename).stem


def as_dict(obj: Any) -> dict[str, Any]:
    d = obj.model_dump() if hasattr(obj, "model_dump") else dict(obj.__dict__)
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in d.items()}
