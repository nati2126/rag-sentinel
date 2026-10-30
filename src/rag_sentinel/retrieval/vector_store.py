"""Qdrant in embedded (local, file-based) mode: no server process needed."""

from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
from qdrant_client import QdrantClient, models

COLLECTION = "chunks"


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class VectorStore:
    def __init__(self, path: Path | str):
        # Embedded Qdrant locks its folder: only one process may open it. The UI therefore goes through the API.
        self.client = QdrantClient(":memory:") if str(path) == ":memory:" else QdrantClient(path=str(path))
        self._dim: int | None = None

    def ensure_collection(self, dim: int) -> None:
        if self._dim == dim:
            return
        if not self.client.collection_exists(COLLECTION):
            self.client.create_collection(
                COLLECTION, vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE)
            )
        else:
            existing = self.client.get_collection(COLLECTION).config.params.vectors.size
            if existing != dim:
                raise ValueError(
                    f"Vector collection has dim {existing} but the embedder produces {dim}. "
                    "Changing the embedding model requires a full reindex (delete data dir or POST /reindex?reset=true)."
                )
        self._dim = dim

    def upsert(self, chunk_ids: list[str], doc_ids: list[str], vectors: np.ndarray) -> None:
        if not chunk_ids:
            return
        self.ensure_collection(int(vectors.shape[1]))
        points = [
            models.PointStruct(id=point_id(c), vector=v.tolist(), payload={"chunk_id": c, "doc_id": d})
            for c, d, v in zip(chunk_ids, doc_ids, vectors, strict=True)
        ]
        self.client.upsert(COLLECTION, points=points, wait=True)

    def delete_document(self, doc_id: str) -> None:
        if not self.client.collection_exists(COLLECTION):
            return
        flt = models.Filter(must=[models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id))])
        self.client.delete(COLLECTION, points_selector=models.FilterSelector(filter=flt), wait=True)

    def reset(self) -> None:
        if self.client.collection_exists(COLLECTION):
            self.client.delete_collection(COLLECTION)
        self._dim = None

    def count(self) -> int:
        if not self.client.collection_exists(COLLECTION):
            return 0
        return self.client.count(COLLECTION).count

    def search(self, vector: np.ndarray, k: int) -> list[tuple[str, float]]:
        if not self.client.collection_exists(COLLECTION):
            return []
        res = self.client.query_points(COLLECTION, query=vector.tolist(), limit=k, with_payload=True)
        return [(p.payload["chunk_id"], float(p.score)) for p in res.points]

    def close(self) -> None:
        self.client.close()
