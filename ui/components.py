"""Shared UI pieces: theme CSS, status badges, document labels."""

from __future__ import annotations

import html

import streamlit as st

# Status colours are reserved for decisions and always shown with an icon + label (never colour alone).
STATUS = {
    "VERIFIED": ("#0ca30c", "check_circle", "Verified"),
    "ANSWERED": ("#52514e", "chat", "Answered (no verification)"),
    "NEEDS_REVIEW": ("#fab219", "warning", "Needs review"),
    "INSUFFICIENT_EVIDENCE": ("#d03b3b", "block", "Insufficient evidence"),
}
KIND_LABEL = {
    "contradiction": "Contradiction",
    "outdated": "Outdated reference",
    "historical": "Historical (version change)",
    "pending_change": "Pending change (draft / future)",
    "different_context": "Different context",
    "complementary": "Complementary",
    "insufficient_evidence": "Cannot compare reliably",
}
STANDING_ICON = {
    "in_force": ":material/verified:",
    "superseded": ":material/history:",
    "not_yet_effective": ":material/schedule:",
    "unapproved": ":material/edit_note:",
    "withdrawn": ":material/block:",
}

CSS = """
<style>
:root { --rs-border: rgba(11,11,11,0.10); --rs-muted: #52514e; --rs-surface: #fcfcfb; }
@media (prefers-color-scheme: dark) { :root { --rs-border: rgba(255,255,255,0.12); --rs-muted: #c3c2b7; --rs-surface: #1a1a19; } }
.block-container { padding-top: 2rem; max-width: 1200px; }
.rs-badge { display:inline-flex; align-items:center; gap:.4rem; padding:.25rem .7rem; border-radius:999px;
            font-weight:600; font-size:.9rem; border:1px solid var(--rs-border); }
.rs-dot { width:.6rem; height:.6rem; border-radius:50%; display:inline-block; }
.rs-muted { color: var(--rs-muted); font-size:.85rem; }
.rs-quote { border-left:3px solid var(--rs-border); padding:.25rem .75rem; margin:.25rem 0; font-size:.92rem; }
</style>
"""


def page_setup(title: str, subtitle: str = "") -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def status_badge(status: str) -> None:
    color, icon, label = STATUS.get(status, ("#898781", "help", status))
    st.markdown(
        f'<span class="rs-badge"><span class="rs-dot" style="background:{color}"></span>{html.escape(label)}</span>',
        unsafe_allow_html=True,
    )


def status_icon(status: str) -> str:
    return {"VERIFIED": "✅", "ANSWERED": "💬", "NEEDS_REVIEW": "⚠️", "INSUFFICIENT_EVIDENCE": "⛔"}.get(status, "•")


def doc_label(d: dict | None) -> str:
    if not d:
        return "(deleted document)"
    v = f" v{d['version']}" if d.get("version") else (f" v{d['version_label']}" if d.get("version_label") else "")
    return f"{d.get('title') or d['filename']}{v} · {d['filename']}"


def quote(text: str) -> None:
    st.markdown(f'<div class="rs-quote">{html.escape(text)}</div>', unsafe_allow_html=True)
