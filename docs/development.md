# Developer guide

Reference material moved out of the README: features in detail, CLI, API, evaluation commands, tests and layout.
Setup is in the [README](../README.md#quick-start).

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
* LangGraph agent with a per-node decision trace and ten verification rules (see
  [architecture.md](architecture.md)).
* A FastAPI service, a Streamlit dashboard (Overview, Knowledge Base, Ask, Conflict Center, Evaluation)
  and a CLI.
* The **VersionConflict** benchmark ([benchmark/README.md](../benchmark/README.md)) with B0 to B4 baselines,
  ablations, bootstrap confidence intervals and McNemar tests.

## CLI

The API must not have the same data folder open, because embedded Qdrant allows one process.

```powershell
.venv\Scripts\python.exe -m rag_sentinel --data-dir data/kb ingest benchmark\corpus\dev
.venv\Scripts\python.exe -m rag_sentinel --data-dir data/kb ask "How many days of annual leave do full-time employees get?"
.venv\Scripts\python.exe -m rag_sentinel --data-dir data/kb stats
```

## Docker

`Dockerfile` and `docker-compose.yml` are provided but have **not been built or tested** yet. The native
Windows setup in the README is the verified path.

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
appear on the Evaluation page. See [evaluation_report.md](evaluation_report.md) for the analysis.

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

