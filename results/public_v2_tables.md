Split **public_v2**, 55 questions, as of 2026-11-27, generated 2026-11-27T12:22:46+00:00.  
LLM `qwen2.5:7b-instruct`, embedder `nomic-embed-text`, reranker `BAAI/bge-reranker-base`, min_relevance 0.0.

### Answer reliability

| Pipeline | Reliable | 95% CI (questions) | 95% CI (clustered by group) | Correct answers | Stale answers | Unsupported answers | Over-abstained | Decision acc. | Latency p50/p95 s |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 38/55 (69.1%) | [56.4%, 81.8%] | [60.7%, 77.8%] | 32/44 | 8/30 | 5/11 | 1/44 | 89.1% | 1.9 / 2.7 |
| B1 | 39/55 (70.9%) | [58.2%, 81.8%] | [58.6%, 84.6%] | 31/44 | 9/30 | 3/11 | 1/44 | 92.7% | 1.8 / 2.6 |
| B2 | 39/55 (70.9%) | [58.2%, 81.8%] | [51.7%, 84.6%] | 31/44 | 6/30 | 3/11 | 2/44 | 90.9% | 4.1 / 5.0 |
| B3 | 42/55 (76.4%) | [65.5%, 87.3%] | [70.9%, 82.8%] | 37/44 | 2/30 | 6/11 | 0/44 | 89.1% | 4.3 / 5.0 |
| B4 | 42/55 (76.4%) | [63.6%, 87.3%] | [66.7%, 86.0%] | 33/44 | 1/30 | 2/11 | 4/44 | 87.3% | 5.8 / 7.5 |
| B4-no-rerank | 47/55 (85.5%) | [74.6%, 94.5%] | [77.8%, 92.9%] | 38/44 | 0/30 | 2/11 | 5/44 | 85.5% | 3.6 / 5.3 |
| B4-relevance-ranking | 34/55 (61.8%) | [49.1%, 74.6%] | [51.7%, 73.1%] | 26/44 | 1/30 | 3/11 | 9/44 | 78.2% | 6.0 / 7.7 |
| B4-newest-wins | 36/55 (65.5%) | [52.7%, 78.2%] | [49.0%, 78.6%] | 27/44 | 1/30 | 2/11 | 13/44 | 72.7% | 5.4 / 7.8 |
| B4-no-conflicts | 40/55 (72.7%) | [61.8%, 83.6%] | [65.5%, 77.6%] | 32/44 | 1/30 | 3/11 | 5/44 | 83.6% | 5.1 / 6.9 |
| B4-no-gating | 41/55 (74.6%) | [61.8%, 85.5%] | [68.0%, 80.0%] | 35/44 | 3/30 | 5/11 | 0/44 | 90.9% | 4.2 / 5.2 |
| B4-no-answer-check | 41/55 (74.6%) | [61.8%, 85.5%] | [66.7%, 82.1%] | 33/44 | 1/30 | 3/11 | 4/44 | 85.5% | 3.8 / 4.8 |

Clustered intervals resample the 4 document groups, because questions about the same documents are correlated.

### Retrieval and grounding

| Pipeline | Recall@5 | MRR@5 | Citation precision | Numeric faithfulness | Abstention precision | Abstention recall |
|---|---|---|---|---|---|---|
| B0 | 81.8% | 54.4% | 51.7% | 93.8% | 85.7% | 54.5% |
| B1 | 85.2% | 69.0% | 44.2% | 95.7% | 88.9% | 72.7% |
| B2 | 83.0% | 67.2% | 44.0% | 86.7% | 80.0% | 72.7% |
| B3 | 88.6% | 82.1% | 62.5% | 82.0% | 100.0% | 45.5% |
| B4 | 88.6% | 82.1% | 57.1% | 89.6% | 69.2% | 81.8% |
| B4-no-rerank | 94.3% | 79.7% | 60.8% | 91.5% | 64.3% | 81.8% |
| B4-relevance-ranking | 83.0% | 67.2% | 60.3% | 87.8% | 47.1% | 72.7% |
| B4-newest-wins | 76.1% | 66.7% | 52.7% | 87.2% | 40.9% | 81.8% |
| B4-no-conflicts | 88.6% | 82.1% | 63.8% | 92.0% | 61.5% | 72.7% |
| B4-no-gating | 88.6% | 82.1% | 50.0% | 77.5% | 100.0% | 54.5% |
| B4-no-answer-check | 88.6% | 82.1% | 56.7% | 89.6% | 66.7% | 72.7% |

### Reliability by category

| Pipeline | historical (n=11) | multi_doc (n=3) | normal (n=12) | outdated (n=18) | unanswerable (n=11) |
|---|---|---|---|---|---|
| B0 | 63.6% | 66.7% | 91.7% | 66.7% | 54.5% |
| B1 | 63.6% | 66.7% | 91.7% | 61.1% | 72.7% |
| B2 | 63.6% | 33.3% | 91.7% | 66.7% | 72.7% |
| B3 | 81.8% | 33.3% | 100.0% | 83.3% | 45.5% |
| B4 | 63.6% | 33.3% | 83.3% | 83.3% | 81.8% |
| B4-no-rerank | 81.8% | 0.0% | 91.7% | 100.0% | 81.8% |
| B4-relevance-ranking | 54.5% | 0.0% | 66.7% | 66.7% | 72.7% |
| B4-newest-wins | 27.3% | 0.0% | 75.0% | 83.3% | 81.8% |
| B4-no-conflicts | 63.6% | 0.0% | 83.3% | 83.3% | 72.7% |
| B4-no-gating | 72.7% | 33.3% | 91.7% | 83.3% | 54.5% |
| B4-no-answer-check | 63.6% | 33.3% | 83.3% | 83.3% | 72.7% |

### Paired comparison with B4 (reliability)

| vs | B4 minus pipeline | 95% CI (paired) | 95% CI (paired, clustered) | B4 better / worse | McNemar p (assumes independent questions) |
|---|---|---|---|---|---|
| B0 | +7.3% | [-7.3%, +21.8%] | [-11.1%, +25.0%] | 10 / 6 | 0.455 |
| B1 | +5.5% | [-7.3%, +18.2%] | [-9.1%, +16.4%] | 8 / 5 | 0.581 |
| B2 | +5.5% | [-7.3%, +16.4%] | [-14.8%, +26.2%] | 7 / 4 | 0.549 |
| B3 | +0.0% | [-10.9%, +10.9%] | [-11.1%, +10.7%] | 4 / 4 | 1 |
| B4-no-rerank | -9.1% | [-18.2%, +0.0%] | [-13.8%, -3.9%] | 1 / 6 | 0.125 |
| B4-relevance-ranking | +14.5% | [+5.5%, +25.4%] | [+3.7%, +22.9%] | 8 / 0 | 0.0078 |
| B4-newest-wins | +10.9% | [+3.6%, +20.0%] | [+6.7%, +18.9%] | 6 / 0 | 0.0312 |
| B4-no-conflicts | +3.6% | [-5.5%, +12.7%] | [-3.7%, +12.2%] | 4 / 2 | 0.688 |
| B4-no-gating | +1.8% | [-5.5%, +9.1%] | [-7.4%, +16.3%] | 3 / 2 | 1 |
| B4-no-answer-check | +1.8% | [+0.0%, +5.5%] | [+0.0%, +6.0%] | 1 / 0 | 1 |

### Conflict detection (corpus level, 2 actionable gold pairs of 12)

| Detector | Precision | Recall | F1 | TP/FP/FN | Kind acc. (matched) | Gold pairs found |
|---|---|---|---|---|---|---|
| naive value difference | 0.0% | 0.0% | 0.0% | 0/806/2 | 0.0% | 5/12 |
| rules only | 0.0% | 0.0% | 0.0% | 0/2/2 | 20.0% | 5/12 |
| rules plus llm judge | 0.0% | 0.0% | 0.0% | 0/3/2 | 80.0% | 5/12 |

Missed (full detector): dwp_news_2025_04_06.md vs govuk_new_state_pension_2026.md (full rate of the new State Pension); dwp_news_2025_04_06.md vs dwp_news_2026_04_04.md (full basic State Pension)

False positives (full detector): dwp_news_2026_04_04.md 'up to £2,100' vs dwp_news_2025_04_06.md 'up to £470' as contradiction; dwp_news_2026_04_04.md '6 April' vs dwp_news_2025_04_06.md '6 April 2025' as contradiction; dwp_news_2026_04_04.md 'up to £2,100 over this parliament' vs dwp_news_2025_04_06.md 'up to £1,900' as contradiction

Detected kinds: {'complementary': 61, 'contradiction': 3, 'different_context': 538, 'historical': 57}

Ingestion: 17 documents, 107 chunks, 523 claims accepted, 124 rejected by the grounding check, 2463 s.

### B4 failures

| Question | Category | Expected | Got | Rules | Answer |
|---|---|---|---|---|---|
| R02 | outdated | VERIFIED | VERIFIED | - | The full rate of the new State Pension is £241.30 a week. |
| R04 | outdated | VERIFIED | VERIFIED | - | The Pension Credit Standard Minimum Guarantee for a single pensioner will be £227.10 a wee |
| R06 | historical | VERIFIED | NEEDS_REVIEW | R10, R5 | The full rate of the new State Pension in January 2026 was £241.30 a week. |
| R09 | normal | VERIFIED | INSUFFICIENT_EVIDENCE | R2 | I can't give a reliable answer. None of the retrieved sources is approved and in force at  |
| R12 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | The full rate of the new State Pension will be £241.30 a week from April 2027. |
| R18 | historical | VERIFIED | INSUFFICIENT_EVIDENCE | R2 | I can't give a reliable answer. None of the retrieved sources is approved and in force at  |
| R19 | historical | VERIFIED | INSUFFICIENT_EVIDENCE | R2 | I can't give a reliable answer. None of the retrieved sources is approved and in force at  |
| R24 | normal | VERIFIED | VERIFIED | - | The VAT distance selling threshold for businesses based in Northern Ireland is £90,000. |
| R27 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | The VAT registration threshold will be £90,000 from April 2027. |
| R28 | outdated | VERIFIED | VERIFIED | - | The yearly repayment threshold for Plan 2 student loans is £21,000. |
| R38 | historical | VERIFIED | VERIFIED | - | The yearly repayment threshold for Plan 2 student loans in July 2024 was £2,274. |
| R41 | multi_doc | VERIFIED | VERIFIED | - | The yearly Plan 1 repayment threshold in July 2024 was £24,990, which remained the same as |
| R52 | multi_doc | VERIFIED | VERIFIED | - | The HSA contribution limit for self-only coverage increased from $4,400 in 2025 to $4,400  |
