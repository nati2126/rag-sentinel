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

## Results (v0.2, held-out `test_v2`, 81 questions, run once)

| Pipeline | Reliable | 95% CI, clustered by document group | Stale presented | Unsupported presented | Latency p50 |
|---|---|---|---|---|---|
| B0 vector RAG | 66/81 (81.5%) | [77.5, 84.8] | 5/21 | 8/23 | 1.2 s |
| B2 hybrid + rerank | 63/81 (77.8%) | [72.1, 83.7] | 6/21 | 11/23 | 2.3 s |
| B3 + temporal / authority ranking | 68/81 (84.0%) | [77.8, 90.2] | 1/21 | 11/23 | 2.4 s |
| **B4 RAG Sentinel** | **74/81 (91.4%)** | [86.2, 96.2] | **0/21** | **4/23** | 3.5 s |

What the numbers support:
* B4 vs B0: +9.9 points (10 questions better, 2 worse), clustered paired CI [+4.6, +15.7]. A real but
  modest gain on this benchmark.
* B4 vs B3: +7.4 points (8 / 2). This is borderline: the question-level CI touches 0 (McNemar p = 0.11). Ranking by
  version and authority already removes most stale answers. B4 adds abstention (unsupported 11/23 → 4/23)
  and contradiction handling (0/5 → 4/5).
* B4 still presents an answer on 4 of 23 questions it should refuse, mostly "related fact" answers to
  unanswerable questions.
* Conflict detection (rules plus LLM judge): 8 of 12 actionable gold conflicts found, 0 false positives.
* The answer check, conflict detection and reranker each change only 1–3 questions on this split. They
  are not individually significant.
* Repeated runs with sampling (3 seeds) are in the report.

The evaluation protocol, ablations, failure analysis and limitations are in
[docs/evaluation_report.md](docs/evaluation_report.md). See `CHANGELOG.md` for the v0.2 changes. v0.1 results
(a different split, since retired to development data) are in
[docs/evaluation_report_v0.1.md](docs/evaluation_report_v0.1.md).

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
# 1. development splits with the relevance gate off, then tune the gate on them (tune refuses test_v2)
.venv\Scripts\python.exe -m evaluation.run --split dev --rebuild --force --min-relevance 0 --ablations
.venv\Scripts\python.exe -m evaluation.run --split test_v1 --rebuild --force --min-relevance 0 --ablations
.venv\Scripts\python.exe -m evaluation.tune --splits dev,test_v1
# 2. held-out split, once, with the tuned gate (about 1 h on an RTX 4070)
.venv\Scripts\python.exe -m evaluation.run --split test_v2 --rebuild --ablations
# 3. repeated runs with sampling (reuse the knowledge base), then the variance table
foreach ($s in 1..3) { .venv\Scripts\python.exe -m evaluation.run --split test_v2 --pipelines B0,B3,B4 --llm-temperature 0.3 --llm-seed $s --tag "s$s" }
.venv\Scripts\python.exe -m evaluation.variance --split test_v2 --tags s1,s2,s3
.venv\Scripts\python.exe -m evaluation.report --split test_v2
```

Results go to `results/` (`<split>[__<tag>]_records.jsonl` per question, `<split>[__<tag>]_summary.json`) and
appear on the Evaluation page. See [docs/evaluation_report.md](docs/evaluation_report.md) for the analysis.

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
evaluation/         runner, metrics, threshold tuning, report and variance tables
tests/              unit (fakes) and integration (real models)
docs/               architecture, evaluation report, demo script
```

## Limitations

* The answer check (same 7B model) misses some answers that state a related fact instead of what was asked,
  and accepts partial answers to multi-part questions.
* Claim extraction with a 7B model misses facts and sometimes mislabels scope (for example the approver in
  "purchases above $500 need director approval"). Detection quality depends on it.
* Embedded Qdrant is single-process; use Qdrant server for concurrent writers.
* The benchmark is small (114 development + 81 held-out questions), synthetic, and written by the system's
  author. Treat differences of a few questions as noise; the clustered confidence intervals say how much.
* Answers are English only, and scanned PDFs (no text layer) are not supported.
