"""Tune the relevance gate (min_relevance) on the dev split, offline.

Uses the dev B4 records produced with min_relevance=0: raising the threshold only turns answers whose best
evidence relevance is below it into abstentions, so every candidate can be scored without re-running the LLM.
The threshold with the highest dev reliability wins; ties go to the lowest threshold (fewest refusals).
The test split is never looked at.

    python -m evaluation.run --split dev --min-relevance 0 --force
    python -m evaluation.tune
"""

from __future__ import annotations

import argparse
import json

from evaluation.run import RESULTS, success


def simulate(records: list[dict], threshold: float) -> list[dict]:
    out = []
    for r in records:
        if r["top_relevance"] < threshold:
            r = {**r, "presented": False, "correct": False, "stale": False, "status": "INSUFFICIENT_EVIDENCE"}
        out.append(r)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pipeline", default="B4")
    args = ap.parse_args()

    summary = json.loads((RESULTS / "dev_summary.json").read_text(encoding="utf-8"))
    used = summary["environment"]["min_relevance"]
    if used != 0:
        raise SystemExit(f"dev records were produced with min_relevance={used}; re-run dev with --min-relevance 0")
    records = [
        r
        for line in (RESULTS / "dev_records.jsonl").read_text(encoding="utf-8").splitlines()
        if (r := json.loads(line))["pipeline"] == args.pipeline
    ]
    if not records:
        raise SystemExit(f"no dev records for {args.pipeline}")

    candidates = sorted({0.0, *(round(r["top_relevance"] + 1e-4, 4) for r in records)})
    rows = []
    for t in candidates:
        sim = simulate(records, t)
        rows.append(
            {
                "min_relevance": t,
                "reliability": round(sum(success(r) for r in sim) / len(sim), 4),
                "abstentions": sum(not r["presented"] for r in sim),
            }
        )
    best = max(rows, key=lambda x: (x["reliability"], -x["min_relevance"]))
    for row in rows:
        mark = "  <- chosen" if row is best else ""
        print(f"min_relevance={row['min_relevance']:.4f}  reliability={row['reliability']:.3f}  "
              f"abstentions={row['abstentions']}{mark}")  # fmt: skip
    out = {
        "min_relevance": best["min_relevance"],
        "tuned_on": "dev",
        "pipeline": args.pipeline,
        "dev_questions": len(records),
        "dev_reliability_at_threshold": best["reliability"],
        "dev_reliability_at_zero": rows[0]["reliability"],
        "sweep": rows,
    }
    (RESULTS / "tuned.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {RESULTS / 'tuned.json'}")


if __name__ == "__main__":
    main()
