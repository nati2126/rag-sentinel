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
  build_public_v2_questions.py writes the public_v2 questions and conflict annotations
  html_to_markdown.py          converts a downloaded web page to Markdown (text unchanged)
```

| Split | Role | Questions | Documents |
|---|---|---|---|
| `dev` | development, threshold tuning | 26 | 14 synthetic and public-derived |
| `test_v1` | development (the v0.1 test split, retired after its failures were analysed) | 88 | 44 synthetic and public-derived |
| `test_v2` | held out, run once (v0.2) | 81 | 40 synthetic and public-derived |
| `public_v1` | held out, run once (v0.2), **real public documents** | 44 | 14 real IRS and UK government documents |
| `public_v2` | held out, run once (v0.3), **real public documents** | 55 | 17 real IRS, HealthCare.gov and UK government documents |

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

### public_v2 sources

`public_v2` was written and committed (tag `public-v2-split`) before any v0.3 code change. It covers four
topics that no public_v1 question asks about: the UK new State Pension, UK VAT registration, UK student loan
repayment and US Health Savings Accounts. (public_v1's HMRC employer pages also list student loan thresholds,
but none of its questions use them, and public_v1 question P24 only checks that HSAs are *not* covered there.)

The documents were downloaded on 2026-11-27 and converted with `html_to_markdown.py`, with the same rules as
public_v1. Superseded versions of GOV.UK pages are **Internet Archive (Wayback Machine) captures** of the same
page, taken before the values changed. The split contains:
* year-to-year changes kept as a version family (three versions of the State Pension, VAT and student loan
  pages; four HSA revenue procedures);
* dated press releases that are never superseded but state last year's rates;
* a published but not yet effective document (Rev. Proc. 2026-24, the 2027 HSA amounts) and an in-force page
  that already states the 2027 amounts next to the 2026 ones;
* long previous-threshold tables (VAT Notice 700/1 supplement);
* page noise as published, such as a table caption "In 2026" under HealthCare.gov's 2027 table.

Metadata dates come from the documents: the page's GOV.UK "updated" timestamp for each version, the release
date of a press release, the calendar year an IRS revenue procedure covers, and the HTTP last-modified date of
the HealthCare.gov page. When a document in the corpus states when new rates applied (the State Pension
press releases, the VAT policy paper), that date is the effective date of the page version carrying them.
Authority levels follow the public_v1 rule (5 IRS revenue procedures and HMRC notices, 4 GOV.UK and
HealthCare.gov guidance pages and the HMRC policy paper, 3 press releases).

The reference date for `public_v2` is **2026-11-27**, its download date, because several current pages were
last updated after 2026-10-01. Historical questions avoid the gaps where a page version's timestamp is later
than the date its rates started.

| File | Source |
|---|---|
| `uk_state_pension/govuk_new_state_pension_2024.md` | https://web.archive.org/web/20240601000000/https://www.gov.uk/new-state-pension/what-youll-get |
| `uk_state_pension/govuk_new_state_pension_2025.md` | https://web.archive.org/web/20250513000000/https://www.gov.uk/new-state-pension/what-youll-get |
| `uk_state_pension/govuk_new_state_pension_2026.md` | https://www.gov.uk/new-state-pension/what-youll-get |
| `uk_state_pension/dwp_news_2025_04_06.md` | https://www.gov.uk/government/news/huge-income-boost-for-millions-of-pensioners-and-working-people |
| `uk_state_pension/dwp_news_2026_04_04.md` | https://www.gov.uk/government/news/over-12-million-pensioners-to-receive-575-state-pension-boost |
| `uk_vat_registration/govuk_vat_registration_2022.md` | https://web.archive.org/web/20220501000000/https://www.gov.uk/vat-registration/when-to-register |
| `uk_vat_registration/govuk_register_for_vat_2026.md` | https://www.gov.uk/register-for-vat |
| `uk_vat_registration/hmrc_vat_threshold_increase_2024.md` | https://www.gov.uk/government/publications/vat-increasing-the-registration-and-deregistration-thresholds/increasing-the-vat-registration-threshold |
| `uk_vat_registration/hmrc_vat_notice_700_1_supplement.md` | https://www.gov.uk/government/publications/vat-notice-7001-should-i-be-registered-for-vat/vat-notice-7001-supplement--2 |
| `uk_student_loans/govuk_repaying_student_loan_2024.md` | https://web.archive.org/web/20240531000000/https://www.gov.uk/repaying-your-student-loan/what-you-pay |
| `uk_student_loans/govuk_repaying_student_loan_2025.md` | https://web.archive.org/web/20250621000000/https://www.gov.uk/repaying-your-student-loan/what-you-pay |
| `uk_student_loans/govuk_repaying_student_loan_2026.md` | https://www.gov.uk/repaying-your-student-loan/what-you-pay |
| `irs_hsa/irs_rp_23_23.pdf` | https://www.irs.gov/pub/irs-drop/rp-23-23.pdf |
| `irs_hsa/irs_rp_24_25.pdf` | https://www.irs.gov/pub/irs-drop/rp-24-25.pdf |
| `irs_hsa/irs_rp_25_19.pdf` | https://www.irs.gov/pub/irs-drop/rp-25-19.pdf |
| `irs_hsa/irs_rp_26_24.pdf` | https://www.irs.gov/pub/irs-drop/rp-26-24.pdf |
| `irs_hsa/healthcare_gov_hsa_eligible_plans.md` | https://www.healthcare.gov/high-deductible-health-plan/ |

Licences as for public_v1: US federal works are in the public domain; GOV.UK content is under the Open
Government Licence v3.0. Wayback captures are of the same Crown-copyright pages.

## Reference date

All questions are evaluated **as of 2026-10-01** (public_v2: **2026-11-27**) unless the question itself names a date.

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
