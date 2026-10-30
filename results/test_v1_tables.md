Split **test_v1**, 88 questions, as of 2026-10-01, generated 2026-10-30T13:30:12+00:00.  
LLM `qwen2.5:7b-instruct`, embedder `nomic-embed-text`, reranker `BAAI/bge-reranker-base`, min_relevance 0.0.

### Answer reliability

| Pipeline | Reliable | 95% CI (questions) | 95% CI (clustered by group) | Correct answers | Stale answers | Unsupported answers | Over-abstained | Decision acc. | Latency p50/p95 s |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 72/88 (81.8%) | [73.9%, 89.8%] | [72.9%, 89.9%] | 60/68 | 8/35 | 8/20 | 0/68 | 90.9% | 1.2 / 1.8 |
| B1 | 72/88 (81.8%) | [73.9%, 89.8%] | [73.6%, 89.6%] | 60/68 | 8/35 | 8/20 | 0/68 | 90.9% | 1.2 / 1.8 |
| B2 | 69/88 (78.4%) | [69.3%, 86.4%] | [69.9%, 87.1%] | 58/68 | 10/35 | 9/20 | 0/68 | 89.8% | 2.0 / 2.6 |
| B3 | 79/88 (89.8%) | [83.0%, 95.5%] | [81.2%, 96.0%] | 66/68 | 2/35 | 7/20 | 0/68 | 92.0% | 2.1 / 2.8 |
| B4 | 85/88 (96.6%) | [92.0%, 100.0%] | [92.9%, 100.0%] | 67/68 | 0/35 | 2/20 | 1/68 | 95.5% | 3.3 / 5.9 |
| B4-no-rerank | 84/88 (95.5%) | [90.9%, 98.9%] | [91.4%, 98.9%] | 65/68 | 1/35 | 1/20 | 2/68 | 96.6% | 2.4 / 4.9 |
| B4-relevance-ranking | 83/88 (94.3%) | [89.8%, 98.9%] | [89.3%, 98.8%] | 64/68 | 1/35 | 1/20 | 3/68 | 93.2% | 3.3 / 5.6 |
| B4-newest-wins | 79/88 (89.8%) | [83.0%, 95.5%] | [83.0%, 95.3%] | 60/68 | 0/35 | 1/20 | 7/68 | 87.5% | 3.1 / 5.9 |
| B4-no-conflicts | 81/88 (92.0%) | [86.4%, 97.7%] | [84.4%, 97.9%] | 66/68 | 2/35 | 5/20 | 0/68 | 93.2% | 2.2 / 3.8 |
| B4-no-gating | 77/88 (87.5%) | [80.7%, 94.3%] | [79.2%, 93.6%] | 67/68 | 1/35 | 10/20 | 0/68 | 88.6% | 2.3 / 4.5 |
| B4-no-answer-check | 82/88 (93.2%) | [87.5%, 97.7%] | [87.5%, 97.8%] | 66/68 | 0/35 | 4/20 | 2/68 | 92.0% | 2.2 / 4.4 |

Clustered intervals resample the 14 document groups, because questions about the same documents are correlated.

### Retrieval and grounding

| Pipeline | Recall@5 | MRR@5 | Citation precision | Numeric faithfulness | Abstention precision | Abstention recall |
|---|---|---|---|---|---|---|
| B0 | 100.0% | 81.2% | 68.5% | 98.7% | 100.0% | 60.0% |
| B1 | 100.0% | 82.5% | 64.9% | 100.0% | 100.0% | 60.0% |
| B2 | 100.0% | 86.1% | 68.5% | 100.0% | 100.0% | 55.0% |
| B3 | 100.0% | 95.0% | 88.6% | 100.0% | 100.0% | 65.0% |
| B4 | 100.0% | 95.0% | 91.0% | 100.0% | 94.7% | 90.0% |
| B4-no-rerank | 97.3% | 73.9% | 90.8% | 100.0% | 90.5% | 95.0% |
| B4-relevance-ranking | 100.0% | 86.1% | 84.3% | 100.0% | 86.4% | 95.0% |
| B4-newest-wins | 97.0% | 80.5% | 86.3% | 97.4% | 73.1% | 95.0% |
| B4-no-conflicts | 100.0% | 95.0% | 88.6% | 100.0% | 100.0% | 75.0% |
| B4-no-gating | 100.0% | 95.0% | 90.9% | 98.7% | 100.0% | 50.0% |
| B4-no-answer-check | 100.0% | 95.0% | 92.1% | 98.7% | 88.9% | 80.0% |

### Reliability by category

| Pipeline | contradiction (n=6) | historical (n=10) | multi_doc (n=6) | normal (n=34) | outdated (n=17) | unanswerable (n=15) |
|---|---|---|---|---|---|---|
| B0 | 16.7% | 80.0% | 83.3% | 100.0% | 70.6% | 80.0% |
| B1 | 16.7% | 80.0% | 83.3% | 100.0% | 70.6% | 80.0% |
| B2 | 16.7% | 70.0% | 83.3% | 100.0% | 64.7% | 73.3% |
| B3 | 16.7% | 100.0% | 100.0% | 100.0% | 88.2% | 86.7% |
| B4 | 83.3% | 100.0% | 100.0% | 100.0% | 94.1% | 93.3% |
| B4-no-rerank | 83.3% | 100.0% | 100.0% | 94.1% | 94.1% | 100.0% |
| B4-relevance-ranking | 83.3% | 100.0% | 100.0% | 100.0% | 76.5% | 100.0% |
| B4-newest-wins | 83.3% | 90.0% | 83.3% | 97.1% | 70.6% | 100.0% |
| B4-no-conflicts | 16.7% | 100.0% | 100.0% | 100.0% | 88.2% | 100.0% |
| B4-no-gating | 16.7% | 100.0% | 100.0% | 100.0% | 94.1% | 66.7% |
| B4-no-answer-check | 83.3% | 100.0% | 100.0% | 97.1% | 94.1% | 80.0% |

### Paired comparison with B4 (reliability)

| vs | B4 minus pipeline | 95% CI (paired) | 95% CI (paired, clustered) | B4 better / worse | McNemar p (assumes independent questions) |
|---|---|---|---|---|---|
| B0 | +14.8% | [+5.7%, +23.9%] | [+7.1%, +23.1%] | 15 / 2 | 0.0023 |
| B1 | +14.8% | [+5.7%, +23.9%] | [+7.9%, +22.4%] | 15 / 2 | 0.0023 |
| B2 | +18.2% | [+9.1%, +27.3%] | [+11.0%, +25.6%] | 18 / 2 | 0.0004 |
| B3 | +6.8% | [+1.1%, +13.6%] | [+0.0%, +14.5%] | 7 / 1 | 0.0703 |
| B4-no-rerank | +1.1% | [-3.4%, +5.7%] | [-4.0%, +6.3%] | 3 / 2 | 1 |
| B4-relevance-ranking | +2.3% | [-2.3%, +6.8%] | [+0.0%, +5.3%] | 3 / 1 | 0.625 |
| B4-newest-wins | +6.8% | [+1.1%, +12.5%] | [+2.2%, +12.6%] | 7 / 1 | 0.0703 |
| B4-no-conflicts | +4.5% | [-1.1%, +10.2%] | [-1.1%, +11.1%] | 5 / 1 | 0.219 |
| B4-no-gating | +9.1% | [+3.4%, +15.9%] | [+3.9%, +16.2%] | 8 / 0 | 0.0078 |
| B4-no-answer-check | +3.4% | [-1.1%, +8.0%] | [-1.9%, +9.5%] | 4 / 1 | 0.375 |

### Conflict detection (corpus level, 12 actionable gold pairs of 19)

| Detector | Precision | Recall | F1 | TP/FP/FN | Kind acc. (matched) | Gold pairs found |
|---|---|---|---|---|---|---|
| naive value difference | 9.3% | 66.7% | 16.3% | 8/78/4 | 21.4% | 14/19 |
| rules only | 57.1% | 33.3% | 42.1% | 4/3/8 | 50.0% | 14/19 |
| rules plus llm judge | 70.0% | 58.3% | 63.6% | 7/3/5 | 92.9% | 14/19 |

Missed (full detector): travel_quick_guide.pdf vs travel_policy_2026.md (hotel limit); security_awareness_slides.md vs incident_response_policy.md (incident reporting); customer_contract_template.md vs support_sla_v2.md (P1 response); support_team_wiki.md vs support_sla_v2.md (P3 response); expense_policy.md vs finance_operations_manual.md (receipt threshold)

False positives (full detector): it_faq.md '3 years' vs procurement_budget_2026.md '4 years' as outdated; finance_operations_manual.md '60 days of the expense date' vs travel_policy_2026.md 'within 30 days of the end of the trip' as outdated; finance_operations_manual.md '60 days of the expense date' vs travel_quick_guide.pdf 'within 30 days of returning' as outdated

Detected kinds: {'complementary': 1, 'contradiction': 3, 'different_context': 40, 'historical': 17, 'insufficient_evidence': 1, 'outdated': 7, 'pending_change': 8}

Ingestion: 44 documents, 44 chunks, 150 claims accepted, 9 rejected by the grounding check, 332 s.

### B4 failures

| Question | Category | Expected | Got | Rules | Answer |
|---|---|---|---|---|---|
| T04 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | Employees may work remotely up to 2 days per week, subject to manager agreement. [E1] |
| T25 | outdated | VERIFIED | NEEDS_REVIEW | R8 | Primary caregivers receive 12 weeks of paid parental leave. |
| T81 | contradiction | NEEDS_REVIEW | VERIFIED | - | A receipt must be attached for every expense above $25. |
