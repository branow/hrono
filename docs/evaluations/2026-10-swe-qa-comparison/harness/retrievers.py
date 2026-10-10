# ruff: noqa: E501, E741, B904, B905, B007, B023
"""The retrieval systems under test. Each returns ranked (label, text) chunks.

All of them index exactly the files hrono ingested (`common.corpus_files`),
and every dense system uses the same embedding model hrono uses.
"""

from __future__ import annotations

import json
import pickle
import re
import time

import common
import httpx
import numpy as np

INDEX = common.ROOT / "cache" / "index"
CHUNK_CHARS = 800  # hrono's passage target is about 800 B


def chunk_files(repo: str) -> list[dict]:
    """Line-aligned windows of at most CHUNK_CHARS per file, no overlap."""
    out = []
    for path, text in common.corpus_files(repo):
        lines = text.splitlines(keepends=True)
        buf, start = [], 1
        size = 0
        for i, line in enumerate(lines, 1):
            if buf and size + len(line) > CHUNK_CHARS:
                out.append(_chunk(path, start, i - 1, "".join(buf)))
                buf, size, start = [], 0, i
            buf.append(line)
            size += len(line)
        if buf and "".join(buf).strip():
            out.append(_chunk(path, start, len(lines), "".join(buf)))
    return out


def _chunk(path, a, b, text):
    return {"label": f"{path}:L{a}-{b}", "path": path, "text": text}


def _cached(name: str, build):
    path = INDEX / f"{name}.pkl"
    if path.exists():
        return pickle.loads(path.read_bytes())
    value = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pickle.dumps(value))
    return value


class ClosedBook:
    name = "closed-book"

    def retrieve(self, repo, question):
        return []


_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+")


def _tokens(text: str) -> list[str]:
    """Identifiers split on snake_case and camelCase, lowercased."""
    out = []
    for tok in _TOKEN.findall(text):
        out.append(tok.lower())
        parts = re.split(r"_|(?<=[a-z])(?=[A-Z])", tok)
        if len(parts) > 1:
            out.extend(p.lower() for p in parts if p)
    return out


class BM25:
    name = "bm25"

    def __init__(self):
        self._idx = {}

    def _index(self, repo):
        if repo not in self._idx:
            from rank_bm25 import BM25Okapi

            chunks = _cached(f"chunks-{repo}", lambda: chunk_files(repo))
            bm = BM25Okapi(
                [_tokens(c["path"] + " " + c["text"]) for c in chunks]
            )
            self._idx[repo] = (chunks, bm)
        return self._idx[repo]

    def retrieve(self, repo, question):
        chunks, bm = self._index(repo)
        scores = bm.get_scores(_tokens(question))
        order = np.argsort(-scores)[:40]
        return [(chunks[i]["label"], chunks[i]["text"]) for i in order]


class Dense:
    name = "dense"

    def __init__(self):
        self._idx = {}

    def _index(self, repo):
        if repo not in self._idx:
            chunks = _cached(f"chunks-{repo}", lambda: chunk_files(repo))

            def build():
                texts = [c["path"] + "\n" + c["text"] for c in chunks]
                return common.encode(
                    texts, batch_size=64, normalize_embeddings=True
                )

            emb = _cached(f"dense-{repo}", build)
            self._idx[repo] = (chunks, np.asarray(emb))
        return self._idx[repo]

    def retrieve(self, repo, question):
        chunks, emb = self._index(repo)
        q = common.encode([question], normalize_embeddings=True)[0]
        order = np.argsort(-(emb @ q))[:40]
        return [(chunks[i]["label"], chunks[i]["text"]) for i in order]


class Hrono:
    """hrono's recall endpoint, as an agent calls it."""

    name = "hrono"

    def __init__(self):
        self._token = (common.ROOT / "token").read_text().strip()

    def hits(self, repo, question):
        for _ in range(60):
            r = httpx.post(
                f"http://127.0.0.1:8788/trees/{repo}/recall",
                json={"question": question, "limit": 10},
                headers={"Authorization": f"Bearer {self._token}"},
                timeout=120,
            )
            if r.status_code != 503:  # 503: the encoder is still loading
                break
            time.sleep(5)
        r.raise_for_status()
        return r.json()["hits"]

    def retrieve(self, repo, question):
        return [(h["header"], h["body"]) for h in self.hits(repo, question)]


class Raptor:
    """RAPTOR's collapsed-tree retrieval over a tree built by build_raptor.py."""

    name = "raptor"

    def __init__(self):
        self._idx = {}

    def _index(self, repo):
        if repo not in self._idx:
            nodes = json.loads((INDEX / f"raptor-{repo}.json").read_text())
            emb = np.load(INDEX / f"raptor-{repo}.npy")
            self._idx[repo] = (nodes, emb)
        return self._idx[repo]

    def retrieve(self, repo, question):
        nodes, emb = self._index(repo)
        q = common.encode([question], normalize_embeddings=True)[0]
        order = np.argsort(-(emb @ q))[:40]
        return [(nodes[i]["label"], nodes[i]["text"]) for i in order]


class LightRAG:
    """LightRAG's hybrid (entity + relation + chunk) context, retrieval only."""

    name = "lightrag"

    def retrieve(self, repo, question):
        import lightrag_adapter

        ctx = lightrag_adapter.context(repo, question)
        return [("LightRAG context", ctx)] if ctx else []


SYSTEMS = {
    s.name: s for s in (ClosedBook, BM25, Dense, Hrono, Raptor, LightRAG)
}


def paths_in(chunks) -> set[str]:
    """Repository file paths named by chunk labels or texts."""
    out = set()
    for label, text in chunks:
        out.add(label.split(":L")[0].split(" ")[0])
        out.update(re.findall(r"[\w./-]+\.(?:py|rst|md|txt|toml|cfg)", label))
    return out
