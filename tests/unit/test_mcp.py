import json

import anyio
import pytest
from mcp import Client

from rag_sentinel.llm import LLMError
from rag_sentinel.mcp.server import build_server
from rag_sentinel.mcp.tools import SentinelTools, ToolInputError
from tests.unit.test_agent import answer_from_evidence

AS_OF = "2026-10-01"
TOOLS = {"search_documents", "ask_verified", "check_statement", "list_documents", "get_document_versions",
         "list_conflicts"}  # fmt: skip


@pytest.fixture
def tools(kb, leave_corpus, scripted_llm):
    scripted_llm.handlers["GeneratedAnswer"] = answer_from_evidence
    kb.ingest_directory(leave_corpus)
    return SentinelTools(kb)


def test_search_ranks_in_force_source_first(tools):
    res = tools.search_documents("annual leave days for full-time employees", AS_OF, top_k=3)
    assert res["as_of"] == AS_OF and len(res["results"]) == 3
    top = res["results"][0]
    assert top["filename"] == "leave_policy_v2.md" and top["standing"] == "in_force"
    standings = {r["filename"]: r["standing"] for r in res["results"]}
    assert standings.get("leave_policy_v1.md", "superseded") == "superseded"


def test_search_top_k_is_capped(tools):
    assert len(tools.search_documents("leave", AS_OF, top_k=50)["results"]) <= 10


def test_ask_verified_is_compact(tools):
    res = tools.ask_verified("How many days of annual leave do full-time employees get?", AS_OF)
    assert res["status"] == "VERIFIED" and res["presented_as_reliable"] is True
    assert "25 days" in res["answer"]
    assert res["citations"][0]["filename"] == "leave_policy_v2.md"
    assert set(res["citations"][0]) == {"label", "filename", "version", "standing", "effective_date", "quote"}
    assert "evidence" not in res and "trace" not in res
    json.dumps(res)  # serialisable


def test_ask_verified_for_a_past_date(tools):
    res = tools.ask_verified("How many days of annual leave did full-time employees get?", "2026-03-01")
    assert res["as_of"] == "2026-03-01" and "20 days" in res["answer"]
    assert res["citations"][0]["filename"] == "leave_policy_v1.md"


def _value(res, n):
    return next(v for v in res["values"] if v["value"] == n)


def test_check_statement_outdated_value(tools):
    res = tools.check_statement("Full-time employees receive 20 days of annual leave.", AS_OF)
    v = _value(res, "20")
    assert v["finding"] == "outdated"
    src = {s["filename"]: s for s in v["sources"]}
    assert src["leave_policy_v1.md"]["standing"] == "superseded"
    # the handbook is in force, but it is the outdated side of a conflict and still states the old v1 value
    kinds = {f["kind"]: f for f in src["employee_handbook.md"]["flags"]}
    assert {"outdated", "value_changed_in_newer_version"} <= set(kinds)
    assert kinds["value_changed_in_newer_version"]["preferred_document"] == "leave_policy_v2.md"
    assert kinds["value_changed_in_newer_version"]["preferred_value"] == "25 days"
    assert "20 days" in src["employee_handbook.md"]["sentence"]
    assert res["verified_answer"]["status"] == "VERIFIED" and "25 days" in res["verified_answer"]["answer"]


def test_check_statement_current_value(tools):
    v = _value(tools.check_statement("Full-time employees receive 25 days of annual leave.", AS_OF), "25")
    assert v["finding"] == "current"
    assert [(s["filename"], s["flags"]) for s in v["sources"]] == [("leave_policy_v2.md", [])]


def test_check_statement_ignores_unrelated_sentences(tools):
    # the handbook says "The office opens at 8 am.": the number is there, the statement is not
    v = _value(tools.check_statement("Full-time employees receive 8 days of annual leave.", AS_OF), "8")
    assert v["finding"] == "not_found" and v["sources"] == []


def test_list_documents_reports_standing(tools):
    res = tools.list_documents(AS_OF)
    rows = {d["filename"]: d for d in res["documents"]}
    assert res["count"] == 4
    assert rows["leave_policy_v1.md"]["standing"] == "superseded"
    assert rows["leave_policy_v1.md"]["superseded_by"] == "leave_policy_v2.md"
    assert rows["leave_policy_v2.md"]["standing"] == "in_force"
    assert tools.list_documents(AS_OF, family="leave-policy")["count"] == 2
    # before v2 took effect, v1 is the one in force
    early = {d["filename"]: d["standing"] for d in tools.list_documents("2026-03-01")["documents"]}
    assert early["leave_policy_v1.md"] == "in_force" and early["leave_policy_v2.md"] == "not_yet_effective"


def test_document_versions_changes_and_affected(tools):
    res = tools.get_document_versions("leave_policy_v2", AS_OF)
    assert res["document"] == "leave_policy_v2.md"
    assert [v["filename"] for v in res["versions"]] == ["leave_policy_v1.md", "leave_policy_v2.md"]
    change = res["changes_from_previous_version"][0]
    assert (change["old_value"], change["new_value"]) == ("20 days", "25 days")
    assert res["documents_still_using_old_values"][0]["filename"] == "employee_handbook.md"


def test_list_conflicts_filters(tools):
    res = tools.list_conflicts()
    assert res["total"] >= 1
    row = res["conflicts"][0]
    assert row["kind"] in ("outdated", "contradiction") and row["status"] == "open"
    assert {row["document_a"], row["document_b"]} >= {"employee_handbook.md"}
    assert tools.list_conflicts(document="contractor_faq.md")["total"] == 0
    assert tools.list_conflicts(status="resolved")["total"] == 0


def test_input_errors(tools):
    with pytest.raises(ToolInputError, match="No document matches"):
        tools.get_document_versions("no_such_file")
    with pytest.raises(ToolInputError, match="several documents"):
        tools.get_document_versions("leave_policy")
    with pytest.raises(ToolInputError, match="YYYY-MM-DD"):
        tools.list_documents("1 October")


def test_kb_is_created_lazily(kb):
    made = []

    def factory():
        made.append(1)
        return kb

    t = SentinelTools(factory)
    assert made == []
    t.list_documents()
    t.list_documents()
    assert made == [1]


# ---------------------------------------------------------------- over the MCP protocol (in-process client)
def _run(server, fn):
    async def main():
        async with Client(server, raise_exceptions=True) as client:
            return await fn(client)

    return anyio.run(main)


def test_server_lists_read_only_tools(tools):
    async def go(client):
        return (await client.list_tools()).tools

    listed = _run(build_server(tools), go)
    assert {t.name for t in listed} == TOOLS
    for t in listed:
        assert t.description and t.annotations.read_only_hint is True
    ask = next(t for t in listed if t.name == "ask_verified")
    assert ask.input_schema["required"] == ["question"]


def test_server_call_tool_returns_structured_result(tools):
    async def go(client):
        return await client.call_tool("ask_verified", {"question": "How many days of annual leave do full-time "
                                                                   "employees get?", "as_of": AS_OF})  # fmt: skip

    res = _run(build_server(tools), go)
    assert not res.is_error
    assert res.structured_content["status"] == "VERIFIED"
    assert json.loads(res.content[0].text)["status"] == "VERIFIED"


def test_server_reports_input_errors_readably(tools):
    async def go(client):
        return await client.call_tool("get_document_versions", {"document": "no_such_file"})

    res = _run(build_server(tools), go)
    assert res.is_error and "No document matches" in res.content[0].text


def test_server_reports_llm_outage(tools, scripted_llm):
    def down(_s, _u):
        raise LLMError("connection refused")

    scripted_llm.handlers["GeneratedAnswer"] = down

    async def go(client):
        return await client.call_tool("ask_verified", {"question": "How many days of annual leave?"})

    res = _run(build_server(tools), go)
    # generation errors are caught by the pipeline itself and end as a refusal, not a crash
    assert not res.is_error and res.structured_content["status"] == "INSUFFICIENT_EVIDENCE"


def test_server_rejects_bad_arguments(tools):
    async def go(client):
        return await client.call_tool("search_documents", {"query": "leave", "top_k": 99})

    res = _run(build_server(tools), go)
    assert res.is_error
