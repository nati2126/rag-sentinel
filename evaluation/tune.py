"""Tune the relevance gate (min_relevance) on development splits, offline.

Uses B4 records produced with min_relevance=0: raising the threshold only turns answers whose best evidence
relevance is below it into abstentions, so every candidate can be scored without re-running the LLM.
Candidates are midpoints between observed relevances. The threshold with the highest pooled reliability
wins; ties go to the lowest threshold (fewest refusals). The held-out splits (test_v2, public_v1) are never read.

    python -m evaluation.run --split dev --min-relevance 0 --force
    python -m evaluation.run --split test_v1 --min-relevance 0 --force
    python -m evaluation.tune --splits dev,test_v1
"""

from __future__ import annotations

import argparse
import json

from evaluation.run import HELD_OUT, RESULTS, success


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
    ap.add_argument("--splits", default="dev,test_v1")
    args = ap.parse_args()

    splits = [x for x in args.splits.split(",") if x]
    if held := HELD_OUT.intersection(splits):
        raise SystemExit(f"{', '.join(sorted(held))}: held-out split(s); they must not be used for tuning")
    records: list[dict] = []
    for split in splits:
        summary = json.loads((RESULTS / f"{split}_summary.json").read_text(encoding="utf-8"))
        used = summary["environment"]["min_relevance"]
        if used != 0:
            raise SystemExit(f"{split} records were produced with min_relevance={used}; re-run with --min-relevance 0")
        recs = [
            r
            for line in (RESULTS / f"{split}_records.jsonl").read_text(encoding="utf-8").splitlines()
            if (r := json.loads(line))["pipeline"] == args.pipeline
        ]
        if not recs:
            raise SystemExit(f"no {split} records for {args.pipeline}")
        records += recs

    rels = sorted({r["top_relevance"] for r in records})
    candidates = [0.0] + [round((x + y) / 2, 4) for x, y in zip(rels, rels[1:], strict=False)]
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
        "tuned_on": splits,
        "pipeline": args.pipeline,
        "questions": len(records),
        "reliability_at_threshold": best["reliability"],
        "reliability_at_zero": rows[0]["reliability"],
        "sweep": rows,
    }
    (RESULTS / "tuned.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"wrote {RESULTS / 'tuned.json'}")


if __name__ == "__main__":
    main()
