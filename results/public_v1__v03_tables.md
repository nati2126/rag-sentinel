Split **public_v1**, 44 questions, as of 2026-10-01, generated 2026-11-27T10:57:00+00:00.  
LLM `qwen2.5:7b-instruct`, embedder `nomic-embed-text`, reranker `BAAI/bge-reranker-base`, min_relevance 0.0.

### Answer reliability

| Pipeline | Reliable | 95% CI (questions) | 95% CI (clustered by group) | Correct answers | Stale answers | Unsupported answers | Over-abstained | Decision acc. | Latency p50/p95 s |
|---|---|---|---|---|---|---|---|---|---|
| B0 | 33/44 (75.0%) | [61.4%, 86.4%] | [67.9%, 87.5%] | 25/36 | 3/25 | 0/8 | 3/36 | 93.2% | 1.9 / 3.2 |
| B3 | 40/44 (90.9%) | [81.8%, 97.7%] | [85.1%, 96.5%] | 34/36 | 0/25 | 2/8 | 1/36 | 93.2% | 4.5 / 5.7 |
| B4 | 42/44 (95.5%) | [88.6%, 100.0%] | [92.0%, 100.0%] | 34/36 | 0/25 | 0/8 | 2/36 | 93.2% | 6.2 / 7.6 |

Clustered intervals resample the 4 document groups, because questions about the same documents are correlated.

### Retrieval and grounding

| Pipeline | Recall@5 | MRR@5 | Citation precision | Numeric faithfulness | Abstention precision | Abstention recall |
|---|---|---|---|---|---|---|
| B0 | 70.4% | 55.0% | 47.5% | 90.9% | 72.7% | 100.0% |
| B3 | 90.3% | 81.6% | 68.8% | 91.9% | 85.7% | 75.0% |
| B4 | 90.3% | 81.6% | 66.7% | 100.0% | 80.0% | 100.0% |

### Reliability by category

| Pipeline | historical (n=8) | multi_doc (n=2) | normal (n=12) | outdated (n=14) | unanswerable (n=8) |
|---|---|---|---|---|---|
| B0 | 75.0% | 0.0% | 83.3% | 64.3% | 100.0% |
| B3 | 100.0% | 50.0% | 91.7% | 100.0% | 75.0% |
| B4 | 100.0% | 50.0% | 91.7% | 100.0% | 100.0% |

### Paired comparison with B4 (reliability)

| vs | B4 minus pipeline | 95% CI (paired) | 95% CI (paired, clustered) | B4 better / worse | McNemar p (assumes independent questions) |
|---|---|---|---|---|---|
| B0 | +20.4% | [+6.8%, +34.1%] | [+6.2%, +31.9%] | 10 / 1 | 0.0117 |
| B3 | +4.5% | [+0.0%, +11.4%] | [+0.0%, +8.0%] | 2 / 0 | 0.5 |

### Conflict detection (corpus level, 2 actionable gold pairs of 10)

| Detector | Precision | Recall | F1 | TP/FP/FN | Kind acc. (matched) | Gold pairs found |
|---|---|---|---|---|---|---|
| naive value difference | 0.0% | 50.0% | 0.1% | 1/3518/1 | 0.0% | 6/10 |
| rules only | 100.0% | 50.0% | 66.7% | 1/0/1 | 16.7% | 6/10 |
| rules plus llm judge | 100.0% | 50.0% | 66.7% | 1/0/1 | 66.7% | 6/10 |

Missed (full detector): irs_news_ir_2025_128.md vs irs_announcement_2026_11.md (medical standard mileage rate)

Detected kinds: {'complementary': 40, 'different_context': 1224, 'historical': 207, 'outdated': 1}

Ingestion: 14 documents, 247 chunks, 892 claims accepted, 243 rejected by the grounding check, 2276 s.

### B4 failures

| Question | Category | Expected | Got | Rules | Answer |
|---|---|---|---|---|---|
| P23 | normal | VERIFIED | NEEDS_REVIEW | R10 | The IRA catch-up contribution limit for individuals aged 50 and over in 2026 is $8,000. |
| P37 | multi_doc | VERIFIED | INSUFFICIENT_EVIDENCE | R3 | I can't give a reliable answer. Generator could not answer: The provided documents do not  |
