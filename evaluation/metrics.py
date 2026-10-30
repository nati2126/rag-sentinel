"""Metric definitions for the VersionConflict benchmark (deterministic; no LLM judge).

Answer matching: citation labels like [E1] are removed, then an expected/stale alternative matches if it is a
case-insensitive substring of the answer, or if all its numbers appear in the answer (number words converted)
and its unit words appear too.
"""

from __future__ import annotations

import math
import random
import re
from collections.abc import Callable, Sequence

from rag_sentinel.claims.normalize import normalize_text, normalize_value, numbers_in, values_equivalent

_LABEL = re.compile(r"\[E\d+\]")
_FILLER = {"per", "the", "and", "for", "day"}


def clean(answer: str) -> str:
    return re.sub(r"\s+", " ", _LABEL.sub(" ", answer or "")).lower().strip()


def matches(alt: str, answer: str) -> bool:
    a = clean(answer)
    alt_l = alt.lower().strip()
    if alt_l in a:
        return True
    nums = numbers_in(alt_l)
    if not nums or not nums <= numbers_in(a):
        return False
    words = [w for w in re.findall(r"[a-z]{3,}", alt_l) if w not in _FILLER]
    return all(w.rstrip("s") in a for w in words)


def is_correct(q: dict, answer: str) -> bool:
    return bool(q["expected"]) and all(any(matches(alt, answer) for alt in group) for group in q["expected"])


def is_stale(q: dict, answer: str) -> bool:
    return bool(q["stale"]) and any(matches(s, answer) for s in q["stale"]) and not is_correct(q, answer)


def passage_relevant(q: dict, filename: str, text: str) -> bool:
    flat = " ".join(text.split()).lower()
    return any(g["file"] == filename and " ".join(g["contains"].split()).lower() in flat for g in q["gold_evidence"])


def recall_at_k(q: dict, ranked: list[tuple[str, str]], k: int = 5) -> float | None:
    """Fraction of gold evidence items found in the top-k passages (filename, text)."""
    if not q["gold_evidence"]:
        return None
    top = ranked[:k]
    found = 0
    for g in q["gold_evidence"]:
        needle = " ".join(g["contains"].split()).lower()
        if any(f == g["file"] and needle in " ".join(t.split()).lower() for f, t in top):
            found += 1
    return found / len(q["gold_evidence"])


def mrr_at_k(q: dict, ranked: list[tuple[str, str]], k: int = 5) -> float | None:
    if not q["gold_evidence"]:
        return None
    for i, (f, t) in enumerate(ranked[:k], 1):
        if passage_relevant(q, f, t):
            return 1.0 / i
    return 0.0


def mean(xs: Sequence[float | None]) -> float | None:
    vals = [x for x in xs if x is not None]
    return round(sum(vals) / len(vals), 4) if vals else None


def percentile(xs: Sequence[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    idx = min(len(s) - 1, max(0, math.ceil(p / 100 * len(s)) - 1))
    return round(s[idx], 1)


def safe_div(a: float, b: float) -> float | None:
    return round(a / b, 4) if b else None


def prf(tp: int, fp: int, fn: int) -> dict:
    p = safe_div(tp, tp + fp)
    r = safe_div(tp, tp + fn)
    f1 = round(2 * p * r / (p + r), 4) if p and r else (0.0 if p is not None and r is not None else None)
    return {"precision": p, "recall": r, "f1": f1, "tp": tp, "fp": fp, "fn": fn}


def bootstrap_ci(
    values: Sequence[float], stat: Callable[[Sequence[float]], float] = lambda v: sum(v) / len(v),
    n: int = 2000, seed: int = 13,
) -> tuple[float, float] | None:  # fmt: skip
    if not values:
        return None
    rng = random.Random(seed)
    k = len(values)
    samples = sorted(stat([values[rng.randrange(k)] for _ in range(k)]) for _ in range(n))
    return round(samples[int(0.025 * n)], 4), round(samples[int(0.975 * n) - 1], 4)


def paired_bootstrap_diff(a: Sequence[float], b: Sequence[float], n: int = 2000, seed: int = 13) -> dict | None:
    """95% CI for mean(b) - mean(a) over paired items."""
    if not a or len(a) != len(b):
        return None
    rng = random.Random(seed)
    k = len(a)
    diffs = []
    for _ in range(n):
        idx = [rng.randrange(k) for _ in range(k)]
        diffs.append(sum(b[i] - a[i] for i in idx) / k)
    diffs.sort()
    return {
        "diff": round((sum(b) - sum(a)) / k, 4),
        "ci95": [round(diffs[int(0.025 * n)], 4), round(diffs[int(0.975 * n) - 1], 4)],
    }


def mcnemar_exact(a: Sequence[int], b: Sequence[int]) -> dict:
    """Exact (binomial) McNemar test on paired binary outcomes."""
    b01 = sum(1 for x, y in zip(a, b, strict=True) if x == 0 and y == 1)
    b10 = sum(1 for x, y in zip(a, b, strict=True) if x == 1 and y == 0)
    n = b01 + b10
    if n == 0:
        return {"b01": 0, "b10": 0, "p_value": 1.0}
    k = min(b01, b10)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return {"b01": b01, "b10": b10, "p_value": round(min(1.0, 2 * p), 4)}


# ------------------------------------------------------------------ conflict matching


def value_match(system_value: str, gold_value: str) -> bool:
    eq = values_equivalent(normalize_value(system_value), normalize_value(gold_value))
    if eq is True:
        return True
    s, g = normalize_text(system_value), normalize_text(gold_value)
    return bool(g) and (g in s or s in g)


def pair_matches(found: dict, gold: dict) -> bool:
    """found: {'a': file, 'a_value': v, 'b': file, 'b_value': v} (order-free)."""
    if {found["a"], found["b"]} != {gold["a"], gold["b"]} or found["a"] == found["b"]:
        return False
    if found["a"] == gold["a"]:
        return value_match(found["a_value"], gold["a_value"]) and value_match(found["b_value"], gold["b_value"])
    return value_match(found["a_value"], gold["b_value"]) and value_match(found["b_value"], gold["a_value"])


def conflict_scores(
    found: list[dict], gold: list[dict], positive: tuple[str, ...] = ("contradiction", "outdated")
) -> dict:
    gold_pos = [g for g in gold if g["kind"] in positive]
    sys_pos = [f for f in found if f["kind"] in positive]
    # dedupe system findings that describe the same document pair and values
    uniq: list[dict] = []
    for f in sys_pos:
        if not any(pair_matches(f, {**u, "kind": u["kind"]}) for u in uniq):
            uniq.append(f)
    tp_gold = {i for i, g in enumerate(gold_pos) if any(pair_matches(f, g) for f in uniq)}
    fp = sum(1 for f in uniq if not any(pair_matches(f, g) for g in gold_pos))
    out = prf(len(tp_gold), fp, len(gold_pos) - len(tp_gold))
    kind_hits = kind_total = 0
    for g in gold:
        cands = [f for f in found if pair_matches(f, g)]
        if cands:
            kind_total += 1
            kind_hits += any(f["kind"] == g["kind"] for f in cands)
    out["kind_accuracy_on_matched_gold_pairs"] = safe_div(kind_hits, kind_total)
    out["gold_pairs_matched_any_kind"] = f"{kind_total}/{len(gold)}"
    out["false_positive_examples"] = [f for f in uniq if not any(pair_matches(f, g) for g in gold_pos)][:15]
    out["missed"] = [g for i, g in enumerate(gold_pos) if i not in tp_gold]
    return out
