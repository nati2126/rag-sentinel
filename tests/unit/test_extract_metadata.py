from datetime import date

import pytest

from rag_sentinel.ingest.extract import ExtractionError, extract, markdown_to_text, split_front_matter
from rag_sentinel.ingest.metadata import DocumentMetadata, merge_metadata, normalize_approval, suggest_metadata


def test_markdown_front_matter_and_text(tmp_path):
    p = tmp_path / "policy.md"
    p.write_text("---\ntitle: Leave\neffective_date: 2026-06-01\n---\n# Heading\n\nSome **bold** text.\n\n- item one\n",
                 encoding="utf-8")  # fmt: skip
    doc = extract(p)
    assert doc.content_type == "md"
    assert doc.embedded_metadata["title"] == "Leave"
    assert "Heading" in doc.text and "Some **bold** text." in doc.text and "item one" in doc.text


def test_malformed_front_matter_is_reported_not_fatal():
    meta, body, warnings = split_front_matter("---\n: : bad: [\n---\nbody")
    assert meta == {} and "body" in body and warnings


def test_markdown_tables_keep_cells():
    text = markdown_to_text("| Item | Limit |\n|---|---|\n| Meals | $60 |\n")
    assert "Meals | $60" in text


def test_pdf_text_and_metadata(tmp_path):
    import pymupdf

    p = tmp_path / "a.pdf"
    d = pymupdf.open()
    d.new_page().insert_text((72, 72), "Per diem is $60 per day.")
    d.new_page().insert_text((72, 72), "Second page.")
    d.set_metadata({"title": "Travel Policy", "author": "Finance", "creationDate": "D:20260301120000"})
    d.save(p)
    doc = extract(p)
    assert [pg.number for pg in doc.pages] == [1, 2]
    assert "$60" in doc.pages[0].text
    assert doc.file_metadata == {"title": "Travel Policy", "created_date": "2026-03-01", "source_org": "Finance"}


def test_docx_text_tables_and_core_properties(tmp_path):
    import docx

    p = tmp_path / "a.docx"
    d = docx.Document()
    d.add_paragraph("Laptops are replaced every 4 years.")
    t = d.add_table(rows=1, cols=2)
    t.rows[0].cells[0].text, t.rows[0].cells[1].text = "Monitor", "6 years"
    d.core_properties.title = "Hardware Standard"
    d.save(p)
    doc = extract(p)
    assert "4 years" in doc.text and "Monitor | 6 years" in doc.text
    assert doc.file_metadata["title"] == "Hardware Standard"


def test_corrupt_and_unsupported_files_raise_clear_errors(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(ExtractionError):
        extract(bad)
    with pytest.raises(ExtractionError, match="Unsupported"):
        extract(tmp_path / "x.xlsx")


def test_merge_precedence_and_provenance():
    meta, sources = merge_metadata([
        ("file", {"title": "From PDF", "created_date": "2026-01-01"}),
        ("front_matter", {"title": "From front matter", "authority_level": 3}),
        ("user", {"authority_level": "5", "approval_status": "Final"}),
    ])  # fmt: skip
    assert meta.title == "From front matter" and sources["title"] == "front_matter"
    assert meta.authority_level == 5 and sources["authority_level"] == "user"
    assert meta.approval_status == "approved"
    assert meta.created_date == date(2026, 1, 1) and meta.effective_date is None  # missing stays missing


def test_invalid_authority_rejected():
    with pytest.raises(ValueError):
        DocumentMetadata(authority_level=9)


def test_approval_aliases():
    assert normalize_approval("Under Review") == "pending"
    assert normalize_approval("whatever") == "unknown"


def test_suggestions_are_separate_from_trusted_metadata():
    s = suggest_metadata("Travel Policy. Version 3.1. This policy is effective from June 1, 2026.")
    assert s == {"effective_date": "2026-06-01", "version": "3.1"}
