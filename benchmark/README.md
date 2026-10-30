# VersionConflict benchmark

A small, fully documented benchmark for **version-aware, conflict-aware** question answering over
document collections. It is designed to measure stale answers, unsupported answers and contradiction
detection, which ordinary RAG benchmarks do not test.

## Contents

```
benchmark/
  corpus/dev/<group>/...      documents used for development and threshold tuning
  corpus/test/<group>/...     held-out documents, used only for reported results
  questions/dev.jsonl         questions over the dev corpus
  questions/test.jsonl        questions over the test corpus
  conflicts/dev.json          gold document-conflict annotations (dev)
  conflicts/test.json         gold document-conflict annotations (test)
  sources/                    Markdown sources for the PDF/DOCX files (see build_binary_docs.py)
```

Dev and test use **disjoint document groups** and are indexed into **separate knowledge bases**, so
nothing tuned on dev can see test documents.

## Document provenance

* **Synthetic** documents describe a fictional company, *Halden Systems*. All names, values and dates are
  invented for the benchmark.
* **Public-derived** documents (`*_summary.md`, `source_org` = the real publisher) are short paraphrased
  summaries written for this benchmark of well-known public facts: RFC 8996 (TLS 1.0/1.1 deprecation, 2021),
  Python's distutils deprecation (PEP 632, Python 3.10) and removal (Python 3.12), Kubernetes' dockershim
  deprecation (v1.20) and removal (v1.24), and NIST SP 800-63B (2017) password guidance. They are not
  verbatim copies; consult the original sources for authoritative text.

Metadata (effective date, authority level 1-5, approval status, supersedes) is given in front matter or
`.meta.yaml` sidecars. This simulates a user supplying metadata at upload; RAG Sentinel never invents it.

## Reference date

All questions are evaluated **as of 2026-10-01** unless the question itself names a date.

## Annotation guideline (expected decision)

The expected decision follows these principles, written before the system was evaluated:

| Decision | When |
|---|---|
| `VERIFIED` | An approved source that is in force at the as-of date, with the highest standing among the sources stating the fact, answers the question. Older, superseded or lower-authority documents that disagree do not prevent a verified answer (the system should warn about them). |
| `NEEDS_REVIEW` | Two or more approved, in-force sources of comparable authority disagree about the asked fact and nothing (supersession, scope, approval) resolves it. |
| `INSUFFICIENT_EVIDENCE` | The corpus does not contain the answer, or only draft / withdrawn / not-yet-effective sources address it. |

Question categories: `normal`, `multi_doc`, `historical`, `contradiction`, `outdated`, `unanswerable`.

## Question format

```json
{
  "id": "T-travel-01",
  "split": "test",
  "group": "travel",
  "category": "outdated",
  "question": "What is the domestic meal per diem?",
  "expected": [["$60", "60"]],
  "stale": ["$50", "$70"],
  "gold_evidence": [{"file": "travel_policy_2026.md", "contains": "$60"}],
  "expected_decision": "VERIFIED",
  "note": "2025 policy and quick guide say $50; the approved 2027 policy ($70) is not yet effective."
}
```

* `expected`: all groups must be matched; within a group any alternative matches (case-insensitive substring,
  numbers compared after normalisation).
* `stale`: values that are outdated, superseded, draft or not yet effective for this question.
* `gold_evidence`: a retrieved passage is relevant if it comes from `file` and contains `contains`.

## Conflict annotations

`conflicts/<split>.json` lists document pairs whose claims about the same fact differ, labelled
`contradiction`, `outdated`, `historical` or `different_context`. Detection precision/recall count
`contradiction` + `outdated` as positives (the ones that need human attention).
