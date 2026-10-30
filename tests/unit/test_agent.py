import re
from datetime import date

import pytest

from rag_sentinel.agent.graph import SentinelAgent
from rag_sentinel.agent.query_analysis import analyze_query
from rag_sentinel.agent.verification import ANSWERED, INSUFFICIENT, NEEDS_REVIEW, VERIFIED, verify

REF = date(2026, 10, 1)


@pytest.mark.parametrize(
    "q,mode,as_of",
    [
        ("How many days of annual leave do employees get?", "current", REF),
        ("What was the annual leave entitlement in March 2026?", "historical", date(2026, 3, 31)),
        ("What was the leave entitlement before June 2026?", "historical", date(2026, 5, 31)),
        ("What was the per diem as of 2025-12-15?", "historical", date(2025, 12, 15)),
        ("What will the per diem be in 2027?", "historical", date(2027, 12, 31)),
        ("What is the leave entitlement in 2026?", "current", REF),
        ("What was the previous annual leave entitlement?", "previous", REF),
    ],
)
def test_query_analysis(q, mode, as_of):
    qa = analyze_query(q, REF)
    assert (qa.mode, qa.as_of) == (mode, as_of)


def ev(label, doc, text, status="in_force", rel=0.9, chunk=None):
    return {"label": label, "doc_id": doc, "chunk_id": chunk or f"c-{doc}", "filename": f"{doc}.md", "text": text,
            "standing_status": status, "relevance": rel}  # fmt: skip


def run(gen, evidence, claims=(), conflicts=(), **kw):
    args = dict(question="How many days of annual leave?", generation=gen, evidence=evidence, claims=list(claims),
                conflicts=list(conflicts), gating=True, use_relevance_gate=True, min_relevance=0.1, use_temporal=True,
                use_conflicts=True)  # fmt: skip
    args.update(kw)
    return verify(**args)


GOOD = {"answer": "Employees get 25 days. [E1]", "citations": ["E1"], "cannot_answer": False, "reason": ""}


def test_verified_when_supported_and_in_force():
    v = run(GOOD, [ev("E1", "v2", "Employees receive 25 days of annual leave.")])
    assert v.status == VERIFIED and v.valid_citations == ["E1"]


def test_r1_relevance_gate():
    assert run(GOOD, [ev("E1", "v2", "25 days", rel=0.01)]).rules_fired == ["R1"]


def test_r2_no_in_force_source():
    v = run(GOOD, [ev("E1", "draft", "25 days", status="unapproved")])
    assert v.status == INSUFFICIENT and v.rules_fired == ["R2"]


def test_r3_declined_and_r4_invalid_citations():
    declined = {"answer": "", "citations": [], "cannot_answer": True, "reason": "not covered"}
    assert run(declined, [ev("E1", "d", "text")]).rules_fired == ["R3"]
    fake = {"answer": "25 days [E7]", "citations": ["E7"], "cannot_answer": False, "reason": ""}
    v = run(fake, [ev("E1", "d", "25 days")])
    assert v.status == INSUFFICIENT and v.rules_fired == ["R4"] and v.invalid_citations == ["E7"]


def test_r5_unsupported_number():
    v = run({**GOOD, "answer": "Employees get 30 days. [E1]"}, [ev("E1", "v2", "Employees receive 25 days.")])
    assert v.status == NEEDS_REVIEW and v.unsupported_values == ["30"]


def test_r6_cites_only_superseded():
    v = run(GOOD, [ev("E1", "v1", "25 days", status="superseded"), ev("E2", "v2", "25 days")])
    assert v.status == NEEDS_REVIEW and "R6" in v.rules_fired


CLAIM = {"chunk_id": "c-v2", "predicate_key": "annual_leave", "predicate": "annual_leave", "value_num": 25.0}


def test_r7_unresolved_contradiction_blocks():
    conflict = {"id": "x", "predicate_key": "annual_leave", "kind": "contradiction", "preferred_doc_id": None,
                "status": "open", "doc_a_id": "v2", "doc_b_id": "other", "explanation": "A says 25, B says 30"}  # fmt: skip
    v = run(GOOD, [ev("E1", "v2", "25 days")], [CLAIM], [conflict])
    assert v.status == NEEDS_REVIEW and v.rules_fired == ["R7"]
    resolved = {**conflict, "status": "resolved", "preferred_doc_id": "v2"}
    assert run(GOOD, [ev("E1", "v2", "25 days")], [CLAIM], [resolved]).status == VERIFIED


def test_r8_cites_outdated_source_only():
    claim = {**CLAIM, "chunk_id": "c-handbook", "value_num": 20.0}
    conflict = {"id": "y", "predicate_key": "annual_leave", "kind": "outdated", "preferred_doc_id": "v2",
                "status": "open", "doc_a_id": "v2", "doc_b_id": "handbook", "explanation": "handbook outdated"}  # fmt: skip
    gen = {"answer": "Employees get 20 days. [E1]", "citations": ["E1"], "cannot_answer": False, "reason": ""}
    v = run(gen, [ev("E1", "handbook", "Employees get 20 days.")], [claim], [conflict])
    assert v.status == NEEDS_REVIEW and v.rules_fired == ["R8"]


def test_baseline_has_no_gate():
    v = run({**GOOD, "answer": "30 days [E1]"}, [ev("E1", "d", "25 days", rel=0.0)], gating=False)
    assert v.status == ANSWERED


# ---------------------------------------------------------------- full graph with scripted LLM


def answer_from_evidence(_system: str, user: str) -> dict:
    """Scripted generator: answers with the value in the first in-force evidence block (or E1 if no metadata)."""
    blocks = re.findall(r"\[(E\d+)\][^\n]*\n(?:    ([^\n]*)\n)?    \"\"\"(.*?)\"\"\"", user, re.S)
    for label, meta, text in blocks:
        if not meta or "in force" in meta:
            m = re.search(r"(\d+) days", text)
            if m:
                return {"answer": f"Employees receive {m.group(1)} days. [{label}]", "citations": [label],
                        "cannot_answer": False, "reason": ""}  # fmt: skip
    return {"answer": "", "citations": [], "cannot_answer": True, "reason": "not in evidence"}


@pytest.fixture
def agent_kb(kb, leave_corpus, scripted_llm):
    scripted_llm.handlers["GeneratedAnswer"] = answer_from_evidence
    kb.ingest_directory(leave_corpus)
    return kb


def test_graph_b4_verified_with_trace(agent_kb):
    res = SentinelAgent(agent_kb, "B4").ask("How many days of annual leave do full-time employees get?")
    assert res["status"] == VERIFIED and "25 days" in res["answer"]
    assert res["citations"][0]["filename"] == "leave_policy_v2.md"
    assert [t["node"] for t in res["trace"]] == [
        "analyze_query",
        "retrieve",
        "extract_claims",
        "detect_conflicts",
        "rank_evidence",
        "generate_answer",
        "verify_evidence",
        "final_decision",
    ]
    assert any(c["kind"] == "outdated" for c in res["conflicts"])
    assert any("Conflict noted" in w for w in res["warnings"])


def test_graph_historical_question_uses_old_version(agent_kb):
    res = SentinelAgent(agent_kb, "B4").ask("How many days of annual leave did full-time employees get in March 2026?")
    assert res["analysis"]["mode"] == "historical" and "20 days" in res["answer"]
    assert res["citations"][0]["filename"] in ("leave_policy_v1.md", "employee_handbook.md")


def test_graph_previous_version(agent_kb):
    res = SentinelAgent(agent_kb, "B4").ask("What was the previous annual leave entitlement for full-time employees?")
    assert res["analysis"]["as_of"] == "2026-05-31" and "20 days" in res["answer"]


def test_graph_baseline_runs_and_reports_answered(agent_kb):
    res = SentinelAgent(agent_kb, "B0").ask("How many days of annual leave do employees get?")
    assert res["status"] in (ANSWERED, INSUFFICIENT) and res["conflicts"] == []
    assert [t["detail"] for t in res["trace"] if t["node"] == "extract_claims"] == ["skipped (pipeline)"]
