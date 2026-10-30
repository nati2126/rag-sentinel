Split **test_v2**, 81 questions, as of 2026-10-01, generated 2026-10-30T14:12:47+00:00.  
LLM `qwen2.5:7b-instruct`, embedder `nomic-embed-text`, reranker `BAAI/bge-reranker-base`, min_relevance 0.0.

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

### B4 failures

| Question | Category | Expected | Got | Rules | Answer |
|---|---|---|---|---|---|
| V18 | contradiction | NEEDS_REVIEW | VERIFIED | - | Confidential documents must be reviewed for classification every 24 months. |
| V22 | multi_doc | VERIFIED | VERIFIED | - | Restricted data must never be sent by e-mail. It must be protected in transit using the se |
| V30 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | The offsite backups are copied to a second data centre every night according to the Disast |
| V41 | historical | VERIFIED | NEEDS_REVIEW | R6 | Speak-up reports were acknowledged within 7 days. |
| V59 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | The build servers must have OpenSSL 3.0 or later installed, as per the Cryptographic Libra |
| V62 | normal | VERIFIED | NEEDS_REVIEW | R7 | CCTV footage is retained for 30 days before being deleted automatically, unless it is need |
| V75 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | Engineers on the on-call rota receive an on-call allowance of $320 per week, which would a |
