# ruff: noqa: E501 - report tables and SQL read best on one line
"""Condense a few sections with each prompt and compare the results.

The sections: the E23 payment-listener case (the listener, two files of its
flow, three test files it is mistaken for), plus a configuration file and a
markdown document to see how each prompt treats non-code. `today` reuses the
condensations stored in the tree; every other prompt calls Haiku once per
section, through hrono's claude-code client, with the input shaped as
hrono's condense op shapes it. Calls are cached by request.

Per prompt it reports:
- words per condensation;
- identifiers not found in the source (hrono's own faithfulness check);
- with granite-97m embeddings of the condensations (the chosen model), how
  often the listener sits closer to a file of its flow than to a test file,
  and the margin between the two means.

Writes `outputs.md` (every condensation side by side) and `table.md`.

Usage: uv run python pilot.py DB OUT_DIR CACHE [prompt ...]
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from prompts import PROMPTS
from sentence_transformers import SentenceTransformer

from hrono.llm.claude_code import ClaudeCodeClient
from hrono.llm.client import CompletionRequest
from hrono.summarize.faithfulness import faithfulness

MODEL = {"model": "haiku"}
EMBEDDER = "ibm-granite/granite-embedding-97m-multilingual-r2"
STORED = "condense"
ANCHOR = "lear/queue_services/entity-pay/src/entity_pay/worker.py"
NEAR = (
    "lear/queue_services/business-pay/src/business_pay/resources/pay_filer.py",
    "lear/jobs/future-effective-filings/file_future_effective.py",
)
FAR = (
    "lear/queue_services/business-pay/tests/integration/test_nats_stan.py",
    "lear/queue_services/business-pay/tests/integration/test_queue_publish.py",
    "lear/queue_services/business-pay/tests/conftest.py",
)
OTHER = (
    "lear/queue_services/entity-pay/src/entity_pay/config.py",
    "sbc-pay/docs/docs/architecture/FAS_Intgeration.md",
)
FILES = (ANCHOR, *NEAR, *FAR, *OTHER)


def main(db_path: str, out: str, cache_path: str, *names: str) -> None:
    sections = _sections(db_path)
    cache_file = Path(cache_path)
    cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
    client = ClaudeCodeClient(cache_file.parent / "claude-workdir")
    prompts = {name: PROMPTS[name] for name in names or PROMPTS}

    def condense(prompt: str, section: dict) -> str:
        rendered = prompt.replace(
            "{content}", f"File: {section['path']}\n\n{section['body']}"
        )
        key = hashlib.sha256(
            f"{MODEL['model']}\n{rendered}".encode()
        ).hexdigest()
        if key not in cache:
            result = client.complete(
                CompletionRequest(model=MODEL, system="", content=rendered)
            )
            cache[key] = result.text
        return cache[key]

    with ThreadPoolExecutor(4) as pool:
        made = {
            name: list(
                pool.map(
                    lambda s, p=prompt, n=name: (
                        s["stored"] if n == "today" else condense(p, s)
                    ),
                    sections,
                )
            )
            for name, prompt in prompts.items()
        }
    cache_file.write_text(json.dumps(cache))

    embedder = SentenceTransformer(EMBEDDER)
    rows = [
        _score(name, texts, sections, embedder) for name, texts in made.items()
    ]
    out_dir = Path(out)
    (out_dir / "table.md").write_text(_table(rows))
    (out_dir / "outputs.md").write_text(_outputs(made, sections))
    print(_table(rows))


def _sections(db_path: str) -> list[dict]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT s.source || '/' || s.path, s.ordinal, c.body, d.text "
        "FROM sections s JOIN contents c USING (content_hash) "
        "JOIN condensations d ON d.content_hash = s.content_hash "
        "AND d.model_name = ? WHERE s.source_type = 'git' "
        "ORDER BY s.source, s.path, s.ordinal",
        (STORED,),
    ).fetchall()
    picked = [
        {
            "path": p,
            "ordinal": o,
            "body": b.decode("utf-8", "replace"),
            "stored": t,
        }
        for p, o, b, t in rows
        if p in FILES
    ]
    found = {s["path"] for s in picked}
    if found != set(FILES):
        raise SystemExit(f"not indexed: {sorted(set(FILES) - found)}")
    return sorted(picked, key=lambda s: (FILES.index(s["path"]), s["ordinal"]))


def _score(name: str, texts: list[str], sections: list[dict], embedder) -> dict:
    vectors = embedder.encode(texts, normalize_embeddings=True)
    files = {}
    for path in FILES:
        rows = [i for i, s in enumerate(sections) if s["path"] == path]
        mean = vectors[rows].mean(0)
        files[path] = mean / np.linalg.norm(mean)
    anchor = files[ANCHOR]
    near = [float(anchor @ files[f]) for f in NEAR]
    far = [float(anchor @ files[f]) for f in FAR]
    unsupported = [
        len(faithfulness(text, s["body"]))
        for text, s in zip(texts, sections, strict=True)
    ]
    return {
        "prompt": name,
        "words": round(np.mean([len(t.split()) for t in texts])),
        "unsupported": sum(unsupported),
        "near_wins": np.mean([n > f for n in near for f in far]),
        "margin": np.mean(near) - np.mean(far),
    }


def _table(rows: list[dict]) -> str:
    lines = [
        "| prompt | words per section | unsupported identifiers (all 9) | listener nearer its flow than a test | margin |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| `{r['prompt']}` | {r['words']} | {r['unsupported']} | "
            f"{r['near_wins']:.0%} | {r['margin']:+.3f} |"
        )
    return "\n".join(lines) + "\n"


def _outputs(made: dict, sections: list[dict]) -> str:
    out = []
    for i, section in enumerate(sections):
        out.append(f"## `{section['path']}` (section {section['ordinal']})\n")
        for name, texts in made.items():
            out.append(f"### {name}\n\n{texts[i].strip()}\n")
    return "\n".join(out)


if __name__ == "__main__":
    main(*sys.argv[1:4], *sys.argv[4:])
