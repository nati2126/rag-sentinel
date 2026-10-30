"""Summarize repeated runs (different sampling seeds) of one split as Markdown.

    python -m evaluation.variance --split test_v2 --tags s1,s2,s3

Each tag is a run made with `evaluation.run ... --llm-temperature T --llm-seed N --tag <tag>`. Reports mean,
standard deviation and range per pipeline, with counts, so run-to-run variability is visible next to the
primary (temperature 0) result.
"""

from __future__ import annotations

import argparse
import json
import statistics

from evaluation.run import RESULTS

METRICS = [
    ("reliability", "Reliability"),
    ("stale_answer_rate", "Stale rate"),
    ("unsupported_answer_rate", "Unsupported rate"),
    ("over_abstention_rate", "Over-abstention"),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test_v2")
    ap.add_argument("--tags", required=True)
    args = ap.parse_args()
    tags = [t for t in args.tags.split(",") if t]
    runs = {t: json.loads((RESULTS / f"{args.split}__{t}_summary.json").read_text(encoding="utf-8")) for t in tags}
    env = {t: (r["environment"]["llm_temperature"], r["environment"]["llm_seed"]) for t, r in runs.items()}
    print(
        f"Repeated runs on **{args.split}**: "
        + ", ".join(f"{t} (temperature {a}, seed {b})" for t, (a, b) in env.items())
    )
    print()
    pipelines = [p for p in next(iter(runs.values()))["pipelines"] if all(p in r["pipelines"] for r in runs.values())]
    header = ["Pipeline"] + [label for _, label in METRICS] + ["Reliable per run"]
    print("| " + " | ".join(header) + " |")
    print("|" + "---|" * len(header))
    for p in pipelines:
        cells = [p]
        for key, _ in METRICS:
            xs = [r["pipelines"][p]["metrics"][key] for r in runs.values()]
            xs = [x for x in xs if x is not None]
            if not xs:
                cells.append("n/a")
                continue
            sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
            cells.append(f"{statistics.mean(xs):.1%} ± {sd:.1%} ({min(xs):.1%} to {max(xs):.1%})")
        counts = [r["pipelines"][p]["metrics"]["counts"] for r in runs.values()]
        cells.append(", ".join(f"{c['reliable']}/{c['questions']}" for c in counts))
        print("| " + " | ".join(cells) + " |")


if __name__ == "__main__":
    main()
