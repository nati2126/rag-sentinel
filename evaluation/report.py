"""Render the result tables of results/<split>_summary.json as Markdown (pasted into docs/evaluation_report.md).

python -m evaluation.report --split test > results/test_tables.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from evaluation.run import RESULTS


def pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def table(header: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test_v2", help="split, or split__tag for a tagged run")
    args = ap.parse_args()
    s = json.loads((RESULTS / f"{args.split}_summary.json").read_text(encoding="utf-8"))
    env = s["environment"]
    print(f"Split **{s['split']}**, {s['questions']} questions, as of {s['as_of']}, generated {s['generated_at']}.  ")
    print(f"LLM `{env['llm']}`, embedder `{env['embedder']}`, reranker `{env['reranker']}`, "
          f"min_relevance {env['min_relevance']}.\n")  # fmt: skip

    P = s["pipelines"]
    print("### Answer reliability\n")
    rows = []
    for name, p in P.items():
        m, k = p["metrics"], p["metrics"]["counts"]
        ci, cc = m["reliability_ci95"], m.get("reliability_ci95_clustered")
        rows.append([
            name,
            f"{k['reliable']}/{k['questions']} ({pct(m['reliability'])})",
            f"[{pct(ci[0])}, {pct(ci[1])}]" if ci else "",
            f"[{pct(cc[0])}, {pct(cc[1])}]" if cc else "",
            f"{k['correct_presented']}/{k['verified_gold']}",
            f"{k['stale_presented']}/{k['stale_questions']}",
            f"{k['unsupported_presented']}/{k['abstain_gold']}",
            f"{k['over_abstained']}/{k['verified_gold']}",
            pct(m["decision_accuracy"]),
            f"{(m['latency_ms']['p50'] or 0) / 1000:.1f} / {(m['latency_ms']['p95'] or 0) / 1000:.1f}",
        ])  # fmt: skip
    print(table(["Pipeline", "Reliable", "95% CI (questions)", "95% CI (clustered by group)", "Correct answers",
                 "Stale answers", "Unsupported answers", "Over-abstained", "Decision acc.", "Latency p50/p95 s"],
                rows))  # fmt: skip
    groups = next(iter(P.values()))["metrics"]["counts"]["groups"]
    print(f"\nClustered intervals resample the {groups} document groups, because questions about the same "
          "documents are correlated.")  # fmt: skip

    print("\n### Retrieval and grounding\n")
    rows = [[n, pct(p["metrics"]["recall_at_5"]), pct(p["metrics"]["mrr_at_5"]), pct(p["metrics"]["citation_precision"]),
             pct(p["metrics"]["faithfulness_numeric"]), pct(p["metrics"]["abstention_precision"]),
             pct(p["metrics"]["abstention_recall"])] for n, p in P.items()]  # fmt: skip
    print(table(["Pipeline", "Recall@5", "MRR@5", "Citation precision", "Numeric faithfulness",
                 "Abstention precision", "Abstention recall"], rows))  # fmt: skip

    cats = sorted({c for p in P.values() for c in p["metrics"]["reliability_by_category"]})
    print("\n### Reliability by category\n")
    rows = [[n] + [pct(p["metrics"]["reliability_by_category"].get(c)) for c in cats] for n, p in P.items()]
    counts = Counter(r["category"] for r in _records(args.split) if r["pipeline"] == "B4")
    print(table(["Pipeline"] + [f"{c} (n={counts.get(c, 0)})" for c in cats], rows))

    if "comparisons_vs_B4" in s:
        print("\n### Paired comparison with B4 (reliability)\n")
        rows = []
        for n, c in s["comparisons_vs_B4"].items():
            d, dc = c["reliability_diff"], c.get("reliability_diff_clustered")
            mc = c["mcnemar"]
            rows.append([n, f"{d['diff']:+.1%}" if d else "n/a", f"[{d['ci95'][0]:+.1%}, {d['ci95'][1]:+.1%}]" if d else "",
                         f"[{dc['ci95'][0]:+.1%}, {dc['ci95'][1]:+.1%}]" if dc else "",
                         f"{mc['b01']} / {mc['b10']}", f"{mc['p_value']:.3g}"])  # fmt: skip
        print(table(["vs", "B4 minus pipeline", "95% CI (paired)", "95% CI (paired, clustered)", "B4 better / worse",
                     "McNemar p (assumes independent questions)"], rows))  # fmt: skip

    cd = s["conflict_detection"]
    print(
        f"\n### Conflict detection (corpus level, {cd['gold_actionable']} actionable gold pairs of {cd['gold_pairs']})\n"
    )
    rows = []
    for n, v in cd.items():
        if isinstance(v, dict) and "precision" in v:
            rows.append([n.replace("_", " "), pct(v["precision"]), pct(v["recall"]), pct(v["f1"]),
                         f"{v['tp']}/{v['fp']}/{v['fn']}", pct(v["kind_accuracy_on_matched_gold_pairs"]),
                         str(v["gold_pairs_matched_any_kind"])])  # fmt: skip
    print(table(["Detector", "Precision", "Recall", "F1", "TP/FP/FN", "Kind acc. (matched)", "Gold pairs found"], rows))
    full = cd["rules_plus_llm_judge"]
    if full["missed"]:
        print("\nMissed (full detector): " + "; ".join(f"{m['a']} vs {m['b']} ({m['topic']})" for m in full["missed"]))
    if full["false_positive_examples"]:
        print("\nFalse positives (full detector): " + "; ".join(
            f"{m['a']} '{m['a_value']}' vs {m['b']} '{m['b_value']}' as {m['kind']}" for m in full["false_positive_examples"]))  # fmt: skip
    print(f"\nDetected kinds: {cd['detected_kinds']}")

    ing = s["ingestion"]
    print(f"\nIngestion: {ing['documents']} documents, {ing['chunks']} chunks, {ing['claims_accepted']} claims "
          f"accepted, {ing['claims_rejected']} rejected by the grounding check, {ing['ingest_seconds']:.0f} s.")  # fmt: skip

    print("\n### B4 failures\n")
    rows = [[r["id"], r["category"], r["expected_decision"], r["status"], ", ".join(r["rules_fired"]) or "-",
             (r["answer"] or "")[:90].replace("|", "/")]
            for r in _records(args.split) if r["pipeline"] == "B4" and not _ok(r)]  # fmt: skip
    print(table(["Question", "Category", "Expected", "Got", "Rules", "Answer"], rows) if rows else "None.")


def _records(split: str) -> list[dict]:
    path = RESULTS / f"{split}_records.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _ok(r: dict) -> bool:
    from evaluation.run import success

    return bool(success(r))


if __name__ == "__main__":
    main()
