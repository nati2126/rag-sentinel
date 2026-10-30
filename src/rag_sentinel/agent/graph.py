"""LangGraph evidence-verification workflow.

analyze_query -> retrieve -> extract_claims -> detect_conflicts -> rank_evidence
    -> (no evidence) -> final_decision
    -> generate_answer -> verify_evidence -> final_decision

Each node is a plain method (testable without LangGraph) and appends a trace entry, so every decision in
the final result can be traced back to the node and rule that produced it.
"""

from __future__ import annotations

import operator
import time
from dataclasses import asdict
from datetime import date, timedelta
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from rag_sentinel.agent.answer_check import make_answer_checker
from rag_sentinel.agent.generation import SYSTEM as GEN_SYSTEM
from rag_sentinel.agent.generation import GeneratedAnswer, build_prompt
from rag_sentinel.agent.query_analysis import analyze_query
from rag_sentinel.agent.verification import ANSWERED, INSUFFICIENT, VERIFIED, citations_in, verify
from rag_sentinel.conflicts.detect import ConflictDetector, make_pair_judge
from rag_sentinel.db import Claim, Document
from rag_sentinel.ingest.versioning import valid_from
from rag_sentinel.kb import KnowledgeBase
from rag_sentinel.llm import LLMError
from rag_sentinel.log import get_logger
from rag_sentinel.pipelines import PIPELINES, Pipeline
from rag_sentinel.ranking import PRESETS, rank_evidence
from rag_sentinel.retrieval.retriever import RetrievalConfig

log = get_logger(__name__)

RANK_POOL = 10  # candidates passed from retrieval to evidence ranking


class SentinelState(TypedDict, total=False):
    question: str
    as_of: str | None
    analysis: dict[str, Any]
    hits: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    generation: dict[str, Any] | None
    answer_check: dict[str, Any] | None
    verification: dict[str, Any]
    result: dict[str, Any]
    trace: Annotated[list[dict[str, Any]], operator.add]


def _d(v: Any) -> Any:
    return v.isoformat() if isinstance(v, date) else v


def claim_dict(c: Claim) -> dict:
    return {k: _d(v) for k, v in c.model_dump().items()}


class SentinelAgent:
    def __init__(self, kb: KnowledgeBase, pipeline: Pipeline | str = "B4"):
        self.kb = kb
        self.p = PIPELINES[pipeline] if isinstance(pipeline, str) else pipeline
        self.settings = kb.settings
        self.graph = self._build()
        self._docs: dict[str, Document] = {}

    # ------------------------------------------------------------------ graph
    def _build(self):
        g = StateGraph(SentinelState)
        for name in ("analyze_query", "retrieve", "extract_claims", "detect_conflicts", "rank_evidence",
                     "generate_answer", "check_answer", "verify_evidence", "final_decision"):  # fmt: skip
            g.add_node(name, getattr(self, name))
        g.add_edge(START, "analyze_query")
        g.add_edge("analyze_query", "retrieve")
        g.add_edge("retrieve", "extract_claims")
        g.add_edge("extract_claims", "detect_conflicts")
        g.add_edge("detect_conflicts", "rank_evidence")
        g.add_conditional_edges("rank_evidence", self._has_evidence, {"yes": "generate_answer", "no": "final_decision"})
        g.add_edge("generate_answer", "check_answer")
        g.add_edge("check_answer", "verify_evidence")
        g.add_edge("verify_evidence", "final_decision")
        g.add_edge("final_decision", END)
        return g.compile()

    @staticmethod
    def _has_evidence(state: SentinelState) -> str:
        return "yes" if state.get("evidence") else "no"

    def ask(self, question: str, as_of: date | None = None) -> dict[str, Any]:
        t0 = time.perf_counter()
        self._docs = self.kb.documents_map()
        state = self.graph.invoke({"question": question, "as_of": as_of.isoformat() if as_of else None, "trace": []})
        result = state["result"]
        result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        result["trace"] = state["trace"]
        return result

    # ------------------------------------------------------------------ nodes
    def analyze_query(self, state: SentinelState) -> dict:
        t = time.perf_counter()
        ref = date.fromisoformat(state["as_of"]) if state.get("as_of") else self.settings.reference_date()
        if self.p.temporal_ranking:
            qa = analyze_query(state["question"], ref)
        else:
            from rag_sentinel.agent.query_analysis import QueryAnalysis

            qa = QueryAnalysis(state["question"], "current", ref, ref, note="temporal analysis disabled")
        return {"analysis": qa.to_dict(), "trace": [_tr("analyze_query", t, f"mode={qa.mode}, as_of={qa.as_of}")]}

    def retrieve(self, state: SentinelState) -> dict:
        t = time.perf_counter()
        s = self.settings
        cfg = RetrievalConfig(self.p.retrieval_mode, self.p.rerank, s.dense_k, s.bm25_k, s.rrf_k, s.rerank_candidates,
                              final_k=RANK_POOL)  # fmt: skip
        hits = self.kb.retriever.retrieve(state["question"], cfg)
        out = [asdict(h) for h in hits]
        return {
            "hits": out,
            "trace": [_tr("retrieve", t, f"{len(out)} hits ({self.p.retrieval_mode}, rerank={self.p.rerank})")],
        }

    def extract_claims(self, state: SentinelState) -> dict:
        t = time.perf_counter()
        if not self.p.conflict_detection:
            return {"claims": [], "trace": [_tr("extract_claims", t, "skipped (pipeline)")]}
        # Claims are extracted once at ingestion (with grounding checks) and looked up here.
        claims = self.kb.claims_for_chunks([h["chunk_id"] for h in state["hits"]])
        return {"claims": [claim_dict(c) for c in claims],
                "trace": [_tr("extract_claims", t, f"{len(claims)} claims for {len(state['hits'])} passages")]}  # fmt: skip

    def detect_conflicts(self, state: SentinelState) -> dict:
        t = time.perf_counter()
        if not self.p.conflict_detection or not state["claims"]:
            return {"conflicts": [], "trace": [_tr("detect_conflicts", t, "skipped")]}
        keys = {c["predicate_key"] for c in state["claims"]}
        all_claims = [c for c in self.kb.claims() if c.predicate_key in keys]
        as_of = date.fromisoformat(state["analysis"]["as_of"])
        lineage = self.kb.lineage()
        llm = self.kb.llm if self.settings.use_llm_conflict_judge else None
        judge = make_pair_judge(llm, self._docs, self.kb.db.cache_get, self.kb.db.cache_set) if llm else None
        det = ConflictDetector(self._docs, all_claims, lineage, as_of, self.settings.ranking,
                               self.settings.authority_margin, judge)  # fmt: skip
        try:
            findings = det.detect(keys)
        except LLMError as exc:
            log.warning("conflict judge failed; rule-only detection", extra={"error": str(exc)})
            det.judge = None
            findings = det.detect(keys)
        stored = {c.id: c for c in self.kb.conflicts(keys=keys)}
        out = []
        for f in findings:
            row = stored.get(f.id)
            status = row.status if row else "open"
            preferred = row.preferred_doc_id if (row and row.status == "resolved") else f.preferred_doc_id
            out.append({
                "id": f.id, "predicate_key": f.predicate_key, "kind": f.kind, "confirmed": f.confirmed,
                "preferred_doc_id": preferred, "margin": f.margin, "explanation": f.explanation,
                "detected_by": f.detected_by, "judge_opinion": f.judge_opinion, "status": status,
                "resolution_note": row.resolution_note if row else None,
                "doc_a_id": f.claim_a.doc_id, "doc_b_id": f.claim_b.doc_id,
                "claim_a": claim_dict(f.claim_a), "claim_b": claim_dict(f.claim_b),
            })  # fmt: skip
        summary = ", ".join(f"{k}={sum(1 for o in out if o['kind'] == k)}" for k in sorted({o["kind"] for o in out}))
        return {"conflicts": out, "trace": [_tr("detect_conflicts", t, f"{len(out)} findings ({summary or 'none'})")]}

    def rank_evidence(self, state: SentinelState) -> dict:
        t = time.perf_counter()
        hits = state["hits"]
        analysis = dict(state["analysis"])
        as_of = date.fromisoformat(analysis["as_of"])
        lineage = self.kb.lineage()
        weights = PRESETS[self.p.ranking_preset] if self.p.ranking_preset != "default" else self.settings.ranking

        from rag_sentinel.retrieval.retriever import Hit

        hit_objs = [Hit(**h) for h in hits]
        note = ""
        if analysis["mode"] == "previous" and self.p.temporal_ranking:
            current = rank_evidence(hit_objs, self._docs, lineage, as_of, weights)
            top_in_force = next((e for e in current if e.standing.in_force), None)
            if top_in_force:
                start = valid_from(self._docs[top_in_force.doc_id])
                has_prev = any(lineage.is_ancestor(m.id, top_in_force.doc_id)
                               for m in lineage.lineage_members(top_in_force.doc_id))  # fmt: skip
                if start and has_prev:
                    as_of = start - timedelta(days=1)
                    note = f"previous version: as-of set to {as_of} (day before {self._docs[top_in_force.doc_id].filename} took effect)"
            analysis["as_of"] = as_of.isoformat()
            analysis["note"] = note or "no earlier version found; answering for the current date"

        if self.p.temporal_ranking:
            ranked = rank_evidence(hit_objs, self._docs, lineage, as_of, weights)
            items = [(e.chunk_id, e.doc_id, e.relevance, e.score, e.standing.status, e.factors, e.explanation)
                     for e in ranked]  # fmt: skip
        else:
            from rag_sentinel.ranking import standing as standing_fn

            items = []
            for h in hit_objs:
                if h.doc_id not in self._docs:
                    continue
                st = standing_fn(self._docs[h.doc_id], as_of, lineage, weights)
                items.append((h.chunk_id, h.doc_id, h.relevance, h.relevance, st.status, {"relevance": h.relevance},
                              "ordered by retrieval relevance"))  # fmt: skip
        by_chunk = {h.chunk_id: h for h in hit_objs}
        evidence = []
        for i, (cid, did, rel, score, status, factors, expl) in enumerate(items[: self.settings.final_k], 1):
            d = self._docs[did]
            h = by_chunk[cid]
            evidence.append({
                "label": f"E{i}", "chunk_id": cid, "doc_id": did, "filename": d.filename, "title": d.title or d.filename,
                "version": d.version_label, "page": h.page, "text": h.text, "relevance": round(rel, 4),
                "score": score, "standing_status": status, "effective_date": _d(d.effective_date),
                "publication_date": _d(d.publication_date), "approval_status": d.approval_status,
                "authority_level": d.authority_level, "factors": factors, "explanation": expl,
            })  # fmt: skip
        summary = ", ".join(f"{e['label']}={e['filename']}({e['standing_status']})" for e in evidence[:3])
        return {"evidence": evidence, "analysis": analysis,
                "trace": [_tr("rank_evidence", t, (note + "; " if note else "") + (summary or "no evidence"))]}  # fmt: skip

    def generate_answer(self, state: SentinelState) -> dict:
        t = time.perf_counter()
        notes = []
        if self.p.conflict_detection:
            for c in state["conflicts"]:
                if (
                    c["kind"] in ("contradiction", "outdated", "historical", "pending_change")
                    and c["status"] != "dismissed"
                ):
                    notes.append(c["explanation"])
        prompt = build_prompt(state["question"], state["evidence"], self.p.metadata_in_prompt,
                              state["analysis"]["as_of"], state["analysis"]["mode"], notes[:6])  # fmt: skip
        if self.kb.llm is None:
            return {"generation": None, "trace": [_tr("generate_answer", t, "no LLM configured")]}
        try:
            gen = self.kb.llm.chat_json(GEN_SYSTEM, prompt, GeneratedAnswer)
        except LLMError as exc:
            log.error("generation failed", extra={"error": str(exc)})
            return {"generation": None, "trace": [_tr("generate_answer", t, f"LLM error: {exc}")]}
        return {"generation": gen.model_dump(),
                "trace": [_tr("generate_answer", t, "declined" if gen.cannot_answer else f"cited {gen.citations}")]}  # fmt: skip

    def check_answer(self, state: SentinelState) -> dict:
        t = time.perf_counter()
        gen = state.get("generation")
        if not (self.p.answer_check and self.p.gating) or not gen or gen.get("cannot_answer") or self.kb.llm is None:
            return {"answer_check": None, "trace": [_tr("check_answer", t, "skipped")]}
        by_label = {e["label"]: e for e in state["evidence"]}
        cited = [by_label[c] for c in citations_in(gen["answer"], gen.get("citations", [])) if c in by_label]
        if not cited:
            return {"answer_check": None, "trace": [_tr("check_answer", t, "skipped (no valid citation)")]}
        checker = make_answer_checker(self.kb.llm, self.kb.db.cache_get, self.kb.db.cache_set)
        try:
            res = checker(state["question"], gen["answer"], cited).model_dump()
        except LLMError as exc:
            # the check failed: record it so verification flags the answer for review instead of trusting it
            res = {"answers_question": True, "supported": False, "missing": "", "error": str(exc)[:200]}
        detail = (
            "error" if res.get("error") else f"answers_question={res['answers_question']} supported={res['supported']}"
        )
        return {"answer_check": res, "trace": [_tr("check_answer", t, detail)]}

    def verify_evidence(self, state: SentinelState) -> dict:
        t = time.perf_counter()
        v = verify(
            question=state["question"], generation=state.get("generation"), evidence=state["evidence"],
            claims=state.get("claims", []), conflicts=state.get("conflicts", []), gating=self.p.gating,
            use_relevance_gate=self.p.rerank, min_relevance=self.settings.min_relevance,
            use_temporal=self.p.temporal_ranking, use_conflicts=self.p.conflict_detection,
            as_of=state["analysis"]["as_of"] if self.p.metadata_in_prompt else "",
            answer_check=state.get("answer_check"),
        )  # fmt: skip
        return {"verification": v.to_dict(),
                "trace": [_tr("verify_evidence", t, f"{v.status} rules={v.rules_fired or ['none']}")]}  # fmt: skip

    def final_decision(self, state: SentinelState) -> dict:
        t = time.perf_counter()
        evidence = state.get("evidence", [])
        gen = state.get("generation")
        if not evidence:
            ver = verify(question=state["question"], generation=None, evidence=[], claims=[], conflicts=[],
                         gating=self.p.gating, use_relevance_gate=False, min_relevance=0, use_temporal=False,
                         use_conflicts=False).to_dict()  # fmt: skip
        else:
            ver = state["verification"]
        status = ver["status"]
        by_label = {e["label"]: e for e in evidence}
        citations = [
            {k: by_label[c][k] for k in ("label", "chunk_id", "doc_id", "filename", "title", "version", "page",
                                         "effective_date", "approval_status", "standing_status", "text")}
            for c in ver.get("valid_citations", []) if c in by_label
        ]  # fmt: skip
        draft = (gen or {}).get("answer", "")
        if status == INSUFFICIENT:
            answer = "I can't give a reliable answer. " + " ".join(ver["reasons"])
        else:
            answer = draft
        result = {
            "question": state["question"],
            "pipeline": self.p.name,
            "status": status,
            "presented_as_reliable": status in (VERIFIED, ANSWERED),
            "answer": answer,
            "draft_answer": draft,
            "citations": citations,
            "reasons": ver["reasons"],
            "warnings": ver["warnings"],
            "rules_fired": ver["rules_fired"],
            "unsupported_values": ver.get("unsupported_values", []),
            "evidence": evidence,
            "conflicts": state.get("conflicts", []),
            "analysis": state["analysis"],
            "generation": gen,
        }
        return {"result": result, "trace": [_tr("final_decision", t, status)]}


def _tr(node: str, t0: float, detail: str) -> dict:
    return {"node": node, "ms": round((time.perf_counter() - t0) * 1000, 1), "detail": detail}
