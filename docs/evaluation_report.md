# Evaluation report v0.2: VersionConflict benchmark

v0.2 is a reliability-hardening release (see `CHANGELOG.md`). This report covers the **held-out `test_v2`
split, run once**, a second held-out split of **real, unedited IRS and UK government documents (`public_v1`),
also run once**, and the development results that informed v0.2. The v0.1 report is kept unchanged in
`docs/evaluation_report_v0.1.md`.

All tables were rendered by `python -m evaluation.report` and `python -m evaluation.variance` from
`results/*.json`. Nothing was edited by hand. Hardware: Windows 11, RTX 4070 8 GB, local Ollama
(`qwen2.5:7b-instruct`, `nomic-embed-text`), `BAAI/bge-reranker-base` on CPU.

## Protocol

| Split | Role in v0.2 | Questions | Documents / groups | Notes |
|---|---|---|---|---|
| `dev` | development | 26 | 14 / 3 | used since v0.1 |
| `test_v1` | development | 88 | 44 / 13 | the v0.1 test split. Its failures were analysed after v0.1, so it is no longer held out. T10 relabelled (see CHANGELOG) |
| `test_v2` | **held out** | 81 | 40 / 12 (+2 leakage-check questions) | written and committed (tag `test-v2-split`) before any v0.2 code change, run once after development stopped |
| `public_v1` | **held out** | 44 | 14 / 4 | real IRS and GOV.UK documents, unedited. Questions committed (tag `public-v1-split`) before its single run, with the same frozen code |

* **Freeze.** Code, prompts and the tuned threshold were committed (tag `v0.2-freeze`) before the `test_v2` run. No change was
  made after it.
* **What was tuned, and on what.** The answer-check prompt (3 iterations), the arbitration rules and the
  relevance gate were all developed and tuned on `dev` + `test_v1` only. `evaluation/tune.py` refuses `test_v2`.
* **Who wrote `test_v2`.** The same author as the system, who knew the v0.1 failure modes. It follows the same
  annotation guideline (`benchmark/README.md`) and was written before v0.2 development. It contains the kinds
  of traps v0.1 failed on (questions answerable only with a related fact, overlapping populations, multi-chunk
  documents), so it is not an easier test. It is also not independent of the author.
* **Reference date.** 2026-10-01, unless a question names a date.
* **Primary run.** Temperature 0, seed 7, deterministic.
* **Repeated runs.** Three further runs at temperature 0.3 with seeds 1, 2 and 3, for B0, B3 and B4. They vary
  answer generation. Ingestion, claims and cached judge verdicts are shared. Answer-check verdicts are cached by
  (question, draft, evidence), so a sampled draft identical to an earlier one reuses its check verdict. This
  measures generation variability. It understates answer-check and extraction variability.
* **Statistics.**
  * Percentile bootstrap (2000 resamples) over questions.
  * The same bootstrap **clustered by document group** (questions about the same documents are correlated).
  * Paired versions of both for differences against B4.
  * The exact McNemar test, which assumes independent questions and is therefore optimistic.
  * Raw counts next to every rate.

## Headline results (test_v2, held out, single run)

| Pipeline | Reliable | Stale presented | Unsupported presented | Over-abstained |
|---|---|---|---|---|
| B0 vector RAG | 66/81 (81.5%) | 5/21 | 8/23 | 1/58 |
| B3 + temporal / authority ranking | 68/81 (84.0%) | 1/21 | 11/23 | 0/58 |
| **B4 RAG Sentinel** | **74/81 (91.4%)** | **0/21** | **4/23** | 2/58 |

*Reliable* means a correct answer presented as reliable, or a correct abstention. *Unsupported presented* counts
answers presented on the 23 questions whose gold decision is to abstain (18 unanswerable, 5 needing review).

What the numbers support:

* **B4 vs B0: +9.9 points (10 questions better, 2 worse).** Clustered paired 95% CI [+4.6, +15.7]. McNemar
  p = 0.039, but McNemar assumes independent questions. The clustered interval is the more honest statement:
  a real but modest gain on this benchmark.
* **B4 vs B3: +7.4 points (8 better, 2 worse).** Clustered CI [+1.4, +12.0], but the question-level CI touches
  0 and McNemar p = 0.11. Treat it as **borderline**. B3 already removes most stale answers. What B4 adds is
  mostly abstention (unsupported 11/23 → 4/23) and contradiction handling (0/5 → 4/5).
* **Stale answers: 0/21 for B4,** against 5/21 for B0 and 1/21 for B3. One of three sampled runs had 1/21 (see
  Repeated runs).
* **Unanswerable questions are still the main weakness.** B4 presents an answer on 4 of 23 abstain-questions
  (17%). In v0.1, on a different split, it was 6/19 (32%). This is better but not solved.
* **The v0.1 judge-override regression is fixed.** On test_v2, rules plus judge find 8 of 12 actionable gold
  conflicts with 0 false positives, against 7/12 for rules alone. In v0.1 the judge made detection worse.
* **Small components are not individually significant on this split.**
  * Answer check: +2.5 points, 2/0 questions.
  * Conflict detection: +1.2 points, 6/5 questions. It fixes contradictions but costs false reviews.
  * Reranker: +3.7 points, 3/0.
  * They should not be presented as proven contributions.
* **Relevance gate is off.** Tuning on dev + test_v1 chose `min_relevance = 0.0`: reliability was flat at 95.6%
  from 0 to 0.038 and only fell above that. With the answer check, the gate added nothing on development data.
  The tie rule (lowest threshold wins) was fixed in `tune.py` before tuning, and the result was kept as is.

## Comparison with v0.1

The v0.1 numbers (B4 80/88 = 90.9%, unsupported 6/19) are from a different split. There is no run of the
v0.1 code on `test_v2`, so **the v0.1 → v0.2 difference on held-out data is not measured**. What can be compared
on the same split:

* **`B4-no-answer-check` approximates v0.2 without the new abstention step:** 72/81, unsupported 6/23. It still
  contains the arbitration fix.
* **Conflict detection with the judge vs rules only** isolates the arbitration fix: 8/0/4 vs 7/0/5 TP/FP/FN.

On `test_v1`, which is now development data and was used to tune the answer-check prompt, v0.2 B4 scores 85/88
(96.6%) against 80/88 for v0.1. That gain is **not** evidence of generalization, because `test_v1` failures
were studied while v0.2 was built.

## Full tables (test_v2)

### Answer reliability

| Pipeline | Reliable | 95% CI (questions) | 95% CI (clustered by group) | Correct answers | Stale answers | Unsupported answers | Over-abstained | Decision acc. | Latency p50/p95 s |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 66/81 (81.5%) | [72.8%, 88.9%] | [77.5%, 84.8%] | 51/58 | 5/21 | 8/23 | 1/58 | 88.9% | 1.2 / 1.9 |
| B1 | 60/81 (74.1%) | [64.2%, 82.7%] | [68.3%, 79.5%] | 49/58 | 6/21 | 12/23 | 2/58 | 82.7% | 1.2 / 1.7 |
| B2 | 63/81 (77.8%) | [69.1%, 86.4%] | [72.1%, 83.7%] | 51/58 | 6/21 | 11/23 | 0/58 | 86.4% | 2.3 / 3.2 |
| B3 | 68/81 (84.0%) | [75.3%, 91.4%] | [77.8%, 90.2%] | 56/58 | 1/21 | 11/23 | 0/58 | 86.4% | 2.4 / 3.1 |
| B4 | 74/81 (91.4%) | [85.2%, 96.3%] | [86.2%, 96.2%] | 55/58 | 0/21 | 4/23 | 2/58 | 92.6% | 3.5 / 4.1 |
| B4-no-rerank | 71/81 (87.6%) | [80.2%, 93.8%] | [82.3%, 93.2%] | 52/58 | 0/21 | 4/23 | 5/58 | 88.9% | 2.3 / 3.4 |
| B4-relevance-ranking | 71/81 (87.6%) | [80.2%, 93.8%] | [82.7%, 92.7%] | 52/58 | 1/21 | 4/23 | 4/58 | 88.9% | 3.4 / 4.9 |
| B4-newest-wins | 68/81 (84.0%) | [75.3%, 91.4%] | [78.8%, 89.1%] | 49/58 | 2/21 | 4/23 | 7/58 | 86.4% | 2.8 / 4.4 |
| B4-no-conflicts | 73/81 (90.1%) | [82.7%, 96.3%] | [85.4%, 94.9%] | 56/58 | 1/21 | 6/23 | 0/58 | 92.6% | 2.6 / 4.3 |
| B4-no-gating | 69/81 (85.2%) | [76.5%, 92.6%] | [80.4%, 90.2%] | 56/58 | 1/21 | 10/23 | 0/58 | 87.6% | 2.5 / 3.1 |
| B4-no-answer-check | 72/81 (88.9%) | [81.5%, 95.1%] | [83.8%, 93.8%] | 55/58 | 0/21 | 6/23 | 2/58 | 90.1% | 2.3 / 3.0 |

Clustered intervals resample the 13 document groups, because questions about the same documents are correlated.

### Retrieval and grounding

| Pipeline | Recall@5 | MRR@5 | Citation precision | Numeric faithfulness | Abstention precision | Abstention recall |
|---|---|---|---|---|---|---|
| B0 | 99.2% | 83.1% | 73.6% | 100.0% | 93.8% | 65.2% |
| B1 | 100.0% | 84.4% | 73.2% | 100.0% | 84.6% | 47.8% |
| B2 | 100.0% | 90.0% | 71.0% | 100.0% | 100.0% | 52.2% |
| B3 | 100.0% | 98.2% | 89.4% | 100.0% | 100.0% | 52.2% |
| B4 | 100.0% | 98.2% | 89.2% | 100.0% | 90.5% | 82.6% |
| B4-no-rerank | 96.8% | 84.0% | 93.1% | 100.0% | 79.2% | 82.6% |
| B4-relevance-ranking | 100.0% | 90.0% | 77.5% | 100.0% | 82.6% | 82.6% |
| B4-newest-wins | 93.7% | 82.7% | 81.0% | 92.8% | 73.1% | 82.6% |
| B4-no-conflicts | 100.0% | 98.2% | 92.3% | 100.0% | 100.0% | 73.9% |
| B4-no-gating | 100.0% | 98.2% | 88.1% | 100.0% | 100.0% | 56.5% |
| B4-no-answer-check | 100.0% | 98.2% | 89.2% | 100.0% | 89.5% | 73.9% |

### Reliability by category

| Pipeline | contradiction (n=5) | historical (n=7) | multi_doc (n=5) | normal (n=34) | outdated (n=12) | unanswerable (n=18) |
|---|---|---|---|---|---|---|
| B0 | 0.0% | 42.9% | 80.0% | 100.0% | 83.3% | 83.3% |
| B1 | 0.0% | 14.3% | 80.0% | 100.0% | 83.3% | 61.1% |
| B2 | 0.0% | 57.1% | 60.0% | 100.0% | 83.3% | 66.7% |
| B3 | 0.0% | 100.0% | 60.0% | 100.0% | 100.0% | 66.7% |
| B4 | 80.0% | 85.7% | 80.0% | 97.1% | 100.0% | 83.3% |
| B4-no-rerank | 80.0% | 71.4% | 80.0% | 94.1% | 91.7% | 83.3% |
| B4-relevance-ranking | 80.0% | 71.4% | 60.0% | 97.1% | 91.7% | 83.3% |
| B4-newest-wins | 80.0% | 28.6% | 80.0% | 97.1% | 83.3% | 83.3% |
| B4-no-conflicts | 20.0% | 100.0% | 60.0% | 100.0% | 100.0% | 88.9% |
| B4-no-gating | 0.0% | 85.7% | 80.0% | 100.0% | 100.0% | 72.2% |
| B4-no-answer-check | 80.0% | 85.7% | 80.0% | 97.1% | 100.0% | 72.2% |

### Paired comparison with B4 (reliability)

| vs | B4 minus pipeline | 95% CI (paired) | 95% CI (paired, clustered) | B4 better / worse | McNemar p (assumes independent questions) |
|---|---|---|---|---|---|
| B0 | +9.9% | [+2.5%, +18.5%] | [+4.6%, +15.7%] | 10 / 2 | 0.0386 |
| B1 | +17.3% | [+8.6%, +25.9%] | [+10.5%, +25.0%] | 15 / 1 | 0.0005 |
| B2 | +13.6% | [+6.2%, +22.2%] | [+6.6%, +20.5%] | 12 / 1 | 0.0034 |
| B3 | +7.4% | [+0.0%, +14.8%] | [+1.4%, +12.0%] | 8 / 2 | 0.109 |
| B4-no-rerank | +3.7% | [+0.0%, +8.6%] | [+0.0%, +7.5%] | 3 / 0 | 0.25 |
| B4-relevance-ranking | +3.7% | [-2.5%, +9.9%] | [-2.4%, +10.1%] | 5 / 2 | 0.453 |
| B4-newest-wins | +7.4% | [+0.0%, +14.8%] | [+0.0%, +14.5%] | 8 / 2 | 0.109 |
| B4-no-conflicts | +1.2% | [-6.2%, +9.9%] | [-5.1%, +7.5%] | 6 / 5 | 1 |
| B4-no-gating | +6.2% | [+0.0%, +12.3%] | [+2.2%, +10.7%] | 6 / 1 | 0.125 |
| B4-no-answer-check | +2.5% | [+0.0%, +6.2%] | [+0.0%, +6.1%] | 2 / 0 | 0.5 |

### Conflict detection (corpus level, 12 actionable gold pairs of 22)

| Detector | Precision | Recall | F1 | TP/FP/FN | Kind acc. (matched) | Gold pairs found |
|---|---|---|---|---|---|---|
| naive value difference | 26.5% | 75.0% | 39.1% | 9/25/3 | 23.5% | 17/22 |
| rules only | 100.0% | 58.3% | 73.7% | 7/0/5 | 76.5% | 17/22 |
| rules plus llm judge | 100.0% | 66.7% | 80.0% | 8/0/4 | 94.1% | 17/22 |

Missed (full detector): it_ops_runbook.md vs access_control_standard_v3.md (privileged access review); data_classification_policy.md vs records_management_standard.md (classification review); code_of_conduct_2024.md vs speak_up_policy.docx (report acknowledgement); build_pipeline_notes.md vs crypto_library_standard_2026.md (checksum algorithm)

Detected kinds: {'complementary': 1, 'contradiction': 4, 'different_context': 12, 'historical': 7, 'outdated': 4, 'pending_change': 3}

Ingestion: 40 documents, 41 chunks, 117 claims accepted, 6 rejected by the grounding check, 226 s.


## Repeated runs (temperature 0.3, seeds 1–3)

Repeated runs on **test_v2**: s1 (temperature 0.3, seed 1), s2 (temperature 0.3, seed 2), s3 (temperature 0.3, seed 3)

| Pipeline | Reliability | Stale rate | Unsupported rate | Over-abstention | Reliable per run |
|---|---|---|---|---|---|
| B0 | 82.3% ± 0.7% (81.5% to 82.7%) | 22.2% ± 2.7% (19.1% to 23.8%) | 34.8% ± 0.0% (34.8% to 34.8%) | 1.7% ± 0.0% (1.7% to 1.7%) | 66/81, 67/81, 67/81 |
| B3 | 84.8% ± 0.7% (84.0% to 85.2%) | 4.8% ± 0.0% (4.8% to 4.8%) | 44.9% ± 2.5% (43.5% to 47.8%) | 0.0% ± 0.0% (0.0% to 0.0%) | 69/81, 68/81, 69/81 |
| B4 | 90.9% ± 0.7% (90.1% to 91.4%) | 1.6% ± 2.7% (0.0% to 4.8%) | 17.4% ± 0.0% (17.4% to 17.4%) | 3.5% ± 0.0% (3.5% to 3.5%) | 74/81, 74/81, 73/81 |

Run-to-run variation from sampling is small next to the differences between pipelines. B4 scores 73–74/81 in every
run, B3 68–69 and B0 66–67. The order B4 > B3 > B0 holds in every run.

One new failure appeared under sampling. In seed 3, B4 answered V72 (multi-part) with the privileged-access review
interval from `it_ops_runbook.md`, a stale copy, alongside the in-force standard. That pair is one of the four gold
conflicts the detector misses, so nothing flagged it. At temperature 0 the generator chose the in-force value. **Zero
stale answers is therefore a property of this run, not a guarantee.** Conflict detection recall bounds it.

These runs re-sample generation only (see the protocol notes).

## Failure analysis (B4 on test_v2, 7 of 81)

Five failures presented a wrong answer as VERIFIED. Two were over-cautious refusals.

| Question | Type | What happened |
|---|---|---|
| V30, V59, V75 | unanswerable, related fact | The documents cover a nearby fact: backups go to "a second data centre", not a cloud region; a minimum OpenSSL version is required, not an installed one; there is a weekly on-call allowance, not a holiday rate. The generator answered with that fact. The answer check accepted it in V30 and V59. In V75 it accepted an answer that even says "which would apply to public holidays as well". This is the failure mode the answer check was built for. On test_v2 it caught 2 of 5 such drafts (V47 vendor software, V76 contractor study leave: R9) and rejected no correct answer. |
| V18 | missed contradiction | Classification review every 24 months (policy) vs every 12 months (records standard). The claim extractor did not produce comparable claims for the pair, so neither rules nor judge saw it. It is one of the 4 missed gold pairs. |
| V22 | partial multi-part answer | The draft answers "can it be e-mailed" (no) but not "how must it be protected" (encrypted in transit). The answer check judges whether the draft answers the question, and accepted a partial answer. |
| V41 | safe refusal (R6) | Historical question (2025). The generator cited the 2026 speak-up policy (7 days) instead of the 2024 code of conduct (14 days). R6 blocked it because that source was not in force in 2025, so nothing wrong was presented. |
| V62 | false review (R7) | The CCTV answer "30 days" was blocked by an unrelated open contradiction (backup retention, 35 vs 30 days) that shares the value 30 and lives in the same retrieved document. R7 matches conflicts by value as well as by attribute, which is too loose here. |

The v0.2 code was frozen before this run, so none of these were fixed. They are the starting list for v0.3.

## Real documents (public_v1, held out, single run)

`test_v2` is synthetic and self-authored. `public_v1` checks whether the results carry over to real documents.

**Corpus.** It has 14 unedited documents in 4 groups:
* IRS standard mileage rates for 2024–2026: three notices, the mid-2026 revision Announcement 2026-11, a news
  release and the rates page.
* IRS 2024–2026 retirement plan limits: three notices and a news release.
* HMRC employer rates and thresholds pages for three tax years.
* The GOV.UK National Minimum Wage page.

PDFs are the originals. HTML pages were converted to Markdown with the text unchanged. Sources and licences are
in `benchmark/README.md`. The documents are long and full of tables: 247 chunks, against 41 for the 40
documents of `test_v2`.

**Questions.** There are 44 questions: outdated 14, normal 12, historical 8, unanswerable 8 and multi-document 2.
The same author wrote them, so they are not independent, but the documents and their inconsistencies are real.
The split was committed before the run. Decision code was the frozen v0.2 code, and nothing was tuned.

| Pipeline | Reliable | Stale presented | Unsupported presented | Over-abstained | Wrong answers presented |
|---|---|---|---|---|---|
| B0 vector RAG | 33/44 (75.0%) | 3/25 | 0/8 | 3/36 | 8 |
| B3 + temporal / authority ranking | **40/44 (90.9%)** | 0/25 | 2/8 | 1/36 | 3 |
| B4 RAG Sentinel | 37/44 (84.1%) | **0/25** | **0/8** | 7/36 | **0** |
| B4 without gating rules | 40/44 (90.9%) | 0/25 | 1/8 | 0/36 | 4 |

*Wrong answers presented* counts answers shown as reliable that were stale, incorrect or should have been
refused (B0 and B3 present every answer they do not abstain on).

What this shows:

* **B4 did not beat B3 on real documents.**
  * B4 is −6.8 points against B3 (2 questions better, 5 worse), with clustered CI [−17.0, 0.0].
  * Against B0 it is +9.1 points, with clustered CI [0.0, +17.9] and McNemar p = 0.29. That is not
    significant on 44 questions.
  * The test_v2 headline (+9.9 over B0) is therefore **not confirmed** on this split.
* **B4 presented no wrong answer.**
  * All 7 of its failures were refusals or review flags.
  * B3 presented 3 wrong answers: 2 to unanswerable questions, and one IRA limit given as the 401(k) value.
  * B4's trade is fewer answers, every one correct. Whether that is better depends on the cost of a wrong
    answer. Reliability as defined here scores the two failure types the same.
* **Stale answers: 0/25 for B3 and every B4 variant,** against 3/25 for B0 and 4/25 for B1. Version and
  authority ranking does this work. It is the one result that holds on both held-out splits.
* **Conflict detection did not work on these documents.**
  * It found 0 of 2 actionable gold pairs and made 7 false positives.
  * The judge rated the 72.5¢ news release vs the 76¢ announcement as `different_context`. That is defensible,
    because the announcement applies from July 1, but it is not the `outdated` link the gold expects.
  * The false positives come from extraction (see below). A naive "values differ" detector would flag 2,744
    pairs.
* **Ingestion does not scale yet.** The 14 documents took 2 h 25 min (8,717 s), against 4 min for `test_v2`.
  * Extraction produced 830 claims and the grounding check rejected 185.
  * Documents that state many values per attribute send thousands of cross-document pairs to the LLM judge.
  * 3,214 of the pairs were finally rated `different_context`.
* **Limits of the split.**
  * It has no contradiction questions: the real documents contain no equal-authority contradictions.
  * It has only 2 actionable gold conflict pairs, so the detection numbers are anecdotes, not rates.

### Failure analysis (B4 on public_v1, 7 of 44)

| Question | What happened |
|---|---|
| P01, P11 | **Extraction dropped an enumerated scope.** Notice 2026-10 says "The standard mileage rate for 2026 is 20.5 cents per mile for use of an automobile: (1) for medical care…". The extractor stored 20.5¢ as the generic standard mileage rate. The judge then linked it to the 72.5¢ business rate as a conflict. In P11 that false conflict blocked a correct answer (R8). In P01 the draft itself gave 20.5¢ as the business rate, and R10/R8 blocked it. |
| P04, P17 | **Correct draft without citation markers.** The 7B generator answered correctly but cited nothing, so R4 refused. B3 has no citation rule and presented the same answers. |
| P05 | **Answer-check false alarm.** The correct 72.5¢ answer for March 2026 was flagged as not in the evidence (R10). |
| P23 | **Wrong draft, correctly blocked.** It gave the 401(k) catch-up ($8,000) for the IRA catch-up ($1,100). R10 stopped it. This counts as a failure only because the gold answer is VERIFIED. |
| P37 | **Historical comparison handled as a current question.** The question compares two past tax years. The query was run in current mode, retrieval returned only the 2025–26 page, which is superseded at the reference date, and R2 refused. The 2024–25 page was never retrieved. |

These are additions to the v0.3 list:
* extract scope from enumerated legal sentences;
* reduce pair-judge volume, for example by comparing only claims with matching qualifiers and periods;
* repair missing citations instead of refusing;
* detect comparisons between past periods as historical questions.

None were fixed before this report, and the split is now spent.

Tables: `results/public_v1_tables.md`. Records: `results/public_v1_records.jsonl`.

## Development results (not held out)

| Split | B0 | B3 | B4 | B4 unsupported | Notes |
|---|---|---|---|---|---|
| dev (26) | 20/26 | 23/26 | 24/26 | 0/5 | D05: onboarding guide's stale value not linked as outdated. D15: answer check rejected a correct "only when compromise is suspected" |
| test_v1 (88) | 72/88 | 79/88 | 85/88 | 2/20 | T04: related-fact answer accepted. T25: stale value blocked by R8 (safe). T81: equal-authority contradiction missed |

Tables: `results/dev_tables.md`, `results/test_v1_tables.md`.

## Limitations

* **Small benchmark, single author.** 81 held-out questions in 12 document groups (13 with the leakage-check
  group). Clustered CIs are a few points wide, and differences of 1–3 questions between ablations are noise.
* **Not independent.** The author of `test_v2` also built the system and knew the v0.1 failure modes. The
  split was written before v0.2 development and follows the same guideline, but an independent annotator would
  likely find other failure modes.
* **Synthetic documents in test_v2.** Clean Markdown plus one generated PDF and one DOCX. On the real documents
  in `public_v1`, extraction quality did drop: scope was lost from enumerated sentences, conflict detection
  failed, and ingestion was about 40 times slower per document. B4's lead over B3 disappeared there. No
  scanned pages were tested.
* **Same 7B model for everything.** Generation, claim extraction, conflict judge and answer check all use
  `qwen2.5:7b-instruct`. Their errors are correlated, which is why the answer check misses some
  related-fact answers.
* **Repeated runs measure generation variability only.** See the protocol notes. Extraction was not re-sampled.
* **McNemar p-values assume independent questions,** which the grouped design violates. Use the clustered
  intervals.
* **The v0.1 → v0.2 improvement is not measured on held-out data** (see "Comparison with v0.1").
