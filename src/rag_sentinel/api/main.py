"""FastAPI backend. Run: uvicorn rag_sentinel.api.main:app --port 8000  (docs at /docs)."""

from __future__ import annotations

import json
import shutil
import tempfile
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlmodel import col, select

from rag_sentinel import __doc__ as pkg_doc
from rag_sentinel.agent.graph import SentinelAgent
from rag_sentinel.config import get_settings
from rag_sentinel.conflicts.detect import ACTIONABLE
from rag_sentinel.db import QueryRun
from rag_sentinel.ingest.extract import ExtractionError
from rag_sentinel.kb import KnowledgeBase, as_dict
from rag_sentinel.llm import LLMError
from rag_sentinel.log import get_logger, setup_logging
from rag_sentinel.pipelines import PIPELINES

log = get_logger(__name__)


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    pipeline: str = "B4"
    as_of: date | None = None


class SupersedeRequest(BaseModel):
    superseded_by: str


class ResolveRequest(BaseModel):
    status: str = Field(pattern="^(open|resolved|dismissed)$")
    preferred_doc_id: str | None = None
    note: str | None = Field(default=None, max_length=1000)


class MetadataPatch(BaseModel):
    title: str | None = None
    family: str | None = None
    version: str | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    source_org: str | None = None
    authority_level: int | None = Field(default=None, ge=1, le=5)
    approval_status: str | None = None
    supersedes: str | None = None


def create_app(kb: KnowledgeBase | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings = get_settings()
        setup_logging(settings.log_level)
        app.state.kb = kb or KnowledgeBase.from_settings(settings)
        app.state.agents = {}
        log.info("api started", extra={"data_dir": str(app.state.kb.settings.data_dir)})
        yield
        app.state.kb.vectors.close()

    app = FastAPI(title="RAG Sentinel API", version="0.2.0", description=pkg_doc, lifespan=lifespan)

    def get_kb(request: Request) -> KnowledgeBase:
        return request.app.state.kb

    def agent_for(request: Request, name: str) -> SentinelAgent:
        if name not in PIPELINES:
            raise HTTPException(400, f"Unknown pipeline '{name}'. Options: {', '.join(PIPELINES)}")
        agents = request.app.state.agents
        if name not in agents:
            agents[name] = SentinelAgent(request.app.state.kb, name)
        return agents[name]

    def _404(exc: KeyError) -> HTTPException:
        return HTTPException(404, f"Not found: {exc.args[0]}")

    # ----------------------------------------------------------------- health
    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/health", tags=["system"])
    def health(k: KnowledgeBase = Depends(get_kb)) -> dict[str, Any]:
        llm_ok = bool(k.llm and hasattr(k.llm, "ping") and k.llm.ping())
        return {"status": "ok", "llm": getattr(k.llm, "name", None), "llm_available": llm_ok,
                "embedder": k.embedder.name, "reranker": getattr(k.reranker, "name", None),
                "as_of": k.settings.reference_date().isoformat()}  # fmt: skip

    @app.get("/pipelines", tags=["system"])
    def pipelines() -> list[dict]:
        return [p.to_dict() for p in PIPELINES.values()]

    # ----------------------------------------------------------------- documents
    @app.post("/documents", tags=["documents"])
    def upload(
        file: UploadFile = File(...),
        title: str | None = Form(None),
        family: str | None = Form(None),
        version: str | None = Form(None),
        publication_date: str | None = Form(None),
        effective_date: str | None = Form(None),
        source_org: str | None = Form(None),
        authority_level: int | None = Form(None),
        approval_status: str | None = Form(None),
        supersedes: str | None = Form(None),
        k: KnowledgeBase = Depends(get_kb),
    ) -> dict[str, Any]:
        meta = {key: v for key, v in {
            "title": title, "family": family, "version": version, "publication_date": publication_date,
            "effective_date": effective_date, "source_org": source_org, "authority_level": authority_level,
            "approval_status": approval_status, "supersedes": supersedes,
        }.items() if v not in (None, "")}  # fmt: skip
        name = Path(file.filename or "upload").name
        with tempfile.TemporaryDirectory(dir=k.settings.data_dir) as tmp:
            tmp_path = Path(tmp) / name
            with tmp_path.open("wb") as fh:
                shutil.copyfileobj(file.file, fh)
            try:
                res = k.ingest_path(tmp_path, meta, filename=name, use_sidecar=False)
            except ExtractionError as exc:
                raise HTTPException(422, str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
            except LLMError as exc:
                raise HTTPException(503, f"Model server unavailable: {exc}") from exc
        return {"status": res.status, "document": as_dict(res.document), "previous_version_id": res.previous_version_id,
                "warnings": res.warnings, "chunks": res.chunks, "claims": res.claims,
                "claims_rejected": res.claims_rejected}  # fmt: skip

    @app.get("/documents", tags=["documents"])
    def list_documents(include_deleted: bool = False, k: KnowledgeBase = Depends(get_kb)) -> list[dict]:
        lineage = k.lineage()
        as_of = k.settings.reference_date()
        out = []
        for d in k.list_documents(include_deleted):
            row = as_dict(d)
            row["superseded"] = (
                (not d.is_deleted) and lineage.superseded_at(d.id, as_of)[0] if d.id in lineage.docs else False
            )
            out.append(row)
        return out

    @app.get("/documents/{doc_id}", tags=["documents"])
    def get_document(doc_id: str, k: KnowledgeBase = Depends(get_kb)) -> dict:
        try:
            d = k.get_document(doc_id)
        except KeyError as exc:
            raise _404(exc) from exc
        return {**as_dict(d), "chunks": len(k.chunks_for(doc_id)), "claims": len(k.claims(doc_id))}

    @app.get("/documents/{doc_id}/versions", tags=["documents"])
    def versions(doc_id: str, k: KnowledgeBase = Depends(get_kb)) -> list[dict]:
        try:
            return [as_dict(d) for d in k.versions(doc_id)]
        except KeyError as exc:
            raise _404(exc) from exc

    @app.get("/documents/{doc_id}/history", tags=["documents"])
    def doc_history(doc_id: str, k: KnowledgeBase = Depends(get_kb)) -> list[dict]:
        return [as_dict(e) for e in k.history(doc_id)]

    @app.get("/documents/{doc_id}/chunks", tags=["documents"])
    def doc_chunks(doc_id: str, k: KnowledgeBase = Depends(get_kb)) -> list[dict]:
        return [as_dict(c) for c in k.chunks_for(doc_id)]

    @app.get("/documents/{doc_id}/claims", tags=["documents"])
    def doc_claims(doc_id: str, k: KnowledgeBase = Depends(get_kb)) -> list[dict]:
        return [as_dict(c) for c in k.claims(doc_id)]

    @app.get("/documents/{doc_id}/affected", tags=["documents"])
    def affected(doc_id: str, k: KnowledgeBase = Depends(get_kb)) -> dict:
        rep = k.affected_documents(doc_id)
        names = {d.id: d.filename for d in k.list_documents(True)}
        return {
            "doc_id": rep.doc_id,
            "changes": [vars(c) | {"previous_filename": names.get(c.previous_doc_id)} for c in rep.changes],
            "references": [vars(r) | {"filename": names.get(r.doc_id)} for r in rep.references],
        }

    @app.patch("/documents/{doc_id}/metadata", tags=["documents"])
    def patch_metadata(doc_id: str, body: MetadataPatch, k: KnowledgeBase = Depends(get_kb)) -> dict:
        try:
            return as_dict(k.update_metadata(doc_id, body.model_dump(exclude_none=True)))
        except KeyError as exc:
            raise _404(exc) from exc

    @app.post("/documents/{doc_id}/supersede", tags=["documents"])
    def supersede(doc_id: str, body: SupersedeRequest, k: KnowledgeBase = Depends(get_kb)) -> dict:
        try:
            return as_dict(k.mark_superseded(doc_id, body.superseded_by))
        except KeyError as exc:
            raise _404(exc) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/documents/{doc_id}/reindex", tags=["documents"])
    def reindex(doc_id: str, k: KnowledgeBase = Depends(get_kb)) -> dict:
        try:
            n_chunks, n_claims, n_rej, warnings = k.reindex_document(doc_id)
        except KeyError as exc:
            raise _404(exc) from exc
        return {"chunks": n_chunks, "claims": n_claims, "claims_rejected": n_rej, "warnings": warnings}

    @app.delete("/documents/{doc_id}", tags=["documents"])
    def delete_document(doc_id: str, k: KnowledgeBase = Depends(get_kb)) -> dict:
        try:
            k.delete_document(doc_id)
        except KeyError as exc:
            raise _404(exc) from exc
        return {"deleted": doc_id}

    @app.post("/reindex", tags=["documents"])
    def reindex_all(reset_vectors: bool = False, k: KnowledgeBase = Depends(get_kb)) -> dict:
        return {"documents": k.reindex_all(reset_vectors)}

    # ----------------------------------------------------------------- ask
    @app.post("/ask", tags=["ask"])
    def ask(body: AskRequest, request: Request) -> dict:
        agent = agent_for(request, body.pipeline)
        try:
            result = agent.ask(body.question, body.as_of)
        except LLMError as exc:
            raise HTTPException(503, f"Model server unavailable: {exc}") from exc
        k: KnowledgeBase = request.app.state.kb
        with k.db.session() as s:
            s.add(QueryRun(question=body.question, pipeline=body.pipeline, status=result["status"],
                           answer=result["answer"], latency_ms=result["latency_ms"],
                           result=json.loads(json.dumps(result, default=str))))  # fmt: skip
            s.commit()
        return result

    @app.get("/queries", tags=["ask"])
    def queries(limit: int = 20, status: str | None = None, k: KnowledgeBase = Depends(get_kb)) -> list[dict]:
        with k.db.session() as s:
            stmt = select(QueryRun).order_by(col(QueryRun.id).desc()).limit(limit)
            if status:
                stmt = stmt.where(QueryRun.status == status)
            return [{"id": q.id, "question": q.question, "pipeline": q.pipeline, "status": q.status,
                     "answer": q.answer, "latency_ms": q.latency_ms, "created_at": q.created_at}
                    for q in s.exec(stmt).all()]  # fmt: skip

    # ----------------------------------------------------------------- conflicts
    @app.get("/conflicts", tags=["conflicts"])
    def conflicts(
        kind: str | None = None,
        status: str | None = None,
        actionable_only: bool = Query(False, description="only contradiction / outdated"),
        k: KnowledgeBase = Depends(get_kb),
    ) -> list[dict]:
        rows = k.conflicts(kind, status)
        if actionable_only:
            rows = [r for r in rows if r.kind in ACTIONABLE]
        claims = k.claims_by_id([r.claim_a_id for r in rows] + [r.claim_b_id for r in rows])
        docs = {d.id: d for d in k.list_documents(True)}
        out = []
        for r in rows:
            row = as_dict(r)
            for side in ("a", "b"):
                c, d = claims.get(getattr(r, f"claim_{side}_id")), docs.get(getattr(r, f"doc_{side}_id"))
                row[f"claim_{side}"] = as_dict(c) if c else None
                row[f"doc_{side}"] = {"id": d.id, "filename": d.filename, "title": d.title, "version": d.version_label,
                                      "effective_date": d.effective_date, "authority_level": d.authority_level,
                                      "approval_status": d.approval_status} if d else None  # fmt: skip
            out.append(row)
        return out

    @app.post("/conflicts/{conflict_id}/resolve", tags=["conflicts"])
    def resolve(conflict_id: str, body: ResolveRequest, k: KnowledgeBase = Depends(get_kb)) -> dict:
        try:
            return as_dict(k.resolve_conflict(conflict_id, body.status, body.preferred_doc_id, body.note))
        except KeyError as exc:
            raise _404(exc) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/analysis/refresh", tags=["conflicts"])
    def refresh(k: KnowledgeBase = Depends(get_kb)) -> dict:
        return k.refresh_analysis()

    # ----------------------------------------------------------------- overview / evaluation
    @app.get("/stats", tags=["overview"])
    def stats(k: KnowledgeBase = Depends(get_kb)) -> dict:
        return k.stats()

    @app.get("/events", tags=["overview"])
    def events(limit: int = 30, k: KnowledgeBase = Depends(get_kb)) -> list[dict]:
        names = {d.id: d.filename for d in k.list_documents(True)}
        return [as_dict(e) | {"filename": names.get(e.doc_id)} for e in k.history(limit=limit)]

    @app.get("/evaluation", tags=["evaluation"])
    def evaluation(k: KnowledgeBase = Depends(get_kb)) -> dict:
        """Latest experiment results written by `python -m eval.run` (never generated by the API)."""
        results_dir = k.settings.results_dir
        files = sorted(results_dir.glob("*.json")) if results_dir.exists() else []
        return {f.stem: json.loads(f.read_text(encoding="utf-8")) for f in files}

    return app


app = create_app()
