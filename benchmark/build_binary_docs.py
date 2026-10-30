"""Build the benchmark's PDF and DOCX documents from Markdown sources.

sources/<split>/<group>/<name>.<pdf|docx>.md  ->  corpus/<split>/<group>/<name>.<pdf|docx> + .meta.yaml sidecar

Front matter becomes the sidecar (metadata a user would enter at upload). Timestamps are fixed so the
output is reproducible.  Run:  python benchmark/build_binary_docs.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent / "src"))

from rag_sentinel.ingest.extract import split_front_matter  # noqa: E402

FIXED = datetime(2026, 1, 1, 0, 0, 0)


def paragraphs(body: str) -> list[str]:
    return [" ".join(p.split()) for p in body.strip().split("\n\n") if p.strip()]


def build_pdf(paras: list[str], title: str, out: Path) -> None:
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    y = 72
    for i, p in enumerate(paras):
        size = 15 if i == 0 else 11
        rect = pymupdf.Rect(72, y, 523, y + 200)
        used = page.insert_textbox(rect, p, fontsize=size, fontname="helv")
        y += (200 - used) + 14 if used >= 0 else 214
    doc.set_metadata({"title": title, "author": "", "creationDate": "D:20260101000000", "modDate": "D:20260101000000",
                      "producer": "VersionConflict benchmark", "creator": "build_binary_docs.py"})  # fmt: skip
    doc.save(out, garbage=4, deflate=True, no_new_id=True)


def build_docx(paras: list[str], title: str, out: Path) -> None:
    import docx

    d = docx.Document()
    d.add_heading(paras[0], level=1)
    for p in paras[1:]:
        d.add_paragraph(p)
    cp = d.core_properties
    cp.title, cp.author, cp.created, cp.modified, cp.last_modified_by = title, "", FIXED, FIXED, ""
    d.save(out)


def main() -> None:
    for src in sorted((ROOT / "sources").rglob("*.md")):
        rel = src.relative_to(ROOT / "sources")
        target = ROOT / "corpus" / rel.with_suffix("")  # strip trailing .md -> name.pdf / name.docx
        target.parent.mkdir(parents=True, exist_ok=True)
        front, body, _ = split_front_matter(src.read_text(encoding="utf-8"))
        paras = paragraphs(body)
        if target.suffix == ".pdf":
            build_pdf(paras, front.get("title", ""), target)
        elif target.suffix == ".docx":
            build_docx(paras, front.get("title", ""), target)
        else:
            raise SystemExit(f"unsupported target {target}")
        sidecar = target.with_name(target.name + ".meta.yaml")
        sidecar.write_text(yaml.safe_dump({k: str(v) for k, v in front.items()}, sort_keys=False), encoding="utf-8")
        print("built", target.relative_to(ROOT))


if __name__ == "__main__":
    main()
