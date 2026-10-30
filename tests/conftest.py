from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest

from rag_sentinel.config import Settings
from rag_sentinel.kb import KnowledgeBase
from rag_sentinel.retrieval.vector_store import VectorStore
from tests.fakes import HashEmbedder, OverlapReranker, ScriptedLLM

_VALUE = re.compile(r"(\$\d+|\d+ (?:days|weeks|hours|characters|years))")


def regex_claims(_system: str, user: str) -> dict:
    """Stand-in for the LLM claim extractor: one claim per sentence containing a value.

    Predicate = the sentence's leading words naming the attribute, marked in fixtures as `[[predicate]]`.
    """
    passage = user.split('"""')[1]
    claims = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", passage):
        m = re.search(r"\[\[(\w+)\|([^\]]+)\]\]", sentence)
        v = _VALUE.search(sentence)
        if not (m and v):
            continue
        claims.append(
            {
                "subject": m.group(2),
                "predicate": m.group(1),
                "value": v.group(1),
                "qualifier": "",
                "effective_date": "",
                "source_quote": sentence.strip(),
                "confidence": 0.9,
            }
        )
    return {"claims": claims}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    from datetime import date

    return Settings(data_dir=tmp_path / "kb", as_of=date(2026, 10, 1), chunk_size=400, chunk_overlap=80,
                    use_llm_conflict_judge=False, _env_file=None)  # fmt: skip


@pytest.fixture
def scripted_llm() -> ScriptedLLM:
    return ScriptedLLM({"ClaimList": regex_claims})


@pytest.fixture
def kb(settings: Settings, scripted_llm: ScriptedLLM) -> KnowledgeBase:
    k = KnowledgeBase(settings, HashEmbedder(), scripted_llm, OverlapReranker(), vectors=VectorStore(":memory:"))
    yield k
    k.vectors.close()


def write_md(folder: Path, name: str, front: dict, body: str) -> Path:
    import yaml

    folder.mkdir(parents=True, exist_ok=True)
    p = folder / name
    p.write_text("---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n" + textwrap.dedent(body), encoding="utf-8")
    return p


@pytest.fixture
def leave_corpus(tmp_path: Path) -> Path:
    """The canonical example: policy v1 (20 days) -> v2 (25 days); handbook still says 20; contractor FAQ 10."""
    d = tmp_path / "corpus"
    write_md(d, "leave_policy_v1.md",
             {"title": "Annual Leave Policy", "family": "leave-policy", "version": "1.0", "publication_date": "2026-01-05",
              "effective_date": "2026-01-15", "authority_level": 5, "approval_status": "approved"},
             """
             # Annual Leave Policy

             [[annual_leave_entitlement|employee]] Full-time employees receive 20 days of paid annual leave per year.

             Leave requests must be submitted through the HR portal.
             """)  # fmt: skip
    write_md(d, "leave_policy_v2.md",
             {"title": "Annual Leave Policy", "family": "leave-policy", "version": "2.0", "publication_date": "2026-05-20",
              "effective_date": "2026-06-01", "authority_level": 5, "approval_status": "approved",
              "supersedes": "leave_policy_v1.md"},
             """
             # Annual Leave Policy

             [[annual_leave_entitlement|employee]] Full-time employees receive 25 days of paid annual leave per year.

             Leave requests must be submitted through the HR portal.
             """)  # fmt: skip
    write_md(d, "employee_handbook.md",
             {"title": "Employee Handbook", "version": "2025.2", "publication_date": "2025-11-01",
              "effective_date": "2025-11-01", "authority_level": 3, "approval_status": "approved"},
             """
             # Employee Handbook

             [[annual_leave_entitlement|employee]] Employees are entitled to 20 days of annual leave.

             The office opens at 8 am.
             """)  # fmt: skip
    write_md(d, "contractor_faq.md",
             {"title": "Contractor FAQ", "publication_date": "2026-02-01", "effective_date": "2026-02-01",
              "authority_level": 2, "approval_status": "approved"},
             """
             # Contractor FAQ

             [[annual_leave_entitlement|contractor]] Contractors accrue 10 days of unpaid leave per year.
             """)  # fmt: skip
    return d
