"""Okapi BM25 lexical retrieval over run-scoped chunk corpora.

True BM25 (Robertson–Walker) — not Postgres ts_rank_cd. Built in-memory from
persisted chunks; corpora are small per research run so no separate index store.
"""

from __future__ import annotations

import math
import re
import uuid
from collections import Counter

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9-]{1,}")

DEFAULT_K1 = 1.5
DEFAULT_B = 0.75


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


class BM25Index:
    """In-memory BM25 index keyed by chunk UUID."""

    def __init__(self, *, k1: float = DEFAULT_K1, b: float = DEFAULT_B) -> None:
        self.k1 = k1
        self.b = b
        self._tokens: dict[uuid.UUID, list[str]] = {}
        self._lengths: dict[uuid.UUID, int] = {}
        self._df: Counter[str] = Counter()
        self._n = 0
        self._avg_dl = 0.0

    def __len__(self) -> int:
        return self._n

    def add(self, doc_id: uuid.UUID, text: str) -> None:
        if doc_id in self._tokens:
            return
        tokens = tokenize(text)
        if not tokens:
            return
        self._tokens[doc_id] = tokens
        self._lengths[doc_id] = len(tokens)
        self._n += 1
        seen: set[str] = set()
        for token in tokens:
            if token not in seen:
                self._df[token] += 1
                seen.add(token)
        self._avg_dl = sum(self._lengths.values()) / max(self._n, 1)

    def search(self, query: str, *, limit: int) -> list[tuple[uuid.UUID, float]]:
        if self._n == 0:
            return []
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
        scored: list[tuple[float, uuid.UUID]] = []
        for doc_id, doc_tokens in self._tokens.items():
            score = self._score_document(query_tokens, doc_tokens, self._lengths[doc_id])
            if score > 0:
                scored.append((score, doc_id))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [(doc_id, score) for score, doc_id in scored[:limit]]

    def _score_document(
        self, query_tokens: list[str], doc_tokens: list[str], doc_len: int
    ) -> float:
        tf = Counter(doc_tokens)
        total = 0.0
        for token in query_tokens:
            if token not in self._df:
                continue
            freq = tf.get(token, 0)
            if freq == 0:
                continue
            idf = math.log(1 + (self._n - self._df[token] + 0.5) / (self._df[token] + 0.5))
            denom = freq + self.k1 * (1 - self.b + self.b * doc_len / max(self._avg_dl, 1))
            total += idf * (freq * (self.k1 + 1)) / denom
        return total


def build_bm25_index(
    chunks: list[tuple[uuid.UUID, str]],
) -> BM25Index:
    index = BM25Index()
    for chunk_id, text in chunks:
        index.add(chunk_id, text)
    return index
