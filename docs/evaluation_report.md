# Evaluation report: VersionConflict benchmark

All numbers below come from `results/test_summary.json` and `results/test_records.jsonl`, produced by
`python -m evaluation.run --split test --rebuild --ablations` on 2026-10-30 (Windows 11, RTX 4070 8 GB,
models served by local Ollama). The tables were rendered by `python -m evaluation.report --split test`.
Nothing was edited by hand.

## Protocol

* **Splits.** Dev (26 questions, 14 documents, 3 groups) was used to develop and debug the system.
  Test (88 questions, 44 documents, 13 groups) uses disjoint document groups in a separate knowledge
  base and was run once, after development stopped. No code or threshold was changed after the test run.
* **Reference date.** 2026-10-01, unless a question names a date.
* **Relevance gate.** `min_relevance` was tuned on dev only (`python -m evaluation.tune`). Every positive
  threshold lowered dev reliability, so the tuned value is **0**: the gate is effectively off in these
  results.
* **Conflict detection** is scored at corpus level against 19 annotated document pairs, 12 of them
  actionable (contradiction or outdated). Predicate canonicalization (embeddings plus the LLM
  same-attribute judge) runs once at ingestion and is shared by all three detectors, so "rules only"
  means rules-only pair classification on LLM-canonicalized keys.
* **Metric definitions** (see `evaluation/run.py`):
  * **Reliability:** the share of questions where the system either presents a correct answer as
    reliable (gold VERIFIED) or does not present one (gold abstain or review).
  * **Stale answer rate:** over the 35 questions with a known outdated value, the share of presented
    answers that contain the outdated value.
  * **Unsupported answer rate:** over the 19 questions whose gold decision is not VERIFIED, the share
    where the system still presents an answer as reliable.
  * **Over-abstention:** answerable questions the system refused or sent to review.
  * Baselines B0 to B2 have no gate, so every answer they produce counts as presented.
* **Uncertainty.** 95% bootstrap CIs (2000 resamples), paired bootstrap for differences, and the exact
  McNemar test on per-question reliability.

## Test results

Split **test**, 88 questions, as of 2026-10-01, generated 2026-10-30T10:48:41+00:00.  
LLM `qwen2.5:7b-instruct`, embedder `nomic-embed-text`, reranker `BAAI/bge-reranker-base`, min_relevance 0.0.

### Answer reliability

| Pipeline | Reliability [95% CI] | Answer acc. | Stale rate | Unsupported rate | Over-abstention | Decision acc. | Latency p50/p95 s |
|---|---|---|---|---|---|---|---|
| B0 | 83.0% [75.0%, 90.9%] | 88.4% | 22.9% | 36.8% | 0.0% | 92.0% | 1.2 / 1.8 |
| B1 | 83.0% [75.0%, 90.9%] | 88.4% | 22.9% | 36.8% | 0.0% | 92.0% | 1.2 / 1.8 |
| B2 | 79.5% [70.5%, 87.5%] | 85.5% | 28.6% | 42.1% | 0.0% | 90.9% | 2.0 / 2.6 |
| B3 | 90.9% [85.2%, 96.6%] | 97.1% | 5.7% | 31.6% | 0.0% | 93.2% | 2.1 / 2.8 |
| B4 | 90.9% [85.2%, 96.6%] | 97.1% | 0.0% | 31.6% | 2.9% | 89.8% | 2.3 / 4.6 |
| B4-no-rerank | 92.0% [86.4%, 97.7%] | 95.7% | 0.0% | 21.1% | 4.3% | 92.0% | 1.6 / 3.7 |
| B4-relevance-ranking | 90.9% [85.2%, 95.5%] | 92.8% | 5.7% | 15.8% | 4.3% | 90.9% | 2.5 / 4.7 |
| B4-newest-wins | 87.5% [80.7%, 93.2%] | 89.9% | 0.0% | 21.1% | 8.7% | 86.4% | 2.4 / 5.0 |
| B4-no-conflicts | 92.0% [86.4%, 97.7%] | 97.1% | 5.7% | 26.3% | 0.0% | 93.2% | 2.1 / 2.8 |
| B4-no-gating | 88.6% [81.8%, 94.3%] | 98.6% | 2.9% | 47.4% | 0.0% | 89.8% | 2.3 / 4.5 |

### Retrieval and grounding

| Pipeline | Recall@5 | MRR@5 | Citation precision | Numeric faithfulness | Abstention precision | Abstention recall |
|---|---|---|---|---|---|---|
| B0 | 100.0% | 80.2% | 66.7% | 98.7% | 100.0% | 63.2% |
| B1 | 100.0% | 81.6% | 63.9% | 100.0% | 100.0% | 63.2% |
| B2 | 100.0% | 85.2% | 67.4% | 100.0% | 100.0% | 57.9% |
| B3 | 100.0% | 95.7% | 87.6% | 100.0% | 100.0% | 68.4% |
| B4 | 100.0% | 95.7% | 91.0% | 100.0% | 86.7% | 68.4% |
| B4-no-rerank | 97.3% | 74.6% | 92.1% | 100.0% | 83.3% | 79.0% |
| B4-relevance-ranking | 100.0% | 85.2% | 82.6% | 100.0% | 84.2% | 84.2% |
| B4-newest-wins | 97.0% | 80.7% | 82.3% | 97.4% | 71.4% | 79.0% |
| B4-no-conflicts | 100.0% | 95.7% | 87.6% | 100.0% | 100.0% | 73.7% |
| B4-no-gating | 100.0% | 95.7% | 86.8% | 100.0% | 100.0% | 52.6% |

### Reliability by category

| Pipeline | contradiction (n=5) | historical (n=10) | multi_doc (n=6) | normal (n=35) | outdated (n=17) | unanswerable (n=15) |
|---|---|---|---|---|---|---|
| B0 | 20.0% | 80.0% | 83.3% | 100.0% | 70.6% | 80.0% |
| B1 | 20.0% | 80.0% | 83.3% | 100.0% | 70.6% | 80.0% |
| B2 | 20.0% | 70.0% | 83.3% | 100.0% | 64.7% | 73.3% |
| B3 | 20.0% | 100.0% | 100.0% | 100.0% | 88.2% | 86.7% |
| B4 | 60.0% | 100.0% | 100.0% | 97.1% | 94.1% | 73.3% |
| B4-no-rerank | 60.0% | 100.0% | 100.0% | 91.4% | 100.0% | 86.7% |
| B4-relevance-ranking | 60.0% | 100.0% | 100.0% | 97.1% | 76.5% | 93.3% |
| B4-newest-wins | 60.0% | 90.0% | 83.3% | 94.3% | 82.3% | 86.7% |
| B4-no-conflicts | 20.0% | 100.0% | 100.0% | 100.0% | 88.2% | 93.3% |
| B4-no-gating | 20.0% | 100.0% | 100.0% | 100.0% | 94.1% | 66.7% |

### Paired comparison with B4 (reliability)

| vs | B4 minus pipeline | 95% CI (paired bootstrap) | B4 better / worse | McNemar p |
|---|---|---|---|---|
| B0 | +8.0% | [-1.1%, +17.1%] | 12 / 5 | 0.143 |
| B1 | +8.0% | [-1.1%, +17.1%] | 12 / 5 | 0.143 |
| B2 | +11.4% | [+2.3%, +21.6%] | 15 / 5 | 0.0414 |
| B3 | +0.0% | [-5.7%, +5.7%] | 4 / 4 | 1 |
| B4-no-rerank | -1.1% | [-6.8%, +4.5%] | 3 / 4 | 1 |
| B4-relevance-ranking | +0.0% | [-5.7%, +5.7%] | 3 / 3 | 1 |
| B4-newest-wins | +3.4% | [-2.3%, +9.1%] | 5 / 2 | 0.453 |
| B4-no-conflicts | -1.1% | [-6.8%, +4.5%] | 3 / 4 | 1 |
| B4-no-gating | +2.3% | [-2.3%, +6.8%] | 3 / 1 | 0.625 |

### Conflict detection (corpus level, 12 actionable gold pairs of 19)

| Detector | Precision | Recall | F1 | TP/FP/FN | Kind acc. (matched) | Gold pairs found |
|---|---|---|---|---|---|---|
| naive value difference | 9.3% | 66.7% | 16.3% | 8/78/4 | 21.4% | 14/19 |
| rules only | 66.7% | 50.0% | 57.1% | 6/3/6 | 85.7% | 14/19 |
| rules plus llm judge | 75.0% | 50.0% | 60.0% | 6/2/6 | 85.7% | 14/19 |

Missed (full detector): travel_quick_guide.pdf vs travel_policy_2026.md (hotel limit); security_awareness_slides.md vs incident_response_policy.md (incident reporting); customer_contract_template.md vs support_sla_v2.md (P1 response); support_team_wiki.md vs support_sla_v2.md (P3 response); expense_policy.md vs finance_operations_manual.md (receipt threshold); endpoint_security_standard.md vs acceptable_use_policy.md (screen lock timeout)

False positives (full detector): it_faq.md '3 years' vs procurement_budget_2026.md '4 years' as outdated; finance_operations_manual.md '60 days of the expense date' vs travel_quick_guide.pdf 'within 30 days of returning' as outdated

Detected kinds: {'complementary': 1, 'contradiction': 2, 'different_context': 42, 'historical': 17, 'insufficient_evidence': 1, 'outdated': 6, 'pending_change': 8}

Ingestion: 44 documents, 44 chunks, 150 claims accepted, 9 rejected by the grounding check, 358 s.

### B4 failures

| Question | Category | Expected | Got | Rules | Answer |
|---|---|---|---|---|---|
| T04 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | Employees may work remotely up to 2 days per week, subject to manager agreement. [E1] |
| T10 | normal | VERIFIED | NEEDS_REVIEW | R7 | Expense claims must be submitted within 30 days of the expense date. |
| T24 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | The Data Protection Officer assesses the risk to individuals when a security incident invo |
| T25 | outdated | VERIFIED | NEEDS_REVIEW | R8 | Primary caregivers receive 12 weeks of paid parental leave. |
| T57 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | Python 3.12 was released in October 2023 and the distutils package has been removed from t |
| T76 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | Employees receive 16 weeks of fully paid parental leave as primary caregivers, and 4 weeks |
| T81 | contradiction | NEEDS_REVIEW | VERIFIED | - | A receipt must be attached for every expense above $25. |
| T83 | contradiction | NEEDS_REVIEW | VERIFIED | - | Company laptops must lock the screen after 5 minutes of inactivity. |

## What the results show

**1. Version and authority awareness is what removes stale answers.** B0 to B2 present the outdated
value on 23 to 29% of the questions that have one. Temporal and authority-aware ranking with metadata in
the prompt (B3) cuts that to 5.7%, and the full system (B4) to 0%. The ablation that ranks by newest
document instead of standing (B4-newest-wins) also reaches 0% stale, but it over-abstains on 8.7% of
answerable questions and has the lowest reliability of the B4 variants (87.5%).

**2. B4 beats the plain RAG baselines, but the margin is not statistically conclusive.** B4 vs B0: +8.0
points (95% CI -1.1 to +17.1, McNemar p = 0.14; 12 questions better, 5 worse). B4 vs B2: +11.4 points
(CI +2.3 to +21.6, p = 0.04). On 88 questions, differences under about 10 points cannot be separated
from noise.

**3. The conflict and gating layers did not improve overall reliability over B3 on this test set.**
B3, B4 and every B4 ablation fall between 87.5% and 92.0%, and none differs significantly from B4.
Contradiction detection does what it is for: reliability on contradiction questions is 20% without it
(B3, B4-no-conflicts, B4-no-gating) and 60% with it. But on 5 questions it is too few to carry the total,
and it also creates false reviews (see T10 and T25 below).

**4. Contradiction detection is precise but misses half of the actionable pairs.** The naive "values
differ" detector finds 8 of 12 actionable pairs but raises 78 false findings (precision 9%). The rule
plus LLM-judge detector has 75% precision at 50% recall. The six misses have three causes:
* **The LLM pair judge over-uses "different_context"** (2 misses, plus one on dev). It ruled "P3 ticket" vs
  "P3 issue" and "laptops and desktops" vs "company devices" to be different contexts.
* **Attribute names were not merged** (2 misses). The receipt threshold was extracted as
  `minimum_expense_for_receipt` in one document and `expense_claim_max_amount` in the other, and the P1
  response as `first_response_time` vs `first_response_deadline`.
* **Bad value extraction** (1 miss). The whole sentence was taken as the value ("Report suspected security
  incidents ... within 48 hours"), so its attribute key did not match.
* The hotel-limit miss was not investigated.

The rules-only detector has the same recall at lower precision (66.7%), so on this test set the judge's
contribution is precision, not recall.

**5. Unsupported answers are the main weakness.** B4 presented an answer to 6 of the 19 questions where
gold says abstain or review (31.6%). In 4 of them the model answered a related but different question
from weakly relevant evidence (T04, T24, T57, T76). Because the dev-tuned relevance gate is 0, nothing
stopped them.

## B4 failure analysis (test)

| Question | What happened | Cause | Component |
|---|---|---|---|
| T04 "Can employees work remotely from another country?" | Answered with the 2-days-per-week rule | Generator answered a related question; no gate (relevance 0.56) | generation |
| T24 "Who is Halden's Data Protection Officer?" | Answered with what the DPO does | Generator answered a related question; relevance 0.001 would have been caught by a gate | generation, gate |
| T57 "When does Python 3.12 reach end of life?" | Answered with the release date and distutils removal | as above (relevance 0.18) | generation, gate |
| T76 "How many days of annual leave do employees get?" (leakage check: leave docs exist only in dev) | Answered with parental leave | as above (relevance 0.15). No dev content leaked | generation, gate |
| T81 receipt threshold ($25 vs $75) | VERIFIED $25 | Contradiction missed: extracted attribute names differ, so the claims were never compared | claim extraction |
| T83 screen lock (5 vs 15 minutes) | VERIFIED 5 minutes | Claims compared, but the LLM judge ruled "laptops and desktops" and "company devices" different contexts | LLM pair judge |
| T25 primary caregiver leave (gold 16 weeks) | NEEDS_REVIEW | The generator cited the outdated Benefits Overview (12 weeks). R8 caught it, so a stale answer became a review instead of being presented: a safe failure, but still a failure | generation, ranking |
| T10 "Within how many days must expense claims be submitted?" (gold 30, VERIFIED) | NEEDS_REVIEW, citing the 30 vs 60 day contradiction | **Benchmark defect.** The expenses group was added to the test corpus after the original questions were written, and it makes this question a genuine equal-authority contradiction (it is close to T82). B4's decision is defensible; the gold label is out of date | annotation |

The labels were not changed after the run. With T10 relabelled to NEEDS_REVIEW, the four pipelines that
flagged it (B4, B4-no-rerank, B4-relevance-ranking, B4-newest-wins) would each gain one question
(+1.1 points), and the six that presented it (B0 to B3, B4-no-conflicts, B4-no-gating) would each lose one.

## Post-hoc sensitivity (test, not used for any reported number)

What a relevance gate *would* have done on B4's test records, simulated offline like `evaluation/tune.py`.
This uses test labels, so it is **not** a valid result. It only shows that the gate matters and that
26 dev questions were too few to tune it:

| min_relevance | Reliability | Unsupported rate | Over-abstention |
|---|---|---|---|
| 0 (tuned on dev) | 90.9% | 31.6% | 2.9% |
| 0.05 | 92.0% | 26.3% | 2.9% |
| 0.2 | 93.2% | 15.8% | 4.3% |
| 0.5 | 93.2% | 15.8% | 4.3% |

## Dev results (for reference; optimistic)

The dev split was used for debugging (for example the R5 handling of years and version numbers, R7
scoping, and the judge prompts), so its numbers are optimistic. B4 dev reliability is 96.2%, against
76.9% for B0. Full tables: `results/dev_tables.md`.

## Limitations

* **Small benchmark.** 88 test questions, of which only 5 are contradiction questions and 19 should
  abstain. Confidence intervals are wide.
* **Mostly synthetic corpus,** with one author for documents and labels. The public-derived documents are
  short paraphrased summaries, not the original texts.
* **One document per chunk.** Benchmark documents are short, so every document is a single chunk.
  Recall@5 is near 100% for every pipeline and says little about retrieval on long documents.
* **The 7B model is the bottleneck.** Extraction naming errors, judge errors and "answer a related
  question" behaviour cause most failures. The rules can only verify what extraction produces.
* **Latency.** B4 p95 is 4.6 s against 1.8 s for B0 (extra rerank, claim lookup and judge calls on
  uncached pairs).
* **Single run.** All outputs are at temperature 0 with a fixed seed, so a rerun should reproduce them
  closely. Variance across seeds or models was not measured.

## Reproduce

```powershell
.venv\Scripts\python.exe -m evaluation.run --split dev --rebuild --force --min-relevance 0
.venv\Scripts\python.exe -m evaluation.tune
.venv\Scripts\python.exe -m evaluation.run --split test --rebuild --ablations
.venv\Scripts\python.exe -m evaluation.report --split test
```
