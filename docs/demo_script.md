# Demo video script (about 5 minutes)

Setup before recording: Ollama running, API started on a fresh data folder
(`.\scripts\run_api.ps1 -DataDir data/demo_video`), UI started (`.\scripts\run_ui.ps1`).

## 1. The problem (30 s)
"Ordinary RAG retrieves whatever text is most similar. When a policy changes, the old version, a wiki
page that copied it and a draft of the next version are all still in the index. Ordinary RAG
answers confidently from any of them."

## 2. Upload versions (60 s)
Knowledge Base page: upload the dev HR documents from `benchmark/corpus/dev/hr_leave/`:
`leave_policy_v1.md`, `leave_policy_v2.md`, `employee_handbook_2025.md`, `onboarding_guide.md`.
* Show the version family: v1 is superseded by v2 from 2026-06-01.
* Show the metadata provenance column (front matter vs user).

## 3. Overview and Conflict Center (60 s)
* Overview: open contradictions, outdated references, knowledge health.
* Conflict Center: the onboarding guide still says 20 days ("outdated, possible"), v1 vs v2 is
  "historical". Open one finding and show both quotes and the explanation.
* Resolve it: mark v2 as authoritative and add a note.

## 4. Ask (90 s)
Ask page, pipeline **B0**: "How many days of annual leave do full-time employees get?" It may answer
20 (stale), with no warning.
Switch to **B4**:
* answer 25 days, VERIFIED, citation to v2 in force;
* warnings about the superseded v1 and the outdated onboarding guide;
* the decision trace (analyze, retrieve, claims, conflicts, rank, generate, verify).

Historical: "How many days did full-time employees get in March 2026?" gives 20, VERIFIED, from v1.

Unanswerable: "Which password manager product does Halden use?" gives INSUFFICIENT_EVIDENCE.

## 5. Contradiction (30 s)
Upload `benchmark/corpus/dev/approvals/`. Ask "Above what amount is director approval required?"
and get NEEDS_REVIEW, showing the $500 vs $1,000 sources of equal authority.

## 6. Evaluation (30 s)
Evaluation page: B0 to B4 on the held-out test split, with stale answer rate, unsupported answer rate,
reliability and confidence intervals. Point out where B4 is *not* better (latency, over-abstention).

## 7. Close (15 s)
Local models only (qwen2.5 7B, nomic-embed-text, bge-reranker-base), no API cost, every number on
screen reproducible with `python -m evaluation.run`.
