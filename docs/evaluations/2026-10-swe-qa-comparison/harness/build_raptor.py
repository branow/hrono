# ruff: noqa: E501, E741, B904, B905, B007, B023
"""Build a RAPTOR tree per repository with the official RAPTOR code.

RAPTOR (Sarthi et al., ICLR 2024; github.com/parthsarthi03/raptor @ 7da1d48)
is used unmodified: its ClusterTreeBuilder (UMAP + GMM soft clustering,
reduction_dimension 10, threshold 0.1, max 3500 tokens per cluster, up to 5
layers) and its summarization prompt. Three things are swapped in:

- leaves are the shared line-aligned chunks (retrievers.chunk_files) instead
  of RAPTOR's sentence splitter, which splits on '.' and so shreds code;
- the embedding model is all-MiniLM-L6-v2, the one hrono uses;
- the summarizer is Claude Sonnet via the CLI, the model hrono writes its
  briefs with, asked for RAPTOR's summary in at most 120 words.

Usage: uv run python build_raptor.py flask [requests ...]
"""

from __future__ import annotations

import json
import sys
import threading
import time

import numpy as np

sys.path.insert(0, str(__import__("common").ROOT / "raptor"))

import common  # noqa: E402
import retrievers  # noqa: E402
from raptor import (  # noqa: E402
    BaseEmbeddingModel,
    BaseSummarizationModel,
    ClusterTreeBuilder,
    ClusterTreeConfig,
)

GATE = threading.Semaphore(8)


class MiniLM(BaseEmbeddingModel):
    def __init__(self):
        self.memo = {}

    def create_embedding(self, text):
        if text not in self.memo:
            self.memo[text] = common.encode([text], normalize_embeddings=True)[
                0
            ]
        return self.memo[text]


class Sonnet(BaseSummarizationModel):
    def summarize(self, context, max_tokens=150):
        with GATE:
            return common.llm(
                "Write a summary of the following, including as many key "
                f"details as possible (at most 120 words): {context}:",
                system="You are a helpful assistant.",
                model="sonnet",
                role="raptor-summary",
            )


def build(repo: str) -> None:
    t0 = time.time()
    chunks = retrievers._cached(
        f"chunks-{repo}", lambda: retrievers.chunk_files(repo)
    )
    texts = [c["path"] + "\n" + c["text"] for c in chunks]
    emb = MiniLM()
    vecs = common.encode(texts, batch_size=64, normalize_embeddings=True)
    emb.memo.update(zip(texts, vecs))
    config = ClusterTreeConfig(
        summarization_model=Sonnet(),
        embedding_models={"MiniLM": emb},
        cluster_embedding_model="MiniLM",
    )
    builder = ClusterTreeBuilder(config)
    leaves = {}
    for i, t in enumerate(texts):
        _, leaves[i] = builder.create_node(i, t)
    layer_to_nodes = {0: list(leaves.values())}
    all_nodes = dict(leaves)
    builder.construct_tree(
        all_nodes, all_nodes, layer_to_nodes, use_multithreading=True
    )
    nodes, vecs_out = [], []
    for idx in sorted(all_nodes):
        node = all_nodes[idx]
        leaf = idx < len(chunks)
        nodes.append(
            {
                "label": chunks[idx]["label"]
                if leaf
                else f"RAPTOR summary #{idx}",
                "text": chunks[idx]["text"] if leaf else node.text,
                "layer": 0 if leaf else 1,
                "children": sorted(node.children),
            }
        )
        vecs_out.append(node.embeddings["MiniLM"])
    out = retrievers.INDEX
    (out / f"raptor-{repo}.json").write_text(json.dumps(nodes))
    np.save(out / f"raptor-{repo}.npy", np.asarray(vecs_out, dtype=np.float32))
    stats = {
        "repo": repo,
        "leaves": len(chunks),
        "summaries": len(all_nodes) - len(chunks),
        "layers": {k: len(v) for k, v in layer_to_nodes.items()},
        "seconds": round(time.time() - t0, 1),
    }
    with open(common.RUNS / "raptor_build.jsonl", "a") as f:
        f.write(json.dumps(stats) + "\n")
    print(stats, flush=True)


if __name__ == "__main__":
    for r in sys.argv[1:]:
        build(r)
