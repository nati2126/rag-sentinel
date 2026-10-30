import pytest

from rag_sentinel.ingest.extract import ExtractionError
from tests.conftest import write_md


def test_duplicate_detection_by_sha(kb, tmp_path):
    p = write_md(tmp_path, "a.md", {"title": "A"}, "Some text about leave.")
    r1 = kb.ingest_path(p)
    copy = tmp_path / "renamed.md"
    copy.write_bytes(p.read_bytes())
    r2 = kb.ingest_path(copy)
    assert r1.status == "created" and r2.status == "duplicate" and r2.document.id == r1.document.id
    assert len(kb.list_documents()) == 1
    assert any(e.event == "duplicate" for e in kb.history())


def test_changed_file_becomes_new_version_and_old_is_preserved(kb, tmp_path):
    p = write_md(tmp_path / "v1", "policy.md", {"title": "P"}, "Version one text.")
    r1 = kb.ingest_path(p)
    p2 = write_md(tmp_path / "v2", "policy.md", {"title": "P"}, "Version two text, changed.")
    r2 = kb.ingest_path(p2)
    assert r2.status == "new_version" and r2.previous_version_id == r1.document.id
    assert r2.document.version_number == 2 and r2.document.family_id == r1.document.family_id
    versions = kb.versions(r2.document.id)
    assert [v.version_number for v in versions] == [1, 2]
    assert kb.chunks_for(r1.document.id), "old version must stay indexed for historical questions"


def test_missing_metadata_is_not_invented(kb, tmp_path):
    r = kb.ingest_path(write_md(tmp_path, "x.md", {}, "Plain text."))
    d = r.document
    assert d.effective_date is None and d.authority_level is None and d.approval_status == "unknown"
    assert any("effective_date unknown" in w for w in r.warnings)


def test_user_metadata_overrides_and_is_tracked(kb, tmp_path):
    r = kb.ingest_path(write_md(tmp_path, "x.md", {"authority_level": 2}, "Text."), user_metadata={"authority_level": 4})
    assert r.document.authority_level == 4 and r.document.metadata_sources["authority_level"] == "user"


def test_supersedes_resolves_even_when_ingested_out_of_order(kb, leave_corpus):
    kb.ingest_path(leave_corpus / "leave_policy_v2.md")
    r1 = kb.ingest_path(leave_corpus / "leave_policy_v1.md")
    v2 = next(d for d in kb.list_documents() if d.filename == "leave_policy_v2.md")
    assert v2.supersedes_id == r1.document.id


def test_mark_superseded_delete_and_reindex(kb, tmp_path):
    a = kb.ingest_path(write_md(tmp_path, "guide.md", {"title": "Guide"}, "Old guide text.")).document
    b = kb.ingest_path(write_md(tmp_path, "manual.md", {"title": "Manual"}, "New manual text.")).document
    kb.mark_superseded(a.id, b.id)
    assert kb.get_document(b.id).supersedes_id == a.id
    n_chunks, *_ = kb.reindex_document(b.id)
    assert n_chunks >= 1
    kb.delete_document(a.id)
    assert kb.get_document(a.id).is_deleted and not kb.chunks_for(a.id)
    assert [d.id for d in kb.list_documents()] == [b.id]
    assert len(kb.list_documents(include_deleted=True)) == 2
    assert kb.vectors.count() == len(kb.chunks_for(b.id))


def test_unsupported_upload_rejected(kb, tmp_path):
    p = tmp_path / "data.xlsx"
    p.write_bytes(b"x")
    with pytest.raises(ExtractionError):
        kb.ingest_path(p)
