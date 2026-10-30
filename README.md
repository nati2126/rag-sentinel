# RAG Sentinel

A version-aware, conflict-aware reliability layer for retrieval-augmented generation.

Ordinary RAG answers from whatever text is most similar to the question. When a policy changes, the old
version, a wiki page that copied it and a draft of the next version all stay in the index, and the system
answers confidently from any of them. RAG Sentinel tracks **document versions and metadata**, extracts
**claims**, detects **contradictions and outdated references**, ranks evidence by **standing** (in force,
approved, authority, recency), and only presents an answer as **VERIFIED** when explicit evidence rules pass.
Otherwise it says **NEEDS_REVIEW** (with the conflicting sources) or **INSUFFICIENT_EVIDENCE**.

Everything runs locally at zero cost: Ollama (`qwen2.5:7b-instruct`, `nomic-embed-text`) and the
`BAAI/bge-reranker-base` cross-encoder.

## Results (held-out test split, 88 questions)

| Pipeline | Reliability [95% CI] | Stale answer rate | Unsupported answer rate | Latency p50 |
|---|---|---|---|---|
| B0 vector RAG | 83.0% [75.0, 90.9] | 22.9% | 36.8% | 1.2 s |
| B2 hybrid + rerank | 79.5% [70.5, 87.5] | 28.6% | 42.1% | 2.0 s |
| B3 + temporal / authority ranking | 90.9% [85.2, 96.6] | 5.7% | 31.6% | 2.1 s |
| **B4 RAG Sentinel** | **90.9%** [85.2, 96.6] | **0.0%** | 31.6% | 2.3 s |

What the numbers support:
* Version and authority-aware ranking removes stale answers (22.9% down to 0%).
* B4 vs B0 is +8.0 points, but that is **not significant** (McNemar p = 0.14). B4 vs B2 is +11.4 points
  (p = 0.04).
* Conflict detection and gating did **not** improve overall reliability over B3 on this test set. They
  help on contradiction questions (20% to 60%, n = 5) and remove the last stale answers, but also cause
  false reviews.
* B4 still presents an answer on 31.6% of the questions it should refuse. The relevance gate tuned on dev
  came out at 0, i.e. off.
* Corpus-level contradiction detection: precision 75% at 50% recall, against 9% precision for naive
  "values differ" detection.

Full tables, ablations, per-question failure analysis and limitations are in
[docs/evaluation_report.md](docs/evaluation_report.md).

## Features

* PDF, DOCX and Markdown ingestion with page numbers; metadata from front matter, `<file>.meta.yaml`
  sidecars or the upload form, with per-field provenance. Missing metadata is never guessed.
* Version families, duplicate detection, explicit and implicit supersession, soft delete, re-indexing,
  full audit history.
* Hybrid retrieval (dense + BM25 with reciprocal rank fusion) and cross-encoder reranking.
* Claim extraction with a JSON schema, a quote grounding check and value normalization (money, percent,
  dates, quantities with units, named versions such as TLS 1.2).
* Claim-level conflict detection: contradiction, outdated, historical, pending change, different context.
  Different values alone never count as a contradiction.
* Temporal and authority-aware evidence ranking, with historical questions ("in March 2026",
  "the previous version").
* LangGraph agent with a per-node decision trace and eight verification rules (see
  [docs/architecture.md](docs/architecture.md)).
* A FastAPI service, a Streamlit dashboard (Overview, Knowledge Base, Ask, Conflict Center, Evaluation)
  and a CLI.
* The **VersionConflict** benchmark ([benchmark/README.md](benchmark/README.md)) with B0 to B4 baselines,
  ablations, bootstrap confidence intervals and McNemar tests.

## Setup (Windows, native)

Requirements: Python 3.11, [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com), about 6 GB free
VRAM (or run the LLM on CPU, slowly).

```powershell
git clone <this repo> rag; cd rag
uv sync                                   # creates .venv (CPU PyTorch)
copy .env.example .env                    # then edit paths

# Models. Set OLLAMA_MODELS to a drive with space BEFORE pulling.
ollama pull qwen2.5:7b-instruct
ollama pull nomic-embed-text
# Reranker: set SENTINEL_HF_HOME in .env, set SENTINEL_HF_OFFLINE=false once so the first run downloads
# BAAI/bge-reranker-base (~1.1 GB), then set it back to true.
```

Run:

```powershell
.\scripts\run_api.ps1            # http://127.0.0.1:8000  (OpenAPI docs at /docs)
.\scripts\run_ui.ps1             # http://localhost:8501
```

CLI (the API must not have the same data folder open; embedded Qdrant allows one process):

```powershell
.venv\Scripts\python.exe -m rag_sentinel --data-dir data/kb ingest benchmark\corpus\dev
.venv\Scripts\python.exe -m rag_sentinel --data-dir data/kb ask "How many days of annual leave do full-time employees get?"
.venv\Scripts\python.exe -m rag_sentinel --data-dir data/kb stats
```

Docker: `Dockerfile` and `docker-compose.yml` are provided but were **not built or tested** on the
development machine. The native setup above is the verified path.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/health`, `/pipelines` | model availability, available pipelines |
| POST | `/documents` | upload a file with optional metadata (multipart) |
| GET | `/documents`, `/documents/{id}` | list, detail |
| GET | `/documents/{id}/versions`, `/history`, `/chunks`, `/claims`, `/affected` | lineage, audit trail, contents, documents still stating an old value |
| PATCH | `/documents/{id}/metadata` | correct metadata (re-runs analysis) |
| POST | `/documents/{id}/supersede`, `/documents/{id}/reindex`, `/reindex` | lifecycle |
| DELETE | `/documents/{id}` | soft delete |
| POST | `/ask` | question, optional `pipeline` and `as_of` |
| GET | `/queries` | past questions and decisions |
| GET | `/conflicts` | filter by `kind`, `status`, `actionable_only` |
| POST | `/conflicts/{id}/resolve`, `/analysis/refresh` | review workflow |
| GET | `/stats`, `/events`, `/evaluation` | dashboard data |

## Evaluation

```powershell
# 1. dev split, relevance gate off, then tune the gate on dev only
.venv\Scripts\python.exe -m evaluation.run --split dev --rebuild --force --min-relevance 0
.venv\Scripts\python.exe -m evaluation.tune
# 2. held-out test split with all baselines and ablations (about 1-2 h on an RTX 4070)
.venv\Scripts\python.exe -m evaluation.run --split test --rebuild --ablations
```

Results go to `results/` (`<split>_records.jsonl` per question, `<split>_summary.json`) and appear on the
Evaluation page. See [docs/evaluation_report.md](docs/evaluation_report.md) for the analysis.

## Tests

```powershell
.venv\Scripts\python.exe -m pytest -m "not integration"   # unit tests, test doubles only
.venv\Scripts\python.exe -m pytest -m integration         # real Ollama + reranker
```

## Project layout

```
src/rag_sentinel/   ingest/ retrieval/ claims/ conflicts/ agent/ api/ kb.py ranking.py pipelines.py
ui/                 Streamlit dashboard
benchmark/          VersionConflict corpus, questions, gold conflicts
evaluation/         runner, metrics, threshold tuning
tests/              unit (fakes) and integration (real models)
docs/               architecture, evaluation report, demo script
```

## Limitations

* Claim extraction with a 7B model misses facts and sometimes mislabels scope (for example the approver in
  "purchases above $500 need director approval"). Detection quality depends on it.
* Embedded Qdrant is single-process; use Qdrant server for concurrent writers.
* The benchmark is small (26 dev + 88 test questions) and mostly synthetic. Treat differences of a few points
  as noise; the confidence intervals in the report say how much.
* Answers are English only, and scanned PDFs (no text layer) are not supported.
