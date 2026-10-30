"""Cross-encoder reranker (BAAI/bge-reranker-base by default). Loaded lazily on first use."""

from __future__ import annotations

from typing import Protocol

import numpy as np

from rag_sentinel.log import get_logger

log = get_logger(__name__)


class Reranker(Protocol):
    name: str

    def score(self, query: str, passages: list[str]) -> np.ndarray:
        """Relevance probabilities in [0, 1], one per passage."""
        ...


class CrossEncoderReranker:
    def __init__(self, model_name: str, device: str = "cpu", max_length: int = 512):
        self.model_name = model_name
        self.name = model_name
        self.device = device
        self.max_length = max_length
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder  # heavy import; deferred

            log.info("loading reranker", extra={"model": self.model_name, "device": self.device})
            self._model = CrossEncoder(self.model_name, device=self.device, max_length=self.max_length)
        return self._model

    def score(self, query: str, passages: list[str]) -> np.ndarray:
        if not passages:
            return np.zeros(0, dtype=np.float32)
        model = self._load()
        logits = model.predict([(query, p) for p in passages], batch_size=16, activation_fn=_identity)
        return 1.0 / (1.0 + np.exp(-np.asarray(logits, dtype=np.float32)))  # explicit sigmoid -> [0, 1]


def _identity(x):  # noqa: ANN001, ANN202 - torch tensor in, tensor out
    return x
