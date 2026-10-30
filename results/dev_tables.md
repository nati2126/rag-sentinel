Split **dev**, 26 questions, as of 2026-10-01, generated 2026-10-30T09:56:01+00:00.  
LLM `qwen2.5:7b-instruct`, embedder `nomic-embed-text`, reranker `BAAI/bge-reranker-base`, min_relevance 0.0.

### Answer reliability

| Pipeline | Reliability [95% CI] | Answer acc. | Stale rate | Unsupported rate | Over-abstention | Decision acc. | Latency p50/p95 s |
|---|---|---|---|---|---|---|---|
| B0 | 76.9% [57.7%, 92.3%] | 85.7% | 27.3% | 60.0% | 0.0% | 88.5% | 1.2 / 1.6 |
| B1 | 76.9% [57.7%, 92.3%] | 85.7% | 27.3% | 60.0% | 0.0% | 88.5% | 1.2 / 1.6 |
| B2 | 73.1% [53.8%, 88.5%] | 81.0% | 36.4% | 60.0% | 0.0% | 88.5% | 2.2 / 2.8 |
| B3 | 88.5% [76.9%, 100.0%] | 95.2% | 9.1% | 40.0% | 0.0% | 92.3% | 2.3 / 3.0 |
| B4 | 96.2% [88.5%, 100.0%] | 100.0% | 0.0% | 20.0% | 0.0% | 96.2% | 2.5 / 2.9 |

### Retrieval and grounding

| Pipeline | Recall@5 | MRR@5 | Citation precision | Numeric faithfulness | Abstention precision | Abstention recall |
|---|---|---|---|---|---|---|
| B0 | 100.0% | 78.8% | 74.1% | 100.0% | 100.0% | 40.0% |
| B1 | 100.0% | 84.1% | 70.4% | 100.0% | 100.0% | 40.0% |
| B2 | 100.0% | 85.6% | 58.1% | 100.0% | 100.0% | 40.0% |
| B3 | 100.0% | 100.0% | 91.3% | 100.0% | 100.0% | 60.0% |
| B4 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 80.0% |

### Reliability by category

| Pipeline | contradiction (n=2) | historical (n=4) | multi_doc (n=2) | normal (n=8) | outdated (n=6) | unanswerable (n=4) |
|---|---|---|---|---|---|---|
| B0 | 50.0% | 75.0% | 100.0% | 100.0% | 66.7% | 50.0% |
| B1 | 50.0% | 75.0% | 50.0% | 100.0% | 83.3% | 50.0% |
| B2 | 50.0% | 75.0% | 50.0% | 100.0% | 66.7% | 50.0% |
| B3 | 50.0% | 100.0% | 100.0% | 100.0% | 83.3% | 75.0% |
| B4 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 75.0% |

### Paired comparison with B4 (reliability)

| vs | B4 minus pipeline | 95% CI (paired bootstrap) | B4 better / worse | McNemar p |
|---|---|---|---|---|
| B0 | +19.2% | [+3.9%, +34.6%] | 5 / 0 | 0.0625 |
| B1 | +19.2% | [+3.9%, +34.6%] | 5 / 0 | 0.0625 |
| B2 | +23.1% | [+7.7%, +42.3%] | 6 / 0 | 0.0312 |
| B3 | +7.7% | [+0.0%, +19.2%] | 2 / 0 | 0.5 |

### Conflict detection (corpus level, 6 actionable gold pairs of 11)

| Detector | Precision | Recall | F1 | TP/FP/FN | Kind acc. (matched) | Gold pairs found |
|---|---|---|---|---|---|---|
| naive value difference | 17.9% | 83.3% | 29.4% | 5/23/1 | 11.1% | 9/11 |
| rules only | 83.3% | 83.3% | 83.3% | 5/1/1 | 100.0% | 9/11 |
| rules plus llm judge | 100.0% | 66.7% | 80.0% | 4/0/2 | 88.9% | 9/11 |

Missed (full detector): onboarding_guide.md vs leave_policy_v2.md (annual leave); it_helpdesk_wiki.md vs password_standard_v2.md (password rotation)

Detected kinds: {'complementary': 3, 'contradiction': 1, 'different_context': 16, 'historical': 4, 'outdated': 3}

Ingestion: 14 documents, 14 chunks, 65 claims accepted, 4 rejected by the grounding check, 140 s.

### B4 failures

| Question | Category | Expected | Got | Rules | Answer |
|---|---|---|---|---|---|
| D20 | unanswerable | INSUFFICIENT_EVIDENCE | VERIFIED | - | Halden Systems uses a company password manager. |
