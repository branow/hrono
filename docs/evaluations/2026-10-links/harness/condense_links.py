# ruff: noqa: E501 - experiment harness; prompts read best whole
"""Pilot: does condensation give usable links when it is asked for them?

Each section is condensed with the v3 `condense` prompt plus one request: list
what the chunk refers to outside itself. The answer is enforced as JSON by the
CLI's --json-schema. Each reference is then embedded and matched against the
v3 tree's leaf pages, mechanically, to see whether it lands on the right page.

Usage: uv run python condense_links.py call   # LLM, one call per section
       uv run python condense_links.py link   # no LLM
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

DB = Path.home() / "hrono-eval/db/hrono-v3.db"
OUT = Path(__file__).resolve().parents[1] / "pilot.json"
WORKDIR = Path(
    "/private/tmp/claude-501/-Users-orest-repos-hrono/f227ac97-692b-47d3-9db3-a839049bf7dc/scratchpad/cliwd"
)
MODEL = "haiku"
EMBED = "ibm-granite/granite-embedding-97m-multilingual-r2"
SECTIONS = [
    37132,  # lear legal-api v2 business_filings.py: fee lines with waiveFees
    42294,  # sbc-pay invoice.py: invoice creation resource
    42292,  # sbc-pay fee.py: fee quote
    34577,  # business-filings-ui filing-mixin.ts
    34650,  # business-filings-ui AnnualReport.vue: staff payment
    38766,  # lear entity-filer worker.py: queue listener
    42541,  # sbc-pay test_fee.py: a test
    41715,  # FAS integration architecture doc
    40533,  # build-deploy doc
    36051,  # openshift rbac template: config
    37133,  # lear legal-api v2 business_filings.py: posts the invoice to pay-api
]
LINKS = (
    "\n\nAlso list REFERENCES: everything outside this chunk that it hands "
    "work to, takes work from, or depends on - another service, endpoint, "
    "queue, job, document, page, person, team, table or named component. "
    "For each give `target`, named as the chunk names it (verbatim), and "
    "`relation`, one sentence: what passes between them, in which direction, "
    "and any condition the chunk attaches. Only what the chunk literally "
    "shows. Leave out standard libraries and frameworks. An empty list is "
    "fine."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "condensed": {"type": "string"},
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "relation": {"type": "string"},
                },
                "required": ["target", "relation"],
            },
        },
    },
    "required": ["condensed", "references"],
}
SYSTEM = (
    "You are a text-summarization engine. The message you are given is the "
    "only input there is: it carries both the instruction and the material. "
    "Follow the instruction and answer in the requested structure."
)


def connect() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def template(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT config FROM registry WHERE collection = 'prompts' AND name = 'condense'"
    ).fetchone()
    return json.loads(row[0])["template"]


def section(conn: sqlite3.Connection, sid: int) -> dict:
    source, path, body = conn.execute(
        "SELECT s.source, s.path, c.body FROM sections s "
        "JOIN contents c USING (content_hash) WHERE s.id = ?",
        (sid,),
    ).fetchone()
    text = body.decode() if isinstance(body, bytes) else body
    return {"id": sid, "source": source, "path": path, "body": text}


def call(prompt: str) -> dict:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    argv = [
        "claude",
        "-p",
        "--model",
        MODEL,
        "--max-turns",
        "3",
        "--allowed-tools",
        "",
        "--safe-mode",
        "--system-prompt",
        SYSTEM,
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(SCHEMA),
    ]
    done = subprocess.run(
        argv,
        input=prompt,
        capture_output=True,
        text=True,
        cwd=WORKDIR,
        timeout=300,
    )
    payload = json.loads(done.stdout)
    return {
        "structured": payload.get("structured_output"),
        "result": payload.get("result"),
        "subtype": payload.get("subtype"),
        "cost": payload.get("total_cost_usd"),
    }


def run_calls() -> None:
    conn = connect()
    tpl = template(conn)
    items = [section(conn, sid) for sid in SECTIONS]

    def one(item: dict) -> dict:
        prompt = tpl.replace("{content}", item["body"]) + LINKS
        return {
            **{k: item[k] for k in ("id", "source", "path")},
            **call(prompt),
        }

    with ThreadPoolExecutor(5) as pool:
        out = list(pool.map(one, items))
    OUT.write_text(json.dumps(out, indent=1))
    print("cost", sum(o["cost"] or 0 for o in out))


TEST = re.compile(
    r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.\w+$|\.(spec|test)\.\w+$"
)


def run_links() -> None:
    from sentence_transformers import SentenceTransformer

    conn = connect()
    rows = conn.execute(
        "SELECT p.id, p.path, p.source_type, p.source, p.section_id, e.vector "
        "FROM passages p JOIN embeddings e ON e.content_hash = p.content_hash"
    ).fetchall()
    level = dict(conn.execute("SELECT id, level FROM nodes"))
    leaf_of_section: dict[int, int] = {}
    for sid, node in conn.execute(
        "SELECT m.section_id, MIN(m.node_id) FROM node_members m "
        "JOIN nodes n ON n.id = m.node_id WHERE n.level = 0 GROUP BY 1"
    ):
        leaf_of_section[sid] = node
    title = {
        n: (t or "").strip().splitlines()[0].lstrip("# ") if t else "?"
        for n, t in conn.execute("SELECT node_id, text FROM briefs")
    }
    page = []
    for _pid, path, kind, source, sid, _ in rows:
        if kind == "node":
            node = int(source.removeprefix("node-"))
            page.append(node if level.get(node) == 0 else None)
        elif TEST.search(path or ""):
            page.append(None)
        else:
            page.append(leaf_of_section.get(sid))
    keep = np.array([p is not None for p in page])
    m = np.stack([np.frombuffer(r[5], dtype=np.float32) for r in rows])
    m = m / np.linalg.norm(m, axis=1, keepdims=True)
    model = SentenceTransformer(EMBED)
    for item in json.loads(OUT.read_text()):
        own = leaf_of_section.get(item["id"])
        refs = (item["structured"] or {}).get("references", [])
        print(
            f"\n## {item['source']}/{item['path']} (own page {own}: {title.get(own)})"
        )
        for ref in refs:
            q = model.encode([f"{ref['target']}: {ref['relation']}"])[0]
            q = q / np.linalg.norm(q)
            scores = np.where(keep, m @ q, -1.0)
            best: dict[int, float] = {}
            for i in np.argsort(-scores):
                best.setdefault(page[i], float(scores[i]))
                if len(best) == 3:
                    break
            hits = "; ".join(
                f"{'SELF ' if n == own else ''}{n} {title.get(n, '?')[:60]} ({s:.2f})"
                for n, s in best.items()
            )
            print(f"- {ref['target']} -- {ref['relation']}\n    -> {hits}")


if __name__ == "__main__":
    {"call": run_calls, "link": run_links}[sys.argv[1]]()
