# RAG Sentinel API + UI image (CPU). Ollama runs in its own container (see docker-compose.yml).
# NOTE: not built or tested on the development machine (Docker Desktop's disk is on a full C: drive).
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY ui ./ui
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    SENTINEL_DATA_DIR=/data/kb \
    SENTINEL_HF_HOME=/models/hf
EXPOSE 8000 8501
CMD ["uvicorn", "rag_sentinel.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
