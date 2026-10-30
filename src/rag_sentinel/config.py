"""Application settings, loaded from environment variables (prefix SENTINEL_) or a .env file."""

from __future__ import annotations

import os
from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class RankingWeights(BaseModel):
    """Weights for evidence ranking (see ranking.py). Factors are each scaled to [0, 1]."""

    relevance: float = 0.45
    authority: float = 0.25
    approval: float = 0.15
    recency: float = 0.15
    # Multipliers applied to evidence that is not in force at the as-of date.
    superseded_factor: float = 0.25
    not_yet_effective_factor: float = 0.35
    withdrawn_factor: float = 0.1
    # Draft / pending documents: a weighted sum alone lets relevance + recency outvote approval status.
    unapproved_factor: float = 0.5


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SENTINEL_", env_file=".env", env_nested_delimiter="__", extra="ignore"
    )

    data_dir: Path = Path("data/kb")
    log_level: str = "INFO"

    # Local LLM (Ollama)
    ollama_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen2.5:7b-instruct"
    llm_num_ctx: int = 8192
    llm_temperature: float = 0.0
    llm_timeout_s: float = 300.0

    # Embeddings (Ollama). nomic-embed-text expects task prefixes.
    embed_model: str = "nomic-embed-text"
    embed_query_prefix: str = "search_query: "
    embed_doc_prefix: str = "search_document: "
    embed_batch: int = 32

    # Cross-encoder reranker (sentence-transformers, CPU by default: the GPU belongs to the LLM)
    reranker_model: str = "BAAI/bge-reranker-base"
    reranker_device: str = "cpu"
    hf_home: Path | None = None
    hf_offline: bool = True

    # Chunking
    chunk_size: int = 900
    chunk_overlap: int = 150

    # Retrieval
    dense_k: int = 20
    bm25_k: int = 20
    rrf_k: int = 60
    rerank_candidates: int = 20
    final_k: int = 5
    # Minimum reranker probability for the top passage before we consider evidence relevant at all.
    min_relevance: float = 0.05

    # Claims / conflicts
    predicate_similarity: float = 0.86
    authority_margin: float = 0.12
    use_llm_conflict_judge: bool = True

    ranking: RankingWeights = RankingWeights()

    # Reference date for "is this document in force?". None = today. Fixed in benchmarks for reproducibility.
    as_of: date | None = None

    # Streamlit -> API
    api_url: str = "http://127.0.0.1:8000"
    # Experiment outputs served on the Evaluation page
    results_dir: Path = Path("results")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "sentinel.db"

    @property
    def qdrant_path(self) -> Path:
        return self.data_dir / "qdrant"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    def reference_date(self) -> date:
        return self.as_of or date.today()

    def apply_hf_env(self) -> None:
        """Point Hugging Face at the configured cache *before* sentence-transformers is imported."""
        if self.hf_home:
            os.environ["HF_HOME"] = str(self.hf_home)
        if self.hf_offline:
            os.environ["HF_HUB_OFFLINE"] = "1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
