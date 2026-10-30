from datetime import date

from rag_sentinel.chunking import chunk_pages
from rag_sentinel.db import Document
from rag_sentinel.ingest.extract import Page
from rag_sentinel.ingest.versioning import Lineage, family_from_filename


def test_family_from_filename():
    assert family_from_filename("Leave_Policy_v2.pdf") == "leave-policy"
    assert family_from_filename("leave-policy-2026-06.docx") == "leave-policy"
    assert family_from_filename("Travel Guide (draft).md") == "travel-guide"
    assert family_from_filename("handbook_rev3_final.md") == "handbook"


def _doc(i, family="f", v=1, eff=None, status="approved", sup=None):
    return Document(id=i, family_id=family, filename=f"{i}.md", content_type="md", sha256=i, version_number=v,
                    effective_date=eff, approval_status=status, supersedes_id=sup, stored_path="")  # fmt: skip


def test_lineage_family_versions_and_future_effective():
    v1 = _doc("v1", v=1, eff=date(2026, 1, 1))
    v2 = _doc("v2", v=2, eff=date(2026, 6, 1))
    v3 = _doc("v3", v=3, eff=date(2027, 1, 1))
    lin = Lineage([v1, v2, v3])
    assert lin.superseded_at("v1", date(2026, 7, 1)) == (True, "v2")
    assert lin.superseded_at("v1", date(2026, 3, 1))[0] is False  # historical as-of date
    assert lin.superseded_at("v2", date(2026, 10, 1))[0] is False  # v3 not effective yet
    assert lin.superseded_at("v2", date(2027, 2, 1)) == (True, "v3")


def test_draft_revision_does_not_supersede():
    v1 = _doc("v1", v=1, eff=date(2026, 1, 1))
    v2 = _doc("v2", v=2, eff=date(2026, 6, 1), status="draft")
    assert Lineage([v1, v2]).superseded_at("v1", date(2026, 10, 1))[0] is False


def test_explicit_supersession_across_families():
    old = _doc("old", family="a", eff=date(2025, 1, 1))
    new = _doc("new", family="b", eff=date(2026, 1, 1), sup="old")
    lin = Lineage([old, new])
    assert lin.same_lineage("old", "new") and lin.is_ancestor("old", "new")
    assert lin.superseded_at("old", date(2026, 2, 1)) == (True, "new")


def test_chunks_are_stable_bounded_and_overlapping():
    text = "\n\n".join(f"Paragraph {i}. " + "word " * 30 for i in range(12))
    pages = [Page(1, text)]
    a = chunk_pages(pages, "sha", size=400, overlap=200)
    b = chunk_pages(pages, "sha", size=400, overlap=200)
    assert [c.id for c in a] == [c.id for c in b]
    assert all(len(c.text) <= 400 for c in a)
    assert len({c.id for c in a}) == len(a)
    # consecutive chunks share at least one paragraph (overlap)
    assert any(a[i].end_char > a[i + 1].start_char for i in range(len(a) - 1))
    assert chunk_pages(pages, "other-sha", 400, 200)[0].id != a[0].id


def test_long_paragraph_is_split():
    text = "This is a sentence. " * 100
    chunks = chunk_pages([Page(None, text)], "sha", size=300, overlap=50)
    assert len(chunks) > 3 and all(len(c.text) <= 300 for c in chunks)
