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
