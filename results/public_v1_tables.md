Split **public_v1**, 44 questions, as of 2026-10-01, generated 2026-11-02T10:02:07+00:00.  
LLM `qwen2.5:7b-instruct`, embedder `nomic-embed-text`, reranker `BAAI/bge-reranker-base`, min_relevance 0.0.

### Answer reliability

| Pipeline | Reliable | 95% CI (questions) | 95% CI (clustered by group) | Correct answers | Stale answers | Unsupported answers | Over-abstained | Decision acc. | Latency p50/p95 s |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 33/44 (75.0%) | [61.4%, 86.4%] | [67.9%, 87.5%] | 25/36 | 3/25 | 0/8 | 3/36 | 93.2% | 2.0 / 3.5 |
| B1 | 32/44 (72.7%) | [59.1%, 84.1%] | [56.6%, 89.7%] | 24/36 | 4/25 | 0/8 | 2/36 | 95.5% | 1.9 / 2.6 |
| B2 | 38/44 (86.4%) | [75.0%, 95.5%] | [74.5%, 100.0%] | 30/36 | 2/25 | 0/8 | 2/36 | 95.5% | 4.4 / 5.3 |
| B3 | 40/44 (90.9%) | [81.8%, 97.7%] | [85.1%, 96.5%] | 34/36 | 0/25 | 2/8 | 1/36 | 93.2% | 4.5 / 5.8 |
| B4 | 37/44 (84.1%) | [72.7%, 93.2%] | [74.5%, 94.7%] | 29/36 | 0/25 | 0/8 | 7/36 | 84.1% | 6.3 / 8.0 |
| B4-no-rerank | 35/44 (79.5%) | [65.9%, 90.9%] | [68.4%, 89.7%] | 27/36 | 0/25 | 0/8 | 7/36 | 81.8% | 3.8 / 5.6 |
| B4-relevance-ranking | 33/44 (75.0%) | [61.4%, 86.4%] | [68.0%, 86.2%] | 25/36 | 1/25 | 0/8 | 9/36 | 77.3% | 6.7 / 8.8 |
| B4-newest-wins | 28/44 (63.6%) | [50.0%, 77.3%] | [52.6%, 72.0%] | 20/36 | 0/25 | 0/8 | 16/36 | 63.6% | 6.2 / 8.1 |
| B4-no-conflicts | 37/44 (84.1%) | [72.7%, 93.2%] | [70.2%, 94.7%] | 29/36 | 0/25 | 0/8 | 7/36 | 79.5% | 4.8 / 7.4 |
| B4-no-gating | 40/44 (90.9%) | [81.8%, 97.7%] | [87.2%, 96.2%] | 33/36 | 0/25 | 1/8 | 0/36 | 97.7% | 4.9 / 6.2 |
| B4-no-answer-check | 37/44 (84.1%) | [72.7%, 93.2%] | [79.0%, 90.6%] | 29/36 | 0/25 | 0/8 | 6/36 | 84.1% | 4.6 / 5.9 |

Clustered intervals resample the 4 document groups, because questions about the same documents are correlated.

### Retrieval and grounding

| Pipeline | Recall@5 | MRR@5 | Citation precision | Numeric faithfulness | Abstention precision | Abstention recall |
|---|---|---|---|---|---|---|
| B0 | 70.4% | 55.0% | 47.5% | 90.9% | 72.7% | 100.0% |
| B1 | 73.2% | 57.2% | 48.6% | 97.1% | 80.0% | 100.0% |
| B2 | 83.8% | 67.7% | 49.3% | 91.2% | 80.0% | 100.0% |
| B3 | 90.3% | 81.6% | 68.8% | 91.9% | 85.7% | 75.0% |
| B4 | 90.3% | 81.6% | 67.7% | 86.5% | 53.3% | 100.0% |
| B4-no-rerank | 90.7% | 82.4% | 63.5% | 89.2% | 53.3% | 100.0% |
| B4-relevance-ranking | 83.8% | 67.7% | 71.7% | 89.5% | 47.1% | 100.0% |
| B4-newest-wins | 77.8% | 73.8% | 61.2% | 73.7% | 33.3% | 100.0% |
| B4-no-conflicts | 90.3% | 81.6% | 70.2% | 86.8% | 53.3% | 100.0% |
| B4-no-gating | 90.3% | 81.6% | 65.8% | 97.3% | 100.0% | 87.5% |
| B4-no-answer-check | 90.3% | 81.6% | 65.7% | 89.2% | 57.1% | 100.0% |

### Reliability by category

| Pipeline | historical (n=8) | multi_doc (n=2) | normal (n=12) | outdated (n=14) | unanswerable (n=8) |
|---|---|---|---|---|---|
| B0 | 75.0% | 0.0% | 83.3% | 64.3% | 100.0% |
| B1 | 37.5% | 50.0% | 75.0% | 78.6% | 100.0% |
| B2 | 75.0% | 50.0% | 100.0% | 78.6% | 100.0% |
| B3 | 100.0% | 50.0% | 91.7% | 100.0% | 75.0% |
| B4 | 75.0% | 0.0% | 91.7% | 85.7% | 100.0% |
| B4-no-rerank | 87.5% | 50.0% | 83.3% | 64.3% | 100.0% |
| B4-relevance-ranking | 75.0% | 0.0% | 75.0% | 71.4% | 100.0% |
| B4-newest-wins | 12.5% | 0.0% | 66.7% | 78.6% | 100.0% |
| B4-no-conflicts | 75.0% | 50.0% | 75.0% | 92.9% | 100.0% |
| B4-no-gating | 100.0% | 50.0% | 91.7% | 92.9% | 87.5% |
| B4-no-answer-check | 75.0% | 0.0% | 91.7% | 85.7% | 100.0% |

### Paired comparison with B4 (reliability)

| vs | B4 minus pipeline | 95% CI (paired) | 95% CI (paired, clustered) | B4 better / worse | McNemar p (assumes independent questions) |
|---|---|---|---|---|---|
| B0 | +9.1% | [-2.3%, +22.7%] | [+0.0%, +17.9%] | 6 / 2 | 0.289 |
| B1 | +11.4% | [-4.5%, +27.3%] | [+0.0%, +19.1%] | 9 / 4 | 0.267 |
| B2 | -2.3% | [-15.9%, +13.6%] | [-22.6%, +17.0%] | 5 / 6 | 1 |
| B3 | -6.8% | [-18.2%, +4.5%] | [-17.0%, +0.0%] | 2 / 5 | 0.453 |
| B4-no-rerank | +4.5% | [-9.1%, +18.2%] | [-10.5%, +16.0%] | 5 / 3 | 0.727 |
| B4-relevance-ranking | +9.1% | [-2.3%, +20.4%] | [+0.0%, +16.0%] | 6 / 2 | 0.289 |
| B4-newest-wins | +20.4% | [+6.8%, +34.1%] | [+12.8%, +31.0%] | 10 / 1 | 0.0117 |
| B4-no-conflicts | +0.0% | [-11.4%, +13.6%] | [-15.8%, +14.9%] | 4 / 4 | 1 |
| B4-no-gating | -6.8% | [-18.2%, +2.3%] | [-12.8%, +0.0%] | 1 / 4 | 0.375 |
| B4-no-answer-check | +0.0% | [-6.8%, +6.8%] | [-5.4%, +10.3%] | 1 / 1 | 1 |

### Conflict detection (corpus level, 2 actionable gold pairs of 10)

| Detector | Precision | Recall | F1 | TP/FP/FN | Kind acc. (matched) | Gold pairs found |
|---|---|---|---|---|---|---|
| naive value difference | 0.0% | 50.0% | 0.1% | 1/2744/1 | 0.0% | 6/10 |
| rules only | n/a | 0.0% | n/a | 0/0/2 | 0.0% | 6/10 |
| rules plus llm judge | 0.0% | 0.0% | 0.0% | 0/7/2 | 66.7% | 6/10 |

Missed (full detector): irs_news_ir_2025_128.md vs irs_announcement_2026_11.md (business standard mileage rate); irs_news_ir_2025_128.md vs irs_announcement_2026_11.md (medical standard mileage rate)

False positives (full detector): irs_news_ir_2025_111.md '$1,100' vs irs_notice_2025_67.pdf '$3,850' as outdated; irs_news_ir_2025_128.md '72.5 cents' vs irs_notice_2026_10.pdf '20.5 cents' as outdated; irs_news_ir_2025_128.md '72.5 cents' vs irs_notice_2026_10.pdf '35 cents per mile' as outdated; irs_news_ir_2025_128.md '72.5 cents' vs irs_standard_mileage_rates_page.md 'cents/mile' as outdated; irs_news_ir_2025_128.md '72.5 cents' vs irs_standard_mileage_rates_page.md '20.5' as outdated; irs_notice_2026_10.pdf '20.5 cents' vs irs_standard_mileage_rates_page.md '72.5' as contradiction; irs_notice_2026_10.pdf '35 cents per mile' vs irs_standard_mileage_rates_page.md 'cents/mile' as contradiction

Detected kinds: {'complementary': 43, 'contradiction': 2, 'different_context': 3214, 'historical': 538, 'outdated': 5}

Ingestion: 14 documents, 247 chunks, 830 claims accepted, 185 rejected by the grounding check, 8717 s.

### B4 failures

| Question | Category | Expected | Got | Rules | Answer |
|---|---|---|---|---|---|
| P01 | outdated | VERIFIED | NEEDS_REVIEW | R10, R5, R8 | The IRS standard mileage rate for business use of a car on 2026-10-01 is 20.5 cents per mi |
| P04 | historical | VERIFIED | INSUFFICIENT_EVIDENCE | R4 | I can't give a reliable answer. The answer has no valid citation to the provided evidence. |
| P05 | historical | VERIFIED | NEEDS_REVIEW | R10 | The IRS business standard mileage rate in March 2026 was 72.5 cents per mile for business  |
| P11 | multi_doc | VERIFIED | NEEDS_REVIEW | R8 | The IRS business standard mileage rates for the first half of 2026 were 72.5 cents per mil |
| P17 | outdated | VERIFIED | INSUFFICIENT_EVIDENCE | R4 | I can't give a reliable answer. The answer has no valid citation to the provided evidence. |
| P23 | normal | VERIFIED | NEEDS_REVIEW | R10 | The IRA catch-up contribution limit for individuals aged 50 and over in 2026 is $8,000. |
| P37 | multi_doc | VERIFIED | INSUFFICIENT_EVIDENCE | R2 | I can't give a reliable answer. None of the retrieved sources is approved and in force at  |
