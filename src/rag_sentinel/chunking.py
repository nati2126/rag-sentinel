"""Paragraph-aware chunking with overlap and stable chunk ids."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from rag_sentinel.ingest.extract import Page


@dataclass(frozen=True)
class ChunkSpan:
    id: str
    seq: int
    page: int | None
    start_char: int  # offsets into the page text
    end_char: int
    text: str


def chunk_id(doc_sha256: str, page: int | None, start: int, end: int) -> str:
    """Same file + same chunking parameters -> same id, so re-indexing is idempotent."""
    return hashlib.sha256(f"{doc_sha256}:{page}:{start}:{end}".encode()).hexdigest()[:20]


_PARA = re.compile(r"\n\s*\n")
_SENT = re.compile(r"(?<=[.!?])\s+")


def _segments(text: str, max_len: int) -> list[tuple[int, int]]:
    """Split into paragraph spans; paragraphs longer than max_len are split on sentences, then hard-cut."""
    spans: list[tuple[int, int]] = []
    pos = 0
    for m in list(_PARA.finditer(text)) + [None]:
        end = m.start() if m else len(text)
        if text[pos:end].strip():
            spans.extend(_split_long(text, pos, end, max_len))
        if m:
            pos = m.end()
    return spans


def _split_long(text: str, start: int, end: int, max_len: int) -> list[tuple[int, int]]:
    if end - start <= max_len:
        return [(start, end)]
    out: list[tuple[int, int]] = []
    cur = start
    for m in _SENT.finditer(text, start, end):
        if m.start() - cur >= max_len:
            out.append((cur, m.start()))
            cur = m.end()
    out.append((cur, end))
    final: list[tuple[int, int]] = []
    for s, e in out:  # hard cut anything that is still too long (e.g. a table without punctuation)
        while e - s > max_len:
            final.append((s, s + max_len))
            s += max_len
        if e > s:
            final.append((s, e))
    return final


def chunk_pages(pages: list[Page], doc_sha256: str, size: int = 900, overlap: int = 150) -> list[ChunkSpan]:
    if overlap >= size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    chunks: list[ChunkSpan] = []
    for page in pages:
        text = page.text
        segs = _segments(text, size)
        i = 0
        while i < len(segs):
            start = segs[i][0]
            end = segs[i][1]
            j = i + 1
            while j < len(segs) and segs[j][1] - start <= size:
                end = segs[j][1]
                j += 1
            body = text[start:end].strip()
            if body:
                chunks.append(
                    ChunkSpan(chunk_id(doc_sha256, page.number, start, end), len(chunks), page.number, start, end, body)
                )
            if j >= len(segs):
                break
            # Overlap: restart at the last segments that fit inside `overlap` characters.
            k = j
            while k - 1 > i and end - segs[k - 1][0] <= overlap:
                k -= 1
            i = k if k > i else j
    return chunks
