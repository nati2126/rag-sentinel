# Changelog

## Unreleased

### v0.3: real-document robustness
* **New held-out split `public_v2`.** It has 55 questions over 17 real documents: the UK State Pension, VAT
  registration and student loan pages, and the IRS HSA revenue procedures.
  * It was committed with tag `public-v2-split` before any v0.3 code change. `public_v1` is now development data.
  * Superseded GOV.UK versions are Internet Archive captures.
  * The reference date is the download date, 2026-11-27.
* **Scoped claim pairs.** When a document states several values for one attribute (a table, an enumerated
  list), each claim is compared only with the best-matching claims of the other document, by subject and
  qualifier words. Previously every value was compared with every value, which sent thousands of pairs to the
  LLM judge on public_v1.
* **Extraction keeps scope.** The extraction prompt asks for:
  * the case of an enumerated list ("(1) for medical care");
  * the row and column of a table cell;
  * the period the value applies to.

  The prompt version changes, so existing knowledge bases re-extract on re-index.
* **Citation repair.** A draft without citation markers is no longer refused outright (R4). It is cited to the
  highest-ranked passages that together contain every number it states. The answer still goes through R5–R10
  and carries a warning. Drafts with no numbers are still refused.
* **Tax years and period comparisons.** "the 2024 to 2025 tax year", "2024-25" and "between March 2024 and
  June 2025" are recognised. A question about a period that ended before the reference date runs in
  historical mode, as of the end of the latest period named.

### MCP server
* `python -m rag_sentinel.mcp` exposes six read-only tools over stdio or Streamable HTTP:
  * `ask_verified`
  * `check_statement`
  * `search_documents`
  * `list_documents`
  * `get_document_versions`
  * `list_conflicts`
* The tools reuse the B4 pipeline's retrieval, ranking and verification. They add no new answer logic.
* `check_statement` reports, for each number, which sources state it, their standing, and two kinds of flag:
  * the source is the outdated side of a detected conflict;
  * the source still states a value that a newer in-force version changed.

  The second flag catches the demo handbook's 20 days, which the conflict judge had rated `different_context`.
* Expected failures (unknown document, bad date, model server down) reach the client as readable tool errors.
* Unit tests over the in-process MCP client, plus a manual end-to-end check over stdio and HTTP with the
  real models on the demo knowledge base.

## v0.2: reliability hardening

The goal was to make the v0.1 claims defensible, not to add features.

### Evaluation protocol
* **New held-out split `test_v2`** (12 new document groups, 40 documents incl. one PDF and one DOCX, 81 questions,
  22 gold conflict pairs). It was written and committed (tag `test-v2-split`) before any v0.2 code change and was
  run only once, after development had stopped.
* **The v0.1 test split is now development data** (`test_v1`). Its failures had been analysed, so it could not
  serve as an untouched test set again. v0.1 results are kept unchanged in `results/v0.1/`.
* **T10 relabelled** in `test_v1` (VERIFIED "30 days" → NEEDS_REVIEW). The expenses group added before the v0.1
  run makes it an equal-authority contradiction. The reason is recorded in the question's `note`.
* Relevance gate tuned on dev + test_v1 pooled (114 questions instead of 26).
* Clustered bootstrap CIs (resampling document groups), raw counts next to every rate, and repeated runs with
  different sampling seeds (`--llm-temperature`, `--llm-seed`, `--tag`, `evaluation/variance.py`).

### Conflict arbitration (fixes the v0.1 "judge overrides rules" regression)
* When rules match subject, attribute and comparable values, the finding is **kept**. The LLM judge gives a second
  opinion: agreement is recorded (`detected_by = rule+llm`), disagreement is stored as `judge_opinion` and shown
  in the Conflict Center as "contested", but it never erases or downgrades the finding.
* The judge still decides pairs the rules cannot (different qualifiers, values not comparable, disjoint subjects).
* A document that states several values for one attribute signals a scope the extractor missed (e.g. "$500 needs
  a director, $10,000 the CFO"), so such pairs are no longer definite rule findings.
* One-directional "is a" subject matching (a laptop is a device; laptop vs phone stays undecided).
* Regression tests for overlapping populations, supersession, units, scope, multi-valued documents and judge
  agreement and dissent.

### Abstention
* New `check_answer` graph node and rules **R9** (the draft does not provide what the question asks for →
  INSUFFICIENT_EVIDENCE) and **R10** (statements not in the cited evidence → NEEDS_REVIEW).
* The check makes the model state what is asked and what the draft provides before its verdict (required JSON
  fields, so the grammar enforces the order). A negative verdict counts only when an independent second sample
  agrees.
* New ablation `B4-no-answer-check`.

### Robustness
* LLM retries resample with a new seed instead of echoing degenerate output, plus a token cap (`num_predict`).
* Judge failures on a pair are recorded as `insufficient_evidence` (`llm_error`) instead of aborting the analysis.
* Additive SQLite migration for new nullable columns.

### Results
Held-out `test_v2` (81 questions, single run): B4 74/81 (91.4%) vs B0 66/81 and B3 68/81. Stale 0/21, unsupported
4/23. Three sampled runs give B4 73–74/81.

Held-out `public_v1`: 44 questions over 14 real, unedited IRS and GOV.UK documents (tag `public-v1-split`), run
once with the same frozen code.
* B4 37/44, against B3 40/44 and B0 33/44.
* Stale answers 0/25.
* No wrong answer presented by B4. Its 7 failures were all refusals or review flags.
* Conflict detection found 0 of 2 gold pairs.
* Ingestion took 2 h 25 min.

Details, failure analysis and limitations are in `docs/evaluation_report.md`.

## v0.1
First complete version: ingestion, versioning, hybrid retrieval, claims, conflict detection, LangGraph agent,
FastAPI, Streamlit, and the VersionConflict benchmark. Results in `results/v0.1/` and
`docs/evaluation_report_v0.1.md`.
