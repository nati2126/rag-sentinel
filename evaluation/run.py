"""Run the VersionConflict benchmark.

    python -m evaluation.run --split dev --min-relevance 0          # development splits: dev, test_v1
    python -m evaluation.tune --splits dev,test_v1                  # pick the relevance gate on development data
    python -m evaluation.run --split test_v2 --ablations            # held-out split, run once
    python -m evaluation.run --split test_v2 --pipelines B0,B3,B4 --llm-temperature 0.3 --llm-seed 1 --tag s1

Each split gets its own knowledge base in data/bench_<split>. Per-question records go to
results/<split>[__<tag>]_records.jsonl (a finished pipeline is skipped on re-run unless --force), and metrics
to results/<split>[__<tag>]_summary.json. Nothing in the summary is hand-edited. Tagged runs reuse the split's
knowledge base, so they vary only query-time sampling (generation and answer check); ingestion, claims and
cached judge verdicts are shared.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import time
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path

from evaluation import metrics as M
from rag_sentinel.agent.graph import SentinelAgent
from rag_sentinel.config import Settings
from rag_sentinel.conflicts.detect import ConflictDetector, make_pair_judge, naive_value_conflicts
from rag_sentinel.kb import KnowledgeBase
from rag_sentinel.log import setup_logging
from rag_sentinel.pipelines import ABLATIONS, PIPELINES

ROOT = Path(__file__).resolve().parent.parent
BENCH = ROOT / "benchmark"
RESULTS = ROOT / "results"
AS_OF = date(2026, 10, 1)


def load_questions(split: str) -> list[dict]:
    with (BENCH / "questions" / f"{split}.jsonl").open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


SPLITS = ["dev", "test_v1", "test_v2", "public_v1"]
HELD_OUT = {"test_v2", "public_v1"}  # never used for tuning


def bench_settings(split: str, min_relevance: float | None, temperature: float | None = None,
                   seed: int | None = None) -> Settings:  # fmt: skip
    base = Settings()
    update = {"data_dir": ROOT / "data" / f"bench_{split}", "as_of": AS_OF}
    if temperature is not None:
        update["llm_temperature"] = temperature
    if seed is not None:
        update["llm_seed"] = seed
    tuned = RESULTS / "tuned.json"
    if min_relevance is not None:
        update["min_relevance"] = min_relevance
    elif tuned.exists():
        update["min_relevance"] = json.loads(tuned.read_text())["min_relevance"]
    return base.model_copy(update=update)


def build_kb(split: str, settings: Settings, rebuild: bool) -> tuple[KnowledgeBase, dict]:
    marker = settings.data_dir / "ingest_stats.json"
    if rebuild and settings.data_dir.exists():
        shutil.rmtree(settings.data_dir)
    kb = KnowledgeBase.from_settings(settings)
    if marker.exists():
        return kb, json.loads(marker.read_text())
    t0 = time.perf_counter()
    results = kb.ingest_directory(BENCH / "corpus" / split)
    stats = {
        "documents": len(results),
        "chunks": sum(r.chunks for r in results),
        "claims_accepted": sum(r.claims for r in results),
        "claims_rejected": sum(r.claims_rejected for r in results),
        "ingest_seconds": round(time.perf_counter() - t0, 1),
        "warnings": {r.document.filename: r.warnings for r in results if r.warnings},
    }
    marker.write_text(json.dumps(stats, indent=2))
    return kb, stats


def eval_conflicts(kb: KnowledgeBase, split: str) -> dict:
    gold = json.loads((BENCH / "conflicts" / f"{split}.json").read_text(encoding="utf-8"))
    docs = kb.documents_map()
    names = {d.id: d.filename for d in docs.values()}
    claims = kb.claims()

    def as_found(findings) -> list[dict]:
        return [{"a": names[f.claim_a.doc_id], "a_value": f.claim_a.value, "b": names[f.claim_b.doc_id],
                 "b_value": f.claim_b.value, "kind": f.kind, "explanation": f.explanation} for f in findings]  # fmt: skip

    naive = [{"a": names[a.doc_id], "a_value": a.value, "b": names[b.doc_id], "b_value": b.value, "kind": "contradiction"}
             for a, b in naive_value_conflicts(claims)]  # fmt: skip
    lineage = kb.lineage()
    s = kb.settings
    rules = ConflictDetector(docs, claims, lineage, AS_OF, s.ranking, s.authority_margin, None).detect()
    judge = make_pair_judge(kb.llm, docs, kb.db.cache_get, kb.db.cache_set)
    full = ConflictDetector(docs, claims, lineage, AS_OF, s.ranking, s.authority_margin, judge).detect()
    return {
        "gold_pairs": len(gold),
        "gold_actionable": sum(1 for g in gold if g["kind"] in ("contradiction", "outdated")),
        "naive_value_difference": M.conflict_scores(naive, gold),
        "rules_only": M.conflict_scores(as_found(rules), gold),
        "rules_plus_llm_judge": M.conflict_scores(as_found(full), gold),
        "detected_kinds": {k: sum(1 for f in full if f.kind == k) for k in sorted({f.kind for f in full})},
    }


def record_for(q: dict, res: dict) -> dict:
    ev = res["evidence"]
    ranked = [(e["filename"], e["text"]) for e in ev]
    presented = res["presented_as_reliable"]
    shown = res["answer"] if presented else ""
    draft = res.get("draft_answer") or ""
    cited = res["citations"]
    rel_cites = [c for c in cited if M.passage_relevant(q, c["filename"], c["text"])]
    gen = res.get("generation") or {}
    grounded = None
    if draft and not gen.get("cannot_answer"):
        grounded = bool(cited) and not res.get("unsupported_values")
    return {
        "id": q["id"], "category": q["category"], "group": q["group"], "expected_decision": q["expected_decision"],
        "status": res["status"], "presented": presented, "answer": res["answer"], "draft_answer": draft,
        "correct": M.is_correct(q, shown) if presented else False,
        "draft_correct": M.is_correct(q, draft),
        "stale": M.is_stale(q, shown) if presented else False,
        "stale_raw": M.is_stale(q, draft),
        "recall5": M.recall_at_k(q, ranked), "mrr5": M.mrr_at_k(q, ranked),
        "citations": [c["filename"] for c in cited], "relevant_citations": len(rel_cites),
        "grounded": grounded, "rules_fired": res.get("rules_fired", []), "reasons": res.get("reasons", []),
        "top_relevance": max((e["relevance"] for e in ev), default=0.0),
        "evidence": [[e["label"], e["filename"], e["standing_status"], e["relevance"]] for e in ev],
        "mode": res["analysis"]["mode"], "as_of": res["analysis"]["as_of"], "latency_ms": res["latency_ms"],
    }  # fmt: skip


def success(r: dict) -> int:
    """Per-question reliability: a correct answer presented as reliable, or abstention when gold says abstain."""
    if r["expected_decision"] == "VERIFIED":
        return int(r["presented"] and r["correct"])
    return int(not r["presented"])


def summarize(records: list[dict]) -> dict:
    n = len(records)
    verified_gold = [r for r in records if r["expected_decision"] == "VERIFIED"]
    abstain_gold = [r for r in records if r["expected_decision"] != "VERIFIED"]
    stale_q = [r for r in verified_gold if r.get("has_stale")]
    abstained = [r for r in records if not r["presented"]]
    cited_total = sum(len(r["citations"]) for r in verified_gold if r["presented"])
    cited_rel = sum(r["relevant_citations"] for r in verified_gold if r["presented"])
    grounded = [r["grounded"] for r in records if r["grounded"] is not None]
    lat = [r["latency_ms"] for r in records]
    by_cat: dict[str, list[int]] = defaultdict(list)
    for r in records:
        by_cat[r["category"]].append(success(r))

    def decision(r: dict) -> str:
        return "VERIFIED" if r["status"] == "ANSWERED" else r["status"]

    return {
        "n": n,
        "recall_at_5": M.mean([r["recall5"] for r in records]),
        "mrr_at_5": M.mean([r["mrr5"] for r in records]),
        "citation_precision": M.safe_div(cited_rel, cited_total),
        "faithfulness_numeric": M.safe_div(sum(grounded), len(grounded)),
        "answer_accuracy": M.safe_div(sum(r["correct"] for r in verified_gold), len(verified_gold)),
        "draft_answer_accuracy": M.safe_div(sum(r["draft_correct"] for r in verified_gold), len(verified_gold)),
        "stale_answer_rate": M.safe_div(sum(r["stale"] for r in stale_q), len(stale_q)),
        "stale_draft_rate": M.safe_div(sum(r["stale_raw"] for r in stale_q), len(stale_q)),
        "unsupported_answer_rate": M.safe_div(sum(r["presented"] for r in abstain_gold), len(abstain_gold)),
        "abstention_rate": M.safe_div(len(abstained), n),
        "abstention_precision": M.safe_div(
            sum(r["expected_decision"] != "VERIFIED" for r in abstained), len(abstained)
        ),
        "abstention_recall": M.safe_div(sum(not r["presented"] for r in abstain_gold), len(abstain_gold)),
        "over_abstention_rate": M.safe_div(sum(not r["presented"] for r in verified_gold), len(verified_gold)),
        "decision_accuracy": M.safe_div(sum(decision(r) == r["expected_decision"] for r in records), n),
        "reliability": M.safe_div(sum(success(r) for r in records), n),
        "reliability_ci95": M.bootstrap_ci([success(r) for r in records]),
        "reliability_ci95_clustered": M.cluster_bootstrap_ci(
            [success(r) for r in records], [r["group"] for r in records]
        ),
        "latency_ms": {"mean": M.mean(lat), "p50": M.percentile(lat, 50), "p95": M.percentile(lat, 95)},
        "reliability_by_category": {c: M.safe_div(sum(v), len(v)) for c, v in sorted(by_cat.items())},
        "counts": {
            "questions": n,
            "reliable": sum(success(r) for r in records),
            "verified_gold": len(verified_gold),
            "correct_presented": sum(r["correct"] for r in verified_gold),
            "over_abstained": sum(not r["presented"] for r in verified_gold),
            "abstain_gold": len(abstain_gold),
            "unsupported_presented": sum(r["presented"] for r in abstain_gold),
            "stale_questions": len(stale_q),
            "stale_presented": sum(r["stale"] for r in stale_q),
            "groups": len({r["group"] for r in records}),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=SPLITS, required=True)
    ap.add_argument("--pipelines", default="B0,B1,B2,B3,B4")
    ap.add_argument("--ablations", action="store_true")
    ap.add_argument("--rebuild", action="store_true", help="re-ingest the corpus")
    ap.add_argument("--force", action="store_true", help="re-run pipelines that already have records")
    ap.add_argument("--min-relevance", type=float, default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--tag", default="", help="suffix for result files (repeated runs)")
    ap.add_argument("--llm-temperature", type=float, default=None)
    ap.add_argument("--llm-seed", type=int, default=None)
    args = ap.parse_args()
    setup_logging("WARNING")

    RESULTS.mkdir(exist_ok=True)
    settings = bench_settings(args.split, args.min_relevance, args.llm_temperature, args.llm_seed)
    stem = args.split + (f"__{args.tag}" if args.tag else "")
    kb, ingest = build_kb(args.split, settings, args.rebuild)
    questions = load_questions(args.split)[: args.limit]
    for q in questions:
        q["has_stale"] = bool(q["stale"])

    names = [p for p in args.pipelines.split(",") if p] + ([a.name for a in ABLATIONS] if args.ablations else [])
    rec_path = RESULTS / f"{stem}_records.jsonl"
    existing: dict[str, list[dict]] = defaultdict(list)
    if rec_path.exists():
        for line in rec_path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            existing[r["pipeline"]].append(r)
    # --force re-runs the requested pipelines; records of other pipelines are kept
    all_records = {k: v for k, v in existing.items() if k not in names or (not args.force and len(v) >= len(questions))}

    for name in names:
        if name in all_records:
            print(f"[{name}] cached ({len(all_records[name])} records)")
            continue
        agent = SentinelAgent(kb, PIPELINES[name])
        recs = []
        t0 = time.perf_counter()
        for i, q in enumerate(questions, 1):
            res = agent.ask(q["question"])
            r = record_for(q, res) | {"pipeline": name, "has_stale": q["has_stale"]}
            recs.append(r)
            mark = "ok " if success(r) else "XX "
            print(f"[{name}] {i:3}/{len(questions)} {mark}{q['id']} {r['status']:<22} {r['latency_ms']:>7.0f}ms  "
                  f"{(r['answer'] or '')[:70]!r}", flush=True)  # fmt: skip
        all_records[name] = recs
        print(f"[{name}] done in {time.perf_counter() - t0:.0f}s")
        with rec_path.open("w", encoding="utf-8") as fh:  # rewrite: keeps one run per pipeline
            for recs_ in all_records.values():
                for r in recs_:
                    fh.write(json.dumps(r) + "\n")

    order = [p for p in PIPELINES if p in all_records]
    summary = {
        "split": args.split,
        "tag": args.tag,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "as_of": AS_OF.isoformat(),
        "questions": len(questions),
        "environment": {
            "llm": settings.llm_model,
            "embedder": settings.embed_model,
            "reranker": settings.reranker_model,
            "min_relevance": settings.min_relevance,
            "llm_temperature": settings.llm_temperature,
            "llm_seed": settings.llm_seed,
            "authority_margin": settings.authority_margin,
            "predicate_similarity": settings.predicate_similarity,
            "python": platform.python_version(),
            "platform": platform.platform(),
        },  # fmt: skip
        "ingestion": ingest,
        "pipelines": {p: PIPELINES[p].to_dict() | {"metrics": summarize(all_records[p])} for p in order},
        "conflict_detection": eval_conflicts(kb, args.split),
    }
    if "B4" in all_records:
        b4 = [success(r) for r in all_records["B4"]]
        summary["comparisons_vs_B4"] = {
            p: {"reliability_diff": M.paired_bootstrap_diff([success(r) for r in all_records[p]], b4),
                "reliability_diff_clustered": M.paired_cluster_bootstrap_diff(
                    [success(r) for r in all_records[p]], b4, [r["group"] for r in all_records["B4"]]),
                "mcnemar": M.mcnemar_exact([success(r) for r in all_records[p]], b4)}
            for p in order if p != "B4"
        }  # fmt: skip
    out = RESULTS / f"{stem}_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print(f"wrote {out}")
    kb.vectors.close()


if __name__ == "__main__":
    main()
