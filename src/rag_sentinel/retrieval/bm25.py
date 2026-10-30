"""BM25 keyword index, rebuilt in memory from SQLite (fine for thousands of chunks).

Own implementation (~30 lines) instead of rank_bm25: its Okapi variant gives *negative* IDF to terms that
occur in more than half of the documents, which is common in small, focused corpora (every leave document
contains "leave") and silently drops relevant results. We use the Lucene IDF, which is always positive:
    idf = ln(1 + (N - df + 0.5) / (df + 0.5))
"""

from __future__ import annotations

import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have how i in is it its many may much of on or our "
    "should that the their this to was we what when where which who will with you your".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


class BM25Index:
    def __init__(self, items: list[tuple[str, str]], k1: float = 1.5, b: float = 0.75):
        self.ids = [i for i, _ in items]
        self.k1, self.b = k1, b
        self.tfs = [Counter(tokenize(t)) for _, t in items]
        self.lengths = [sum(tf.values()) for tf in self.tfs]
        self.avgdl = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(self.tfs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, query_tokens: list[str], i: int) -> float:
        tf, dl = self.tfs[i], self.lengths[i]
        s = 0.0
        for t in query_tokens:
            f = tf.get(t, 0)
            if f:
                s += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
        return s

    def search(self, query: str, k: int) -> list[tuple[str, float]]:
        q = tokenize(query)
        if not q or not self.ids:
            return []
        scored = [(self.ids[i], self.score(q, i)) for i in range(len(self.ids))]
        scored = [x for x in scored if x[1] > 0]
        scored.sort(key=lambda x: (-x[1], x[0]))
        return scored[:k]
