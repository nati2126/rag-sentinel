# VersionConflict benchmark

A small, fully documented benchmark for **version-aware, conflict-aware** question answering over
document collections. It is designed to measure stale answers, unsupported answers and contradiction
detection, which ordinary RAG benchmarks do not test.

## Contents

```
benchmark/
  corpus/<split>/<group>/...   documents, one knowledge base per split
  questions/<split>.jsonl      questions
  conflicts/<split>.json       gold document-conflict annotations
  sources/                     Markdown sources for the synthetic PDF/DOCX files (see build_binary_docs.py)
  build_public_questions.py    writes the public_v1 questions and conflict annotations
```

| Split | Role | Questions | Documents |
|---|---|---|---|
| `dev` | development, threshold tuning | 26 | 14 synthetic and public-derived |
| `test_v1` | development (the v0.1 test split, retired after its failures were analysed) | 88 | 44 synthetic and public-derived |
| `test_v2` | held out, run once (v0.2) | 81 | 40 synthetic and public-derived |
| `public_v1` | held out, run once (v0.2), **real public documents** | 44 | 14 real IRS and UK government documents |

Splits use **disjoint document groups** and are indexed into **separate knowledge bases**, so nothing
tuned on one split can see another split's documents.

## Document provenance

* **Synthetic** documents (dev, test_v1, test_v2) describe a fictional company, *Halden Systems*. All names,
  values and dates are invented for the benchmark.
* **Public-derived** documents (`*_summary.md`, `source_org` = the real publisher) are short paraphrased
  summaries written for this benchmark of well-known public facts: RFC 8996 (TLS 1.0/1.1 deprecation, 2021),
  Python's distutils deprecation (PEP 632, Python 3.10) and removal (Python 3.12), Kubernetes' dockershim
  deprecation (v1.20) and removal (v1.24), and NIST SP 800-63B (2017) password guidance. They are not
  verbatim copies; consult the original sources for authoritative text.
* **Real public documents** (`public_v1`) were downloaded on 2026-11-02 and are **not edited**. PDFs are the
  original files. Web pages were converted to Markdown with their text unchanged; only site navigation, menus and
  footers were removed, and the page title was added as the first heading where it sits outside the page body.
  They contain real year-to-year changes, a mid-year revision (the IRS raised the 2026 mileage rates from July 1,
  2026, while its December 2025 news release still states the January rates) and an announced future rate (the
  April 2027 UK minimum wage, not yet in force on the reference date).

Metadata (effective date, authority level 1-5, approval status, supersedes) is given in front matter or
`.meta.yaml` sidecars. This simulates a user supplying metadata at upload; RAG Sentinel never invents it.
For `public_v1` the dates come from the documents themselves (the tax year a notice covers, a release date,
a page's published and last-updated dates). One exception: the minimum wage page's machine-readable
modified date (2024-10-30) is older than its content, so its effective date is taken from its own
"Current rates" table (April 2026). Authority levels were assigned by rule: 5 for primary guidance (IRS
notices and announcements, HMRC rates and thresholds), 4 for official summary pages, 3 for news releases.

### public_v1 sources

US federal government works are in the public domain. UK pages contain public sector information licensed
under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).

| File | Source |
|---|---|
| `irs_mileage/irs_notice_2024_08.pdf` | https://www.irs.gov/pub/irs-drop/n-24-08.pdf |
| `irs_mileage/irs_notice_2025_05.pdf` | https://www.irs.gov/pub/irs-drop/n-25-05.pdf |
| `irs_mileage/irs_notice_2026_10.pdf` | https://www.irs.gov/pub/irs-drop/n-26-10.pdf |
| `irs_mileage/irs_announcement_2026_11.md` | https://www.irs.gov/irb/2026-29_irb (Announcement 2026-11 section only) |
| `irs_mileage/irs_news_ir_2025_128.md` | https://www.irs.gov/newsroom/irs-sets-2026-business-standard-mileage-rate-at-725-cents-per-mile-up-25-cents |
| `irs_mileage/irs_standard_mileage_rates_page.md` | https://www.irs.gov/tax-professionals/standard-mileage-rates |
| `irs_retirement/irs_notice_2023_75.pdf` | https://www.irs.gov/pub/irs-drop/n-23-75.pdf |
| `irs_retirement/irs_notice_2024_80.pdf` | https://www.irs.gov/pub/irs-drop/n-24-80.pdf |
| `irs_retirement/irs_notice_2025_67.pdf` | https://www.irs.gov/pub/irs-drop/n-25-67.pdf |
| `irs_retirement/irs_news_ir_2025_111.md` | https://www.irs.gov/newsroom/401k-limit-increases-to-24500-for-2026-ira-limit-increases-to-7500 |
| `uk_employer_rates/hmrc_rates_and_thresholds_2024_to_2025.md` | https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2024-to-2025 |
| `uk_employer_rates/hmrc_rates_and_thresholds_2025_to_2026.md` | https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2025-to-2026 |
| `uk_employer_rates/hmrc_rates_and_thresholds_2026_to_2027.md` | https://www.gov.uk/guidance/rates-and-thresholds-for-employers-2026-to-2027 |
| `uk_minimum_wage/govuk_minimum_wage_rates.md` | https://www.gov.uk/national-minimum-wage-rates |

These documents are a snapshot for benchmarking, not tax or payroll advice. Check the publishers' current pages.

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
