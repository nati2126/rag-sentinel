"""Explicit test doubles. These are used only by unit tests so they run without Ollama or model weights.

They are NOT used anywhere in the application. Integration tests (pytest -m integration) use the real models.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

import numpy as np
from pydantic import BaseModel


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder."""

    name = "test:hash"

    def __init__(self, dim: int = 256):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.stack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), dtype=np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)

    def embed_labels(self, texts: list[str]) -> np.ndarray:
        return self.embed_documents(texts)


class OverlapReranker:
    """Scores passages by query-token overlap, squashed into (0, 1)."""

    name = "test:overlap"

    def score(self, query: str, passages: list[str]) -> np.ndarray:
        q = set(re.findall(r"[a-z0-9]+", query.lower()))
        out = []
        for p in passages:
            t = set(re.findall(r"[a-z0-9]+", p.lower()))
            out.append(len(q & t) / (len(q) or 1))
        return np.asarray(out, dtype=np.float32)


class ScriptedLLM:
    """Returns responses produced by per-schema handler functions: handler(system, user) -> dict."""

    name = "test:scripted"

    def __init__(self, handlers: dict[str, Callable[[str, str], dict]]):
        self.handlers = handlers
        self.calls: list[tuple[str, str]] = []

    def chat_json(self, system: str, user: str, schema: type[BaseModel]):
        self.calls.append((schema.__name__, user))
        handler = self.handlers.get(schema.__name__)
        if handler is None:
            raise AssertionError(f"ScriptedLLM has no handler for {schema.__name__}")
        return schema.model_validate(handler(system, user))
