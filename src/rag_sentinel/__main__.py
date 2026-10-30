"""Command line: python -m rag_sentinel {ingest,stats,ask} ...

Uses the same settings as the API (.env, SENTINEL_* variables).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from rag_sentinel.config import Settings
from rag_sentinel.kb import KnowledgeBase


def main() -> None:
    ap = argparse.ArgumentParser(prog="rag_sentinel")
    ap.add_argument("--data-dir", help="override SENTINEL_DATA_DIR")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ing = sub.add_parser("ingest", help="ingest a file or every supported file in a folder (recursive)")
    ing.add_argument("path", type=Path)
    sub.add_parser("stats", help="knowledge base statistics")
    ask = sub.add_parser("ask", help="ask a question")
    ask.add_argument("question")
    ask.add_argument("--pipeline", default="B4")
    ask.add_argument("--as-of", help="YYYY-MM-DD")
    args = ap.parse_args()

    settings = Settings(**({"data_dir": args.data_dir} if args.data_dir else {}))
    kb = KnowledgeBase.from_settings(settings)

    if args.cmd == "ingest":
        if args.path.is_dir():
            results = kb.ingest_directory(args.path)
        else:
            results = [kb.ingest_path(args.path)]
        for r in results:
            d = r.document
            print(f"{r.status:12} {d.filename}  v{d.version_label or '-'}  chunks={r.chunks} claims={r.claims}")
            for w in r.warnings:
                print(f"{'':12} warning: {w}")
    elif args.cmd == "stats":
        print(json.dumps(kb.stats(), indent=2, default=str))
    else:
        from datetime import date

        from rag_sentinel.agent.graph import SentinelAgent

        agent = SentinelAgent(kb, args.pipeline)
        res = agent.ask(args.question, as_of=date.fromisoformat(args.as_of) if args.as_of else None)
        print(f"[{res['status']}] {res['answer']}")
        for r in res["reasons"]:
            print(f"  reason: {r}")
        for c in res["citations"]:
            print(f"  [{c['label']}] {c['filename']} ({c['standing_status']})")


if __name__ == "__main__":
    main()
