Split **dev**, 26 questions, as of 2026-10-01, generated 2026-10-30T12:25:36+00:00.  
LLM `qwen2.5:7b-instruct`, embedder `nomic-embed-text`, reranker `BAAI/bge-reranker-base`, min_relevance 0.0.

### Answer reliability

| Pipeline | Reliable | 95% CI (questions) | 95% CI (clustered by group) | Correct answers | Stale answers | Unsupported answers | Over-abstained | Decision acc. | Latency p50/p95 s |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 20/26 (76.9%) | [57.7%, 92.3%] | [50.0%, 92.3%] | 18/21 | 3/11 | 3/5 | 0/21 | 88.5% | 1.3 / 1.6 |
| B1 | 20/26 (76.9%) | [57.7%, 92.3%] | [50.0%, 84.6%] | 18/21 | 3/11 | 3/5 | 0/21 | 88.5% | 1.2 / 1.6 |
| B2 | 19/26 (73.1%) | [53.8%, 88.5%] | [50.0%, 77.8%] | 17/21 | 4/11 | 3/5 | 0/21 | 88.5% | 2.3 / 2.9 |
| B3 | 23/26 (88.5%) | [76.9%, 100.0%] | [75.0%, 92.3%] | 20/21 | 1/11 | 2/5 | 0/21 | 92.3% | 2.5 / 2.9 |
| B4 | 24/26 (92.3%) | [80.8%, 100.0%] | [88.9%, 100.0%] | 19/21 | 1/11 | 0/5 | 1/21 | 96.2% | 3.5 / 4.1 |
| B4-no-rerank | 24/26 (92.3%) | [80.8%, 100.0%] | [88.9%, 100.0%] | 19/21 | 0/11 | 0/5 | 2/21 | 92.3% | 2.0 / 3.2 |
| B4-relevance-ranking | 26/26 (100.0%) | [100.0%, 100.0%] | [100.0%, 100.0%] | 21/21 | 0/11 | 0/5 | 0/21 | 96.2% | 3.6 / 4.4 |
| B4-newest-wins | 23/26 (88.5%) | [76.9%, 100.0%] | [77.8%, 100.0%] | 18/21 | 1/11 | 0/5 | 2/21 | 88.5% | 2.8 / 4.1 |
| B4-no-conflicts | 23/26 (88.5%) | [76.9%, 100.0%] | [75.0%, 92.3%] | 19/21 | 1/11 | 1/5 | 1/21 | 92.3% | 2.9 / 5.1 |
| B4-no-gating | 23/26 (88.5%) | [76.9%, 100.0%] | [75.0%, 92.3%] | 20/21 | 1/11 | 2/5 | 0/21 | 92.3% | 2.6 / 4.1 |
| B4-no-answer-check | 24/26 (92.3%) | [80.8%, 100.0%] | [88.9%, 100.0%] | 20/21 | 1/11 | 1/5 | 0/21 | 96.2% | 2.3 / 2.9 |

Clustered intervals resample the 3 document groups, because questions about the same documents are correlated.

### Retrieval and grounding

| Pipeline | Recall@5 | MRR@5 | Citation precision | Numeric faithfulness | Abstention precision | Abstention recall |
|---|---|---|---|---|---|---|
| B0 | 100.0% | 78.8% | 74.1% | 100.0% | 100.0% | 40.0% |
| B1 | 100.0% | 84.1% | 70.4% | 100.0% | 100.0% | 40.0% |
| B2 | 100.0% | 85.6% | 58.1% | 100.0% | 100.0% | 40.0% |
| B3 | 100.0% | 100.0% | 95.5% | 100.0% | 100.0% | 60.0% |
| B4 | 100.0% | 100.0% | 95.2% | 100.0% | 83.3% | 100.0% |
| B4-no-rerank | 100.0% | 75.5% | 100.0% | 95.8% | 71.4% | 100.0% |
| B4-relevance-ranking | 100.0% | 85.6% | 95.7% | 100.0% | 100.0% | 100.0% |
| B4-newest-wins | 90.9% | 75.8% | 86.4% | 95.8% | 71.4% | 100.0% |
| B4-no-conflicts | 100.0% | 100.0% | 90.9% | 100.0% | 80.0% | 80.0% |
| B4-no-gating | 100.0% | 100.0% | 95.5% | 100.0% | 100.0% | 60.0% |
| B4-no-answer-check | 100.0% | 100.0% | 95.5% | 100.0% | 100.0% | 80.0% |

### Reliability by category

| Pipeline | contradiction (n=2) | historical (n=4) | multi_doc (n=2) | normal (n=8) | outdated (n=6) | unanswerable (n=4) |
|---|---|---|---|---|---|---|
| B0 | 50.0% | 75.0% | 100.0% | 100.0% | 66.7% | 50.0% |
| B1 | 50.0% | 75.0% | 50.0% | 100.0% | 83.3% | 50.0% |
| B2 | 50.0% | 75.0% | 50.0% | 100.0% | 66.7% | 50.0% |
| B3 | 50.0% | 100.0% | 100.0% | 100.0% | 83.3% | 75.0% |
| B4 | 100.0% | 100.0% | 100.0% | 100.0% | 66.7% | 100.0% |
| B4-no-rerank | 100.0% | 100.0% | 100.0% | 100.0% | 66.7% | 100.0% |
| B4-relevance-ranking | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| B4-newest-wins | 100.0% | 50.0% | 100.0% | 100.0% | 83.3% | 100.0% |
| B4-no-conflicts | 50.0% | 100.0% | 100.0% | 100.0% | 66.7% | 100.0% |
| B4-no-gating | 50.0% | 100.0% | 100.0% | 100.0% | 83.3% | 75.0% |
| B4-no-answer-check | 100.0% | 100.0% | 100.0% | 100.0% | 83.3% | 75.0% |

### Paired comparison with B4 (reliability)

| vs | B4 minus pipeline | 95% CI (paired) | 95% CI (paired, clustered) | B4 better / worse | McNemar p (assumes independent questions) |
|---|---|---|---|---|---|
| B0 | +15.4% | [+0.0%, +34.6%] | [+0.0%, +50.0%] | 5 / 1 | 0.219 |
| B1 | +15.4% | [+0.0%, +34.6%] | [+7.7%, +50.0%] | 5 / 1 | 0.219 |
| B2 | +19.2% | [+0.0%, +38.5%] | [+11.1%, +50.0%] | 6 / 1 | 0.125 |
| B3 | +3.9% | [-7.7%, +19.2%] | [+0.0%, +25.0%] | 2 / 1 | 1 |
| B4-no-rerank | +0.0% | [+0.0%, +0.0%] | [+0.0%, +0.0%] | 0 / 0 | 1 |
| B4-relevance-ranking | -7.7% | [-19.2%, +0.0%] | [-11.1%, +0.0%] | 0 / 2 | 0.5 |
| B4-newest-wins | +3.9% | [-7.7%, +15.4%] | [+0.0%, +11.1%] | 2 / 1 | 1 |
| B4-no-conflicts | +3.9% | [+0.0%, +11.5%] | [+0.0%, +25.0%] | 1 / 0 | 1 |
| B4-no-gating | +3.9% | [-7.7%, +19.2%] | [+0.0%, +25.0%] | 2 / 1 | 1 |
| B4-no-answer-check | +0.0% | [-11.5%, +11.5%] | [+0.0%, +0.0%] | 1 / 1 | 1 |

### Conflict detection (corpus level, 6 actionable gold pairs of 11)

| Detector | Precision | Recall | F1 | TP/FP/FN | Kind acc. (matched) | Gold pairs found |
|---|---|---|---|---|---|---|
| naive value difference | 17.9% | 83.3% | 29.4% | 5/23/1 | 11.1% | 9/11 |
| rules only | 100.0% | 33.3% | 50.0% | 2/0/4 | 55.6% | 9/11 |
| rules plus llm judge | 100.0% | 50.0% | 66.7% | 3/0/3 | 77.8% | 9/11 |

Missed (full detector): employee_handbook_2025.md vs leave_policy_v2.md (annual leave); onboarding_guide.md vs leave_policy_v2.md (annual leave); it_helpdesk_wiki.md vs password_standard_v2.md (password rotation)

Detected kinds: {'complementary': 4, 'contradiction': 1, 'different_context': 17, 'historical': 3, 'outdated': 2}

Ingestion: 14 documents, 14 chunks, 63 claims accepted, 4 rejected by the grounding check, 142 s.

### B4 failures

| Question | Category | Expected | Got | Rules | Answer |
|---|---|---|---|---|---|
| D05 | outdated | VERIFIED | VERIFIED | - | A new hire starts with 20 days of annual leave per year. |
| D15 | outdated | VERIFIED | INSUFFICIENT_EVIDENCE | R9 | I can't give a reliable answer. The evidence-based draft does not answer the question (mis |
