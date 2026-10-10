# ruff: noqa: E501, E741, B904, B905, B007, B023
"""LightRAG (HKU, lightrag-hku 1.5.7) over the same files, retrieval only.

Indexing uses LightRAG's own pipeline and defaults (fixed-token chunks,
entity/relation extraction, graph merge), with gleaning off to bound cost.
Extraction and query keyword extraction run on Claude Haiku via the CLI, the
model hrono condenses with; embeddings are all-MiniLM-L6-v2. At query time
LightRAG's hybrid context (entities, relations, source chunks) is returned
and the shared answer step does the rest.

    uv run python lightrag_adapter.py build flask
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
import time

import common
import numpy as np

STORE = common.ROOT / "cache" / "lightrag"
_GATE = None
_RAGS = {}


async def _llm(prompt, system_prompt=None, history_messages=None, **kwargs):
    global _GATE
    if _GATE is None:
        _GATE = asyncio.Semaphore(8)
    history = history_messages or []
    if history:
        prior = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in history)
        prompt = f"{prior}\n\n[user]\n{prompt}"
    async with _GATE:
        return await asyncio.to_thread(
            common.llm,
            prompt,
            system=system_prompt or "You are a helpful assistant.",
            model="haiku",
            role="lightrag",
        )


async def _embed(texts, **kwargs):
    vecs = await asyncio.to_thread(
        common.encode,
        list(texts),
        batch_size=64,
        normalize_embeddings=True,
    )
    return np.asarray(vecs, dtype=np.float32)


async def _rag(repo):
    if repo not in _RAGS:
        from lightrag import LightRAG
        from lightrag.utils import EmbeddingFunc

        rag = LightRAG(
            working_dir=str(STORE / repo),
            llm_model_func=_llm,
            llm_model_name="claude-haiku",
            llm_model_max_async=8,
            entity_extract_max_gleaning=0,
            embedding_func=EmbeddingFunc(
                embedding_dim=384, max_token_size=256, func=_embed
            ),
        )
        await rag.initialize_storages()
        _RAGS[repo] = rag
    return _RAGS[repo]


async def _build(repo):
    t0 = time.time()
    rag = await _rag(repo)
    files = common.corpus_files(repo)
    # LightRAG deduplicates documents by file name, so the path is flattened
    # into the name (src/flask/__init__.py -> src__flask____init__.py).
    await rag.ainsert(
        [f"File: {p}\n\n{t}" for p, t in files],
        file_paths=[p.replace("/", "__") for p, _ in files],
    )
    # the pipeline can return with documents still queued; drain it
    for _ in range(50):
        statuses = json.loads(
            (STORE / repo / "kv_store_doc_status.json").read_text()
        )
        busy = [
            v
            for v in statuses.values()
            if v.get("status") not in ("processed", "failed")
        ]
        print(f"{len(busy)} documents not finished", flush=True)
        if not busy:
            break
        await rag.apipeline_process_enqueue_documents()
        await asyncio.sleep(2)
    await rag.finalize_storages()
    stats = {
        "repo": repo,
        "files": len(files),
        "seconds": round(time.time() - t0, 1),
    }
    with open(common.RUNS / "lightrag_build.jsonl", "a") as f:
        f.write(json.dumps(stats) + "\n")
    print(stats, flush=True)


_LOOP = None
_LOOP_LOCK = threading.Lock()


def context(repo: str, question: str) -> str:
    """LightRAG's hybrid-mode context for one question."""
    global _LOOP
    from lightrag import QueryParam

    if _LOOP is None:
        _LOOP = asyncio.new_event_loop()

    async def go():
        rag = await _rag(repo)
        return await rag.aquery(
            question, param=QueryParam(mode="hybrid", only_need_context=True)
        )

    with _LOOP_LOCK:
        out = _LOOP.run_until_complete(go())
    return out if isinstance(out, str) else json.dumps(out)


if __name__ == "__main__":
    if sys.argv[1] == "build":
        for r in sys.argv[2:]:
            asyncio.run(_build(r))
