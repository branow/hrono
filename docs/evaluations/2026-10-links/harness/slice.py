# ruff: noqa: E501 - experiment harness
"""Stage 3: condense a slice with references, link it, rebuild its briefs.

The slice: every section of a file cited by three hard questions
(hard-inconsistency-1 fee waiver, hard-failure-1 payment notification,
hard-legacy-0 two payment listeners): 100 sections in 21 leaf pages.

Then each reference is matched to a leaf page by its rare names
(links2.py), and every leaf page in the slice gets a new brief: the v3
`brief` prompt over its members' condensations (the new ones where the slice
re-condensed them), plus a CONNECTIONS block - what this page sends to and
receives from other pages - and one more line in the prompt asking for them.
A judge then says, for each fact of the three questions, whether the pages
that hold its files state it: the v3 briefs against the new ones.

Usage: uv run --with claude-agent-sdk python slice.py condense
       uv run --extra embed python slice.py link
       uv run --with claude-agent-sdk python slice.py brief
       uv run --with claude-agent-sdk python slice.py judge
"""

from __future__ import annotations

import asyncio
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import condense_links as c  # noqa: E402
import links2  # noqa: E402

QIDS = ["hard-inconsistency-1", "hard-failure-1", "hard-legacy-0"]
HARD = Path.home() / "hrono-deep/data/hard15.json"
DIR = c.OUT.parent / "slice"


def questions() -> list[dict]:
    by = {q["qid"]: q for q in json.loads(HARD.read_text())}
    return [by[q] for q in QIDS]


def slice_sections(conn) -> list[int]:
    files = {
        f for q in questions() for fact in q["facts"] for f in fact["files"]
    }
    out = []
    for sid, source, path in conn.execute(
        "SELECT id, source, path FROM sections"
    ):
        if f"{source}/{path}" in files:
            out.append(sid)
    return sorted(out)


def condense() -> None:
    conn = c.connect()
    tpl = c.template(conn)
    DIR.mkdir(exist_ok=True)
    done_path = DIR / "condensed.json"
    done = json.loads(done_path.read_text()) if done_path.exists() else {}
    todo = [s for s in slice_sections(conn) if str(s) not in done]
    items = [c.section(conn, s) for s in todo]

    def one(item: dict) -> tuple[str, dict]:
        try:
            got = asyncio.run(
                links2._ask(
                    tpl.replace("{content}", item["body"]) + links2.LINKS
                )
            )
        except Exception as exc:  # noqa: BLE001 - a pilot records and goes on
            got = {"error": str(exc)}
        return str(item["id"]), {
            "path": f"{item['source']}/{item['path']}",
            **got,
        }

    with ThreadPoolExecutor(6) as pool:
        for sid, got in pool.map(one, items):
            done[sid] = got
            done_path.write_text(json.dumps(done, indent=1))
    ok = [v for v in done.values() if v.get("structured")]
    print(
        "sections",
        len(done),
        "ok",
        len(ok),
        "cost",
        round(sum(v.get("cost") or 0 for v in done.values()), 2),
    )


def leaves_of(conn) -> dict[int, int]:
    return dict(
        conn.execute(
            "SELECT m.section_id, MIN(m.node_id) FROM node_members m "
            "JOIN nodes n ON n.id = m.node_id WHERE n.level = 0 GROUP BY 1"
        )
    )


def titles(conn) -> dict[int, str]:
    return {
        n: (t or "?").strip().splitlines()[0].lstrip("# ")
        for n, t in conn.execute("SELECT node_id, text FROM briefs")
    }


def link() -> None:
    """Each reference to its best page by rare names; no LLM."""
    import re

    conn = c.connect()
    leaf = leaves_of(conn)
    level = dict(conn.execute("SELECT id, level FROM nodes"))
    # a page whose members are mostly tests asserts the link, it is not its end
    tests: dict[int, list[bool]] = {}
    for node, path in conn.execute(
        "SELECT m.node_id, s.path FROM node_members m JOIN sections s ON s.id = m.section_id"
    ):
        tests.setdefault(node, []).append(bool(c.TEST.search(path)))
    test_page = {n for n, flags in tests.items() if sum(flags) > len(flags) / 2}
    page_of: dict[int, int | None] = {}
    for pid, path, kind, source, sid in conn.execute(
        "SELECT id, path, source_type, source, section_id FROM passages"
    ):
        if kind == "node":
            node = int(source.removeprefix("node-"))
            page_of[pid] = (
                node if level.get(node) == 0 and node not in test_page else None
            )
        elif c.TEST.search(path or ""):
            page_of[pid] = None
        else:
            page_of[pid] = leaf.get(sid)
    done = json.loads((DIR / "condensed.json").read_text())
    # A page that refers to the same target is another caller of it, not its
    # receiver: two legal-API pages both POST to PAYMENT_SVC_URL, and the
    # name ties them, not the payment service they both call.
    refers: dict[int | None, set[str]] = {}
    for sid, got in done.items():
        for ref in (got.get("structured") or {}).get("references", []):
            refers.setdefault(leaf.get(int(sid)), set()).update(
                n.lower() for n in links2.names(ref["target"])
            )
    links = []
    for sid, got in done.items():
        own = leaf.get(int(sid))
        for ref in (got.get("structured") or {}).get("references", []):
            text = f"{ref['target']} {ref['what']}"
            mine = {n.lower() for n in links2.names(ref["target"])}
            score: dict[int, float] = {}
            for name in links2.names(text):
                q = links2.phrase(name)
                if not q:
                    continue
                hits = conn.execute(
                    "SELECT passage_id FROM passages_fts WHERE passages_fts MATCH ? LIMIT 2000",
                    (q,),
                ).fetchall()
                pages = {page_of.get(p) for (p,) in hits} - {None, own}
                pages = {p for p in pages if not (mine & refers.get(p, set()))}
                if pages and len(pages) <= 40:
                    for page in pages:
                        score[page] = score.get(page, 0.0) + 1.0 / len(pages)
            if not score:
                continue
            best = max(score, key=lambda p: score[p])
            if score[best] < 0.25:  # only common names agreed: no link
                continue
            links.append(
                {
                    "from": own,
                    "to": best,
                    "score": round(score[best], 2),
                    "section": int(sid),
                    "path": got["path"],
                    **ref,
                }
            )
    (DIR / "links.json").write_text(json.dumps(links, indent=1))
    title = titles(conn)
    print("links", len(links))
    for item in links[:400]:
        print(
            f"{item['from']} -> {item['to']} {title.get(item['to'], '?')[:50]} | [{item['direction']}] {item['target'][:60]} ({item['score']})"
        )
    _ = re


CONNECT = (
    "\n7. Its connections, from the CONNECTIONS block when there is one: for "
    "each other part it sends to or receives from, one line - which part, "
    "what crosses and in which direction, and which side checks what (who "
    "may, which credential is sent, what is not checked). Only connections "
    "the notes show."
)


def slice_leaves(conn) -> list[int]:
    leaf = leaves_of(conn)
    return sorted({leaf[s] for s in slice_sections(conn) if s in leaf})


def connections(node: int, links: list[dict], title: dict[int, str]) -> str:
    out = [
        f'- sends to "{title.get(item["to"], "?")}": {item["target"]} - {item["what"]}'
        for item in links
        if item["from"] == node and item["direction"] != "receives"
    ]
    out += [
        f'- receives from "{title.get(item["to"], "?")}": {item["target"]} - {item["what"]}'
        for item in links
        if item["from"] == node and item["direction"] == "receives"
    ]
    out += [
        f'- "{title.get(item["from"], "?")}" ({item["path"]}) {item["direction"]} here: {item["target"]} - {item["what"]}'
        for item in links
        if item["to"] == node
    ]
    return "\n".join(dict.fromkeys(out))


async def _sonnet(prompt: str) -> dict:
    import shutil

    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    options = ClaudeAgentOptions(
        model="sonnet",
        system_prompt=c.SYSTEM,
        tools=[],
        max_turns=3,
        setting_sources=[],
        cwd=str(c.WORKDIR),
        cli_path=shutil.which("claude"),
        thinking={"type": "disabled"},
    )
    result = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message
    return {"text": result.result, "cost": result.total_cost_usd}


def brief() -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src"))
    from hrono.summarize.briefs import labeled

    conn = c.connect()
    template = json.loads(
        conn.execute(
            "SELECT config FROM registry WHERE collection = 'prompts' AND name = 'brief'"
        ).fetchone()[0]
    )["template"]
    template = template.replace("\n\nLeave out:", CONNECT + "\n\nLeave out:", 1)
    new = json.loads((DIR / "condensed.json").read_text())
    links = json.loads((DIR / "links.json").read_text())
    title = titles(conn)
    out_path = DIR / "briefs.json"
    out = json.loads(out_path.read_text()) if out_path.exists() else {}

    def one(node: int) -> tuple[str, dict]:
        rows = (
            c.connect()
            .execute(
                "SELECT s.id, s.path, d.text FROM node_members m "
                "JOIN sections s ON s.id = m.section_id "
                "JOIN condensations d ON d.content_hash = s.content_hash "
                "AND d.model_name = 'condense-contracts' WHERE m.node_id = ? "
                "ORDER BY s.uri, s.id",
                (node,),
            )
            .fetchall()
        )
        pairs = []
        for sid, path, text in rows:
            fresh = (new.get(str(sid)) or {}).get("structured")
            pairs.append((path, fresh["condensed"] if fresh else text))
        content = labeled(pairs)
        block = connections(node, links, title)
        if block:
            content += "\n\n=== CONNECTIONS ===\n" + block
        got = asyncio.run(_sonnet(template.replace("{content}", content)))
        return str(node), {**got, "connections": block}

    todo = [n for n in slice_leaves(conn) if str(n) not in out]
    with ThreadPoolExecutor(4) as pool:
        for node, got in pool.map(one, todo):
            out[node] = got
            out_path.write_text(json.dumps(out, indent=1))
    print(
        "briefs",
        len(out),
        "cost",
        round(sum(v["cost"] or 0 for v in out.values()), 2),
    )


JUDGE = """You check whether a map of a software system states a fact.

FACT:
{fact}

MAP PAGES:
{pages}

Does the map state this fact? Answer "yes" if every claim in the fact is stated (names may differ slightly), "partial" if some claims are stated and others missing, "no" if it is not stated. Then one sentence on what is missing."""

VERDICT = {
    "type": "object",
    "properties": {
        "verdict": {"enum": ["yes", "partial", "no"]},
        "missing": {"type": "string"},
    },
    "required": ["verdict", "missing"],
}


async def _judge(prompt: str) -> dict:
    import shutil

    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    options = ClaudeAgentOptions(
        model="sonnet",
        system_prompt=c.SYSTEM,
        tools=[],
        max_turns=3,
        setting_sources=[],
        cwd=str(c.WORKDIR),
        cli_path=shutil.which("claude"),
        thinking={"type": "disabled"},
        output_format={"type": "json_schema", "schema": VERDICT},
    )
    result = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message
    return {**(result.structured_output or {}), "cost": result.total_cost_usd}


def judge() -> None:
    conn = c.connect()
    leaf = leaves_of(conn)
    secs: dict[str, list[int]] = {}
    for sid, source, path in conn.execute(
        "SELECT id, source, path FROM sections"
    ):
        secs.setdefault(f"{source}/{path}", []).append(sid)
    old = dict(conn.execute("SELECT node_id, text FROM briefs"))
    new = {
        int(k): v["text"]
        for k, v in json.loads((DIR / "briefs.json").read_text()).items()
    }
    jobs = []
    for q in questions():
        for i, fact in enumerate(q["facts"]):
            pages = sorted(
                {
                    leaf[s]
                    for f in fact["files"]
                    for s in secs.get(f, [])
                    if s in leaf
                }
            )
            for arm, texts in (("v3", old), ("links", new)):
                body = "\n\n".join(
                    f"--- page ---\n{texts.get(p, '')}" for p in pages
                )
                jobs.append(
                    (
                        q["qid"],
                        i,
                        arm,
                        JUDGE.format(fact=fact["fact"], pages=body),
                    )
                )

    def one(job):
        qid, i, arm, prompt = job
        return {
            "qid": qid,
            "fact": i,
            "arm": arm,
            **asyncio.run(_judge(prompt)),
        }

    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(one, jobs))
    (DIR / "judged.json").write_text(json.dumps(rows, indent=1))
    points = {"yes": 1.0, "partial": 0.5, "no": 0.0}
    for arm in ("v3", "links"):
        mine = [r for r in rows if r["arm"] == arm]
        print(
            arm,
            round(
                sum(points.get(r.get("verdict"), 0) for r in mine) / len(mine),
                3,
            ),
            {v: sum(r.get("verdict") == v for r in mine) for v in points},
        )
    print("cost", round(sum(r["cost"] or 0 for r in rows), 2))


def judge_notes() -> None:
    """The ceiling: the same facts against the v3 condensations of the
    fact's own files, the detail a brief is written from."""
    conn = c.connect()
    jobs = []
    for q in questions():
        for i, fact in enumerate(q["facts"]):
            blocks = []
            for f in fact["files"]:
                source, path = f.split("/", 1)
                for (text,) in conn.execute(
                    "SELECT d.text FROM sections s JOIN condensations d "
                    "ON d.content_hash = s.content_hash AND d.model_name = 'condense-contracts' "
                    "WHERE s.source = ? AND s.path = ? ORDER BY s.ordinal",
                    (source, path),
                ):
                    blocks.append(f"--- {f} ---\n{text}")
            jobs.append(
                (
                    q["qid"],
                    i,
                    JUDGE.format(fact=fact["fact"], pages="\n\n".join(blocks)),
                )
            )

    def one(job):
        qid, i, prompt = job
        return {
            "qid": qid,
            "fact": i,
            "arm": "notes",
            **asyncio.run(_judge(prompt)),
        }

    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(one, jobs))
    (DIR / "judged-notes.json").write_text(json.dumps(rows, indent=1))
    points = {"yes": 1.0, "partial": 0.5, "no": 0.0}
    print(
        "notes",
        round(
            sum(points.get(r.get("verdict"), 0) for r in rows) / len(rows), 3
        ),
        {v: sum(r.get("verdict") == v for r in rows) for v in points},
        "cost",
        round(sum(r["cost"] or 0 for r in rows), 2),
    )


if __name__ == "__main__":
    {
        "condense": condense,
        "link": link,
        "brief": brief,
        "judge": judge,
        "notes": judge_notes,
    }[sys.argv[1]]()
