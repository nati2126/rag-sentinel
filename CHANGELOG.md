# Changelog

## v0.2: reliability hardening

The goal was to make the v0.1 claims defensible, not to add features.

### Evaluation protocol
* **New held-out split `test_v2`** (12 new document groups, 40 documents incl. one PDF and one DOCX, 81 questions,
  22 gold conflict pairs). It was written and committed (`ccdaadb`) before any v0.2 code change and was
  run only once, after development had stopped.
* **The v0.1 test split is now development data** (`test_v1`). Its failures had been analysed, so it could not
  serve as an untouched test set again. v0.1 results are kept unchanged in `results/v0.1/`.
* **T10 relabelled** in `test_v1` (VERIFIED "30 days" → NEEDS_REVIEW). The expenses group added before the v0.1
  run makes it an equal-authority contradiction. The reason is recorded in the question's `note`.
* Relevance gate tuned on dev + test_v1 pooled (107 questions instead of 26).
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

## v0.1
First complete version: ingestion, versioning, hybrid retrieval, claims, conflict detection, LangGraph agent,
FastAPI, Streamlit, and the VersionConflict benchmark. Results in `results/v0.1/` and
`docs/evaluation_report_v0.1.md`.
