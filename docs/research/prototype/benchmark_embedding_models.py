"""Timed embedding benchmark: every candidate model over the identical chunk corpus.

Produces the numbers for the model-comparison report: on this machine, embedding
this corpus takes X per model. Unlike test_embedding_models.py (which persists
vectors incrementally and therefore skips already-embedded hashes), this script
always re-encodes everything, so timings are comparable across models regardless
of DB state. Nothing is written to the embeddings table.

Per model: load time, wall time over all unique-hash chunks, ms/chunk, chunks/s,
KB of text/s, dims, param count. Plus machine info (chip, RAM, torch backend).
Appends one run record to .hrono/embedding-benchmark.json (a list — history is
documentation; re-runs never overwrite).

A model that fails to load/encode is recorded with its error and skipped — a
failed candidate is a result too.

Usage: uv run python benchmark_embedding_models.py  [model ...]
"""

import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import torch
from sentence_transformers import SentenceTransformer

from test_embedding_models import load_chunks_with_content

APP_DIR = Path(__file__).resolve().parent
OUT_PATH = APP_DIR / ".hrono" / "embedding-benchmark.json"

MODELS = [
    "Qwen/Qwen3-Embedding-0.6B",
    "ibm-granite/granite-embedding-311m-multilingual-r2",
    "ibm-granite/granite-embedding-97m-multilingual-r2",
]
BATCH_SIZE = 8  # identical for every model — this is a model comparison, not a batch-size sweep


def main() -> None:
    models = sys.argv[1:] or MODELS
    chunks = load_chunks_with_content()
    texts = list({c["hash"]: c["content"] for c in chunks}.values())
    total_kb = sum(len(t) for t in texts) / 1024
    print(f"corpus: {len(texts)} unique-hash chunks, {total_kb:.0f} KB of text")

    results = [bench_model(name, texts, total_kb) for name in models]
    record = {"machine": machine_info(), "corpus_chunks": len(texts),
              "corpus_kb": round(total_kb), "batch_size": BATCH_SIZE, "results": results}

    history = json.loads(OUT_PATH.read_text()) if OUT_PATH.exists() else []
    history.append(record)
    OUT_PATH.write_text(json.dumps(history, indent=2))
    print(f"\nappended run to {OUT_PATH} ({len(history)} run(s) recorded)")


def bench_model(name: str, texts: list[str], total_kb: float) -> dict:
    print(f"\n--- {name} ---")
    try:
        t0 = time.monotonic()
        model = SentenceTransformer(name)
        load_s = time.monotonic() - t0
        params = sum(p.numel() for p in model.parameters())

        t0 = time.monotonic()
        vectors = model.encode(texts, batch_size=BATCH_SIZE,
                               normalize_embeddings=True, show_progress_bar=False)
        encode_s = time.monotonic() - t0
    except Exception as e:  # noqa: BLE001 — a failed candidate is a recorded result
        print(f"FAILED: {e}")
        return {"model": name, "error": f"{type(e).__name__}: {e}"}

    result = {
        "model": name,
        "params_m": round(params / 1e6),
        "dims": int(vectors.shape[1]),
        "load_s": round(load_s, 1),
        "encode_s": round(encode_s, 1),
        "ms_per_chunk": round(1000 * encode_s / len(texts)),
        "chunks_per_s": round(len(texts) / encode_s, 2),
        "kb_per_s": round(total_kb / encode_s, 1),
    }
    print(f"{result['params_m']}M params, {result['dims']} dims | load {result['load_s']}s | "
          f"{result['ms_per_chunk']} ms/chunk, {result['chunks_per_s']} chunks/s, {result['kb_per_s']} KB/s")

    # free MPS memory before the next candidate so timings don't degrade run-over-run
    del model
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()
    return result


def machine_info() -> dict:
    chip = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                          capture_output=True, text=True).stdout.strip()
    mem_gb = int(subprocess.run(["sysctl", "-n", "hw.memsize"],
                                capture_output=True, text=True).stdout.strip() or 0) // 2**30
    backend = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
    return {"chip": chip, "ram_gb": mem_gb, "backend": backend,
            "platform": platform.platform(), "torch": torch.__version__}


if __name__ == "__main__":
    main()
