"""Text embeddings via Ollama (nomic-embed-text by default)."""

from __future__ import annotations

from typing import Protocol

import httpx
import numpy as np

from rag_sentinel.llm import LLMError


class Embedder(Protocol):
    name: str
    dim: int

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    def embed_query(self, text: str) -> np.ndarray: ...

    def embed_labels(self, texts: list[str]) -> np.ndarray: ...


def _normalize(m: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(m, axis=1, keepdims=True)
    return m / np.clip(norms, 1e-12, None)


class OllamaEmbedder:
    def __init__(
        self,
        base_url: str,
        model: str,
        query_prefix: str = "",
        doc_prefix: str = "",
        batch: int = 32,
        timeout: float = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = f"ollama:{model}"
        self.query_prefix = query_prefix
        self.doc_prefix = doc_prefix
        self.batch = batch
        self.client = httpx.Client(timeout=timeout)
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            self._dim = int(self._embed(["dimension probe"]).shape[1])
        return self._dim

    def _embed(self, texts: list[str]) -> np.ndarray:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch):
            try:
                r = self.client.post(
                    f"{self.base_url}/api/embed", json={"model": self.model, "input": texts[i : i + self.batch]}
                )
                r.raise_for_status()
            except httpx.HTTPError as exc:
                raise LLMError(f"Ollama embedding failed ({self.model}): {exc}") from exc
            out.extend(r.json()["embeddings"])
        return _normalize(np.asarray(out, dtype=np.float32))

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return self._embed([self.doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([self.query_prefix + text])[0]

    def embed_labels(self, texts: list[str]) -> np.ndarray:
        """Embeddings for short labels (predicate clustering). nomic uses the 'clustering:' task prefix."""
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        return self._embed(["clustering: " + t for t in texts])
