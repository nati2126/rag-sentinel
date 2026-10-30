"""Thin HTTP client for the RAG Sentinel API. The UI never touches the database or vector store directly."""

from __future__ import annotations

import os
from typing import Any

import httpx
import streamlit as st

API_URL = os.environ.get("SENTINEL_API_URL", "http://127.0.0.1:8000").rstrip("/")
_client = httpx.Client(base_url=API_URL, timeout=600)


class ApiError(RuntimeError):
    pass


def _handle(r: httpx.Response) -> Any:
    if r.status_code >= 400:
        try:
            detail = r.json().get("detail", r.text)
        except ValueError:
            detail = r.text
        raise ApiError(f"{r.status_code}: {detail}")
    return r.json()


def get(path: str, **params) -> Any:
    try:
        return _handle(_client.get(path, params={k: v for k, v in params.items() if v is not None}))
    except httpx.HTTPError as exc:
        raise ApiError(f"API not reachable at {API_URL} ({exc}). Start it with: scripts\\run_api.ps1") from exc


def post(path: str, json: dict | None = None, **kw) -> Any:
    try:
        return _handle(_client.post(path, json=json, **kw))
    except httpx.HTTPError as exc:
        raise ApiError(f"API not reachable at {API_URL} ({exc})") from exc


def patch(path: str, json: dict) -> Any:
    return _handle(_client.patch(path, json=json))


def delete(path: str) -> Any:
    return _handle(_client.delete(path))


def safe(fn, *args, **kwargs):
    """Call the API and show a readable error instead of a stack trace."""
    try:
        return fn(*args, **kwargs)
    except ApiError as exc:
        st.error(str(exc))
        return None
