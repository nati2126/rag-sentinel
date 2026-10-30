"""Text + file-level metadata extraction for PDF, DOCX and Markdown.

Only metadata that is actually present in the file is returned. Nothing is guessed here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

SUPPORTED = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".markdown": "md"}


class ExtractionError(Exception):
    """Raised when a file cannot be read. The message is safe to show to users."""


@dataclass
class Page:
    number: int | None  # 1-based page for PDFs, None for formats without pages
    text: str


@dataclass
class ExtractedDocument:
    content_type: str
    pages: list[Page]
    file_metadata: dict[str, Any] = field(default_factory=dict)  # from the file container (PDF info, DOCX core props)
    embedded_metadata: dict[str, Any] = field(default_factory=dict)  # Markdown front matter
    warnings: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


def detect_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED:
        raise ExtractionError(f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(SUPPORTED))}")
    return SUPPORTED[ext]


def extract(path: Path, filename: str | None = None) -> ExtractedDocument:
    kind = detect_type(filename or path.name)
    try:
        if kind == "pdf":
            doc = _extract_pdf(path)
        elif kind == "docx":
            doc = _extract_docx(path)
        else:
            doc = _extract_markdown(path.read_bytes())
    except ExtractionError:
        raise
    except Exception as exc:  # corrupt or unreadable files
        raise ExtractionError(f"Could not read {kind.upper()} file: {exc}") from exc
    if not doc.text.strip():
        doc.warnings.append("No extractable text (scanned PDF or empty file?). OCR is not supported.")
    return doc


# --- PDF -------------------------------------------------------------------

_PDF_DATE = re.compile(r"D:(\d{4})(\d{2})?(\d{2})?")


def _pdf_date(raw: str | None) -> str | None:
    if not raw:
        return None
    m = _PDF_DATE.match(raw)
    if not m:
        return None
    y, mo, d = m.group(1), m.group(2) or "01", m.group(3) or "01"
    return f"{y}-{mo}-{d}"


def _extract_pdf(path: Path) -> ExtractedDocument:
    import pymupdf

    with pymupdf.open(path) as pdf:
        if pdf.needs_pass:
            raise ExtractionError("PDF is password-protected.")
        pages = [Page(number=i + 1, text=page.get_text("text").strip()) for i, page in enumerate(pdf)]
        info = pdf.metadata or {}
    meta = {
        "title": (info.get("title") or "").strip() or None,
        "created_date": _pdf_date(info.get("creationDate")),
        "last_modified": _pdf_date(info.get("modDate")),
        "source_org": (info.get("author") or "").strip() or None,
    }
    return ExtractedDocument("pdf", pages, file_metadata={k: v for k, v in meta.items() if v})


# --- DOCX ------------------------------------------------------------------


def _extract_docx(path: Path) -> ExtractedDocument:
    import docx

    d = docx.Document(str(path))
    blocks = [p.text.strip() for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))
    cp = d.core_properties
    meta = {
        "title": (cp.title or "").strip() or None,
        "created_date": cp.created.date().isoformat() if cp.created else None,
        "last_modified": cp.modified.date().isoformat() if cp.modified else None,
        "source_org": (cp.author or "").strip() or None,
        "version": (cp.version or "").strip() or None,
    }
    return ExtractedDocument(
        "docx", [Page(None, "\n\n".join(blocks))], file_metadata={k: v for k, v in meta.items() if v}
    )


# --- Markdown --------------------------------------------------------------

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_front_matter(text: str) -> tuple[dict[str, Any], str, list[str]]:
    m = _FRONT_MATTER.match(text)
    if not m:
        return {}, text, []
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        return {}, text[m.end() :], [f"Ignored malformed front matter: {exc}"]
    if not isinstance(data, dict):
        return {}, text[m.end() :], ["Ignored front matter that is not a mapping"]
    return data, text[m.end() :], []


def markdown_to_text(md: str) -> str:
    """Render Markdown to plain text, keeping headings, list items and table cells as separate lines."""
    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").enable("table").parse(md)
    lines: list[str] = []
    row: list[str] = []
    in_row = False
    for tok in tokens:
        if tok.type == "tr_open":
            in_row, row = True, []
        elif tok.type == "tr_close":
            in_row = False
            lines.append(" | ".join(row))
        elif tok.type == "inline":
            if in_row:
                row.append(tok.content.strip())
            else:
                lines.append(tok.content.strip())
        elif tok.type in ("paragraph_close", "heading_close", "bullet_list_close", "ordered_list_close"):
            lines.append("")
        elif tok.type in ("fence", "code_block"):
            lines.append(tok.content.rstrip())
    text = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _extract_markdown(raw: bytes) -> ExtractedDocument:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    front, body, warnings = split_front_matter(text)
    return ExtractedDocument("md", [Page(None, markdown_to_text(body))], embedded_metadata=front, warnings=warnings)
