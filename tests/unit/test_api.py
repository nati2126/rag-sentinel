import pytest
from fastapi.testclient import TestClient

from rag_sentinel.api.main import create_app
from tests.unit.test_agent import answer_from_evidence


@pytest.fixture
def client(kb, scripted_llm):
    scripted_llm.handlers["GeneratedAnswer"] = answer_from_evidence
    with TestClient(create_app(kb)) as c:
        yield c


def upload(client, path, **meta):
    with path.open("rb") as fh:
        return client.post("/documents", files={"file": (path.name, fh, "text/markdown")}, data=meta)


def test_upload_versions_ask_and_conflicts(client, leave_corpus):
    for name in ("leave_policy_v1.md", "leave_policy_v2.md", "employee_handbook.md", "contractor_faq.md"):
        r = upload(client, leave_corpus / name)
        assert r.status_code == 200, r.text
    dup = upload(client, leave_corpus / "employee_handbook.md")
    assert dup.json()["status"] == "duplicate"

    docs = client.get("/documents").json()
    assert len(docs) == 4
    v1 = next(d for d in docs if d["filename"] == "leave_policy_v1.md")
    v2 = next(d for d in docs if d["filename"] == "leave_policy_v2.md")
    assert v1["superseded"] is True and v2["superseded"] is False
    assert [v["version_number"] for v in client.get(f"/documents/{v2['id']}/versions").json()] == [1, 2]

    res = client.post("/ask", json={"question": "How many days of annual leave do full-time employees get?"}).json()
    assert res["status"] == "VERIFIED" and res["citations"][0]["doc_id"] == v2["id"]

    outdated = client.get("/conflicts", params={"kind": "outdated"}).json()
    assert len(outdated) == 1 and outdated[0]["doc_a"] and outdated[0]["claim_b"]
    r = client.post(f"/conflicts/{outdated[0]['id']}/resolve", json={"status": "resolved", "note": "ok"})
    assert r.json()["status"] == "resolved"

    affected = client.get(f"/documents/{v2['id']}/affected").json()
    assert affected["references"][0]["filename"] == "employee_handbook.md"

    stats = client.get("/stats").json()
    assert stats["documents"] == 4 and stats["outdated_references"] == 0  # resolved now
    assert client.get("/queries").json()[0]["status"] == "VERIFIED"


def test_upload_with_user_metadata_and_errors(client, tmp_path):
    p = tmp_path / "note.md"
    p.write_text("Laptops are replaced every 4 years.", encoding="utf-8")
    r = upload(client, p, authority_level="2", approval_status="draft", effective_date="2026-02-01")
    d = r.json()["document"]
    assert d["authority_level"] == 2 and d["approval_status"] == "draft" and d["effective_date"] == "2026-02-01"
    assert d["metadata_sources"]["authority_level"] == "user"

    bad = tmp_path / "x.xlsx"
    bad.write_bytes(b"x")
    assert upload(client, bad).status_code == 422
    assert client.get("/documents/nope").status_code == 404
    assert client.post("/ask", json={"question": "hello?", "pipeline": "B9"}).status_code == 400
    assert client.patch(f"/documents/{d['id']}/metadata", json={"authority_level": 4}).json()["authority_level"] == 4
    assert client.delete(f"/documents/{d['id']}").status_code == 200
    assert client.get("/documents").json() == []
