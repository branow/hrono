# ruff: noqa: E501 - report tables and SQL read best on one line
"""Pilot: which embedding model tells the E23 files apart from look-alikes?

A handful of files, each case an anchor with files it belongs with ("near",
same flow or feature) and files it only looks like ("far", other services,
tests). Each model embeds every section of these files, once as raw text
and once as hrono's stored condensation; a file is the mean of its
sections. A good model puts the anchor closer to every near file than to
every far file.

Per model and text kind it prints, for each case, the margin
mean(cos anchor-near) - mean(cos anchor-far), and the share of (near, far)
pairs where the near file is the closer one.

Usage: uv run python embed_pilot.py DB [model ...]
"""

from __future__ import annotations

import sqlite3
import sys
import time

import numpy as np
from sentence_transformers import SentenceTransformer

CASES = {
    "E23 payment listener": {
        "anchor": "lear/queue_services/entity-pay/src/entity_pay/worker.py",
        "near": [
            "lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py",
            "lear/queue_services/entity-filer/src/entity_filer/worker.py",
        ],
        "far": [
            "lear/queue_services/business-pay/tests/integration/test_nats_stan.py",
            "lear/queue_services/business-pay/tests/integration/test_queue_publish.py",
            "lear/queue_services/business-pay/tests/conftest.py",
        ],
    },
    "E23 future-effective job": {
        "anchor": "lear/jobs/future-effective-filings/file_future_effective.py",
        "near": [
            "lear/queue_services/entity-filer/src/entity_filer/worker.py",
            "lear/queue_services/entity-pay/src/entity_pay/worker.py",
        ],
        "far": [
            "lear/jobs/involuntary-dissolutions/involuntary_dissolutions.py",
            "lear/jobs/involuntary-dissolutions/tests/unit/test_job.py",
        ],
    },
    "control: account model": {
        "anchor": "sbc-pay/pay-api/src/pay_api/models/payment_account.py",
        "near": [
            "sbc-pay/pay-api/src/pay_api/services/payment_account.py",
            "sbc-pay/pay-api/src/pay_api/services/non_sufficient_funds.py",
        ],
        "far": ["sbc-auth/auth-api/src/auth_api/models/org.py"],
    },
}

# model id -> (load options, text prefix the model card asks for)
MODELS = {
    "sentence-transformers/all-MiniLM-L6-v2": ({}, ""),
    "BAAI/bge-base-en-v1.5": ({}, ""),
    "nomic-ai/nomic-embed-text-v1.5": (
        {"trust_remote_code": True},
        "clustering: ",
    ),
    "jinaai/jina-embeddings-v2-base-code": ({"trust_remote_code": True}, ""),
    "ibm-granite/granite-embedding-97m-multilingual-r2": ({}, ""),
}
MAX_TOKENS = 8192  # long-context models read whole sections; others cap lower


def main(db_path: str, *models: str) -> None:
    texts = _texts(db_path)
    for model_id in models or MODELS:
        options, prefix = MODELS[model_id]
        model = SentenceTransformer(model_id, **options)
        model.max_seq_length = min(
            MAX_TOKENS, model.max_seq_length or MAX_TOKENS
        )
        for kind in ("raw", "condensed"):
            started = time.time()
            files = {
                name: _file_vector(model, prefix, sections[kind])
                for name, sections in texts.items()
            }
            seconds = time.time() - started
            print(
                f"\n{model_id} [{kind}] reads {model.max_seq_length} tokens, "
                f"{seconds:.1f}s for {sum(len(s[kind]) for s in texts.values())} texts"
            )
            for case, spec in CASES.items():
                anchor = files[spec["anchor"]]
                near = [float(anchor @ files[f]) for f in spec["near"]]
                far = [float(anchor @ files[f]) for f in spec["far"]]
                won = np.mean([n > f for n in near for f in far])
                print(
                    f"  {case:26} near {np.mean(near):.3f}  far {np.mean(far):.3f}  "
                    f"margin {np.mean(near) - np.mean(far):+.3f}  near wins {won:.0%}"
                )


def _texts(db_path: str) -> dict[str, dict[str, list[str]]]:
    wanted = sorted(
        {spec["anchor"] for spec in CASES.values()}
        | {f for spec in CASES.values() for f in spec["near"] + spec["far"]}
    )
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    texts: dict[str, dict[str, list[str]]] = {
        name: {"raw": [], "condensed": []} for name in wanted
    }
    for name, body, condensed in conn.execute(
        "SELECT s.source || '/' || s.path, c.body, d.text FROM sections s "
        "JOIN contents c USING (content_hash) "
        "JOIN condensations d ON d.content_hash = s.content_hash "
        "AND d.model_name = 'condense' "
        "WHERE s.source_type = 'git' ORDER BY s.ordinal"
    ):
        if name in texts:
            texts[name]["raw"].append(body.decode("utf-8", "replace"))
            texts[name]["condensed"].append(condensed)
    missing = [name for name, t in texts.items() if not t["raw"]]
    if missing:
        raise SystemExit(f"not indexed: {missing}")
    return texts


def _file_vector(model, prefix: str, sections: list[str]) -> np.ndarray:
    vectors = model.encode(
        [prefix + text for text in sections],
        batch_size=4,
        normalize_embeddings=True,
    )
    mean = vectors.mean(0)
    return mean / np.linalg.norm(mean)


if __name__ == "__main__":
    main(*sys.argv[1:])
