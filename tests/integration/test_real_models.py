"""Integration tests against the real local models (Ollama + bge-reranker-base). Run: pytest -m integration"""

from datetime import date

import pytest

from rag_sentinel.agent.graph import SentinelAgent
from rag_sentinel.config import Settings
from rag_sentinel.kb import KnowledgeBase
from rag_sentinel.retrieval.vector_store import VectorStore
from tests.conftest import write_md

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def real_kb(tmp_path_factory):
    base = Settings()
    settings = base.model_copy(update={"data_dir": tmp_path_factory.mktemp("kb"), "as_of": date(2026, 10, 1)})
    kb = KnowledgeBase.from_settings(settings)
    kb.vectors.close()
    kb.vectors = VectorStore(":memory:")
    kb.retriever.vectors = kb.vectors
    if not kb.llm.ping():
        pytest.skip("Ollama not running or model not pulled")
    d = tmp_path_factory.mktemp("corpus")
    write_md(d, "leave_policy_v1.md", {"title": "Annual Leave Policy", "family": "leave-policy", "version": "1.0",
             "effective_date": "2026-01-15", "authority_level": 5, "approval_status": "approved"},
             "# Annual Leave Policy\n\nFull-time employees receive 20 days of paid annual leave per calendar year.\n\n"
             "Up to 5 unused days may be carried over to the next year.\n")  # fmt: skip
    write_md(d, "leave_policy_v2.md", {"title": "Annual Leave Policy", "family": "leave-policy", "version": "2.0",
             "effective_date": "2026-06-01", "authority_level": 5, "approval_status": "approved",
             "supersedes": "leave_policy_v1.md"},
             "# Annual Leave Policy\n\nFull-time employees receive 25 days of paid annual leave per calendar year.\n\n"
             "Up to 5 unused days may be carried over to the next year.\n")  # fmt: skip
    write_md(d, "employee_handbook.md", {"title": "Employee Handbook", "effective_date": "2025-11-01",
             "authority_level": 3, "approval_status": "approved"},
             "# Employee Handbook\n\n## Time off\n\nAll employees are entitled to 20 days of annual leave each year. "
             "Sick leave is 10 days per year.\n")  # fmt: skip
    write_md(d, "contractor_faq.md", {"title": "Contractor FAQ", "effective_date": "2026-02-01", "authority_level": 2,
             "approval_status": "approved"},
             "# Contractor FAQ\n\nContractors are not eligible for paid annual leave; they may take up to 10 unpaid "
             "days per year.\n")  # fmt: skip
    kb.ingest_directory(d)
    yield kb
    kb.vectors.close()


def test_real_claims_are_grounded(real_kb):
    claims = real_kb.claims()
    assert claims, "the LLM extracted no claims"
    for c in claims:
        text = real_kb.lookup_chunks([c.chunk_id])[c.chunk_id][1]
        assert " ".join(c.source_quote.split()).lower() in " ".join(text.split()).lower()
    values = {c.value_norm for c in claims}
    assert {"20 day", "25 day"} <= values


def test_real_conflicts(real_kb):
    # v0.1 regression: the LLM judge overruled this rule finding ('all employees' vs 'full-time employees').
    # Since v0.2 the judge can only add a dissenting opinion to a rule finding, never remove it.
    kinds = {c.kind for c in real_kb.conflicts()}
    assert "outdated" in kinds and "historical" in kinds
    assert "contradiction" not in kinds, [c.explanation for c in real_kb.conflicts() if c.kind == "contradiction"]


def test_real_end_to_end_answer(real_kb):
    res = SentinelAgent(real_kb, "B4").ask("How many days of annual leave do full-time employees get?")
    assert res["status"] == "VERIFIED", res["reasons"]
    assert "25" in res["answer"] and res["citations"][0]["filename"] == "leave_policy_v2.md"


def test_real_unanswerable(real_kb):
    res = SentinelAgent(real_kb, "B4").ask("What is the company's dental insurance provider?")
    assert res["status"] == "INSUFFICIENT_EVIDENCE"
