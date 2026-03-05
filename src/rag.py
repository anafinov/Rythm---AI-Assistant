"""Simple TF-IDF vector search over knowledge base chunks.

Uses only numpy + stdlib — no ChromaDB or other heavy vector DBs needed.
Persists index to a JSON file for reuse between restarts.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import Counter

import numpy as np

logger = logging.getLogger(__name__)

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
INDEX_FILE = "kb_index.json"


class KnowledgeBase:
    def __init__(self, persist_dir: str = "./kb_data"):
        self.persist_dir = persist_dir
        self.chunks: list[str] = []
        self.sources: list[str] = []
        self.vocab: list[str] = []
        self.tfidf_matrix: np.ndarray | None = None
        os.makedirs(persist_dir, exist_ok=True)
        self._load_index()

    def search(self, query: str, n_results: int = 3) -> list[str]:
        if not self.chunks or self.tfidf_matrix is None:
            return []
        query_vec = self._text_to_tfidf(query)
        scores = self.tfidf_matrix @ query_vec
        top_idx = np.argsort(scores)[::-1][:n_results]
        return [self.chunks[i] for i in top_idx if scores[i] > 0]

    def index_directory(self, knowledge_dir: str) -> int:
        """Read all .md files, chunk, build TF-IDF index and persist."""
        self.chunks = []
        self.sources = []
        for filename in sorted(os.listdir(knowledge_dir)):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(knowledge_dir, filename)
            with open(filepath, encoding="utf-8") as f:
                text = f.read()
            source = filename.removesuffix(".md")
            for chunk in _split_text(text, CHUNK_SIZE, CHUNK_OVERLAP):
                self.chunks.append(chunk)
                self.sources.append(source)

        self._build_tfidf()
        self._save_index()
        logger.info("Indexed %d chunks from %s", len(self.chunks), knowledge_dir)
        return len(self.chunks)

    # ── TF-IDF ───────────────────────────────────────────────────────────

    def _build_tfidf(self):
        tokenized = [_tokenize(c) for c in self.chunks]
        vocab_set: set[str] = set()
        for tokens in tokenized:
            vocab_set.update(tokens)
        self.vocab = sorted(vocab_set)
        word2idx = {w: i for i, w in enumerate(self.vocab)}

        n_docs = len(tokenized)
        df = Counter()
        for tokens in tokenized:
            df.update(set(tokens))

        rows = []
        for tokens in tokenized:
            tf = Counter(tokens)
            vec = np.zeros(len(self.vocab))
            for word, count in tf.items():
                idx = word2idx[word]
                idf = math.log((n_docs + 1) / (df[word] + 1)) + 1
                vec[idx] = count * idf
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            rows.append(vec)
        self.tfidf_matrix = np.array(rows)

    def _text_to_tfidf(self, text: str) -> np.ndarray:
        tokens = _tokenize(text)
        word2idx = {w: i for i, w in enumerate(self.vocab)}
        vec = np.zeros(len(self.vocab))
        tf = Counter(tokens)
        for word, count in tf.items():
            if word in word2idx:
                vec[word2idx[word]] = count
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    # ── Persistence ──────────────────────────────────────────────────────

    def _save_index(self):
        path = os.path.join(self.persist_dir, INDEX_FILE)
        data = {
            "chunks": self.chunks,
            "sources": self.sources,
            "vocab": self.vocab,
            "matrix": self.tfidf_matrix.tolist() if self.tfidf_matrix is not None else [],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        logger.info("Index saved to %s", path)

    def _load_index(self):
        path = os.path.join(self.persist_dir, INDEX_FILE)
        if not os.path.exists(path):
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.chunks = data.get("chunks", [])
        self.sources = data.get("sources", [])
        self.vocab = data.get("vocab", [])
        matrix = data.get("matrix", [])
        if matrix:
            self.tfidf_matrix = np.array(matrix)
        logger.info("Loaded index with %d chunks", len(self.chunks))


# ── Helpers ──────────────────────────────────────────────────────────────

_WORD_RE = re.compile(r"[a-zа-яё0-9]+", re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in _WORD_RE.findall(text)]


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
