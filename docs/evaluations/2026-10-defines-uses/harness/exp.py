# ruff: noqa: E501 - experiment harness; prompts read best whole
"""Defines/uses links on a slice: does a brief that sees what its part is
connected to state the facts hard questions turn on?

The slice is the 21 leaf pages behind three hard questions
(`../../2026-10-links/`): all 574 of their sections.

1. condense: every section with the v3 condense prompt plus two lists, the
   names it DEFINES and the names it USES from elsewhere (with a direction).
2. link (no LLM): uses matched to defines, and senders to receivers, by name
   in SQLite FTS5 - porter-stemmed words first, trigram on a miss - kept only
   when the name is rare. Uses no slice section defines are looked up in the
   whole tree's sources (`expand`), and the sections found are condensed the
   same way, so a link can leave the slice as it would in a full build.
3. brief: the 21 leaves rewritten. B0: new condensations and the CHECKS
   rule. B: B0 plus a CONNECTED ELSEWHERE block, the notes of the linked
   sections in other leaves. C: B plus the slice's level-1 parents rewritten
   with the links between their children and to other areas.
4. claims + judge: each fact split into short yes/no claims, tagged local or
   connection; a judge says per claim whether an arm's pages state it.

Usage (from this folder):
  uv run --with claude-agent-sdk python exp.py condense [N]
  uv run python exp.py expand
  uv run --with claude-agent-sdk python exp.py condense-expand
  uv run python exp.py link
  uv run --with claude-agent-sdk python exp.py brief B0|B
  uv run --with claude-agent-sdk python exp.py upper
  uv run --with claude-agent-sdk python exp.py claims
  uv run --with claude-agent-sdk python exp.py judge RUN
  uv run python exp.py report
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
LINKS_HARNESS = HERE.parents[1] / "2026-10-links" / "harness"
sys.path.insert(0, str(LINKS_HARNESS))
import condense_links as c  # noqa: E402
import slice as sl  # noqa: E402

DATA = HERE.parent / "data"
NAMES_DB = DATA / "names.db"
HAIKU = "claude-haiku-4-5-20251001"
SONNET = "sonnet"

DEFINES_USES = (
    "\n\nAlso return two lists of names, each name exactly as the content "
    "writes it (one identifier, path, endpoint, queue or topic subject, "
    "config key, table, document title or defined term; nothing added):\n"
    "- `defines`: names this content creates that other parts of the system "
    "could call, send to, read or refer to - a public function or class, a "
    "route or endpoint path, a queue or topic it subscribes to, a table it "
    "owns, a term or process a document defines. Leave out private helpers "
    "and local variables.\n"
    "- `uses`: names that live OUTSIDE this content and that it calls, sends "
    "to, receives from, reads or refers to - another module's function or "
    "class, another service's endpoint, a queue or topic it publishes to or "
    "consumes, a shared table, a config key naming another service, another "
    "document or page. Give `direction`: `sends` (calls, publishes, writes, "
    "posts), `receives` (subscribes, consumes, is called by), or `reads` "
    "(reads, depends on, refers to); and `what`: one sentence on what passes "
    "and any condition the content attaches (who may, which credential is "
    "sent, what is or is not checked). Leave out standard libraries, "
    "frameworks, logging, and this content's own names.\n"
    "Empty lists are right when nothing applies."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "condensed": {"type": "string"},
        "defines": {"type": "array", "items": {"type": "string"}},
        "uses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "direction": {"enum": ["sends", "receives", "reads"]},
                    "what": {"type": "string"},
                },
                "required": ["name", "direction", "what"],
            },
        },
    },
    "required": ["condensed", "defines", "uses"],
}


# --- model calls -------------------------------------------------------------


async def _ask(prompt: str, model: str, schema: dict | None = None) -> dict:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    options = ClaudeAgentOptions(
        model=model,
        system_prompt=c.SYSTEM,
        tools=[],
        max_turns=3,
        setting_sources=[],
        extra_args={"safe-mode": None},  # no MCP servers or their notes
        cwd=str(c.WORKDIR),
        cli_path=shutil.which("claude"),
        thinking={"type": "disabled"},
        **(
            {"output_format": {"type": "json_schema", "schema": schema}}
            if schema
            else {}
        ),
    )
    result = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message
    return {
        "structured": result.structured_output if schema else None,
        "text": result.result,
        "cost": result.total_cost_usd,
    }


def ask(prompt: str, model: str, schema: dict | None = None) -> dict:
    for attempt in range(3):
        try:
            return asyncio.run(_ask(prompt, model, schema))
        except Exception as exc:  # noqa: BLE001 - an experiment retries, then records
            error = str(exc)
            if attempt == 2:
                return {"error": error, "cost": 0}
    return {"error": "unreachable", "cost": 0}


def run_pool(fn, items, width: int = 6):
    c.WORKDIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(width) as pool:
        yield from pool.map(fn, items)


def load(name: str) -> dict:
    path = DATA / name
    return json.loads(path.read_text()) if path.exists() else {}


def save(name: str, value) -> None:
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(value, indent=1))


# --- the slice ---------------------------------------------------------------


def slice_leaves(conn) -> list[int]:
    return sl.slice_leaves(conn)


def members(conn, nodes: list[int]) -> list[int]:
    marks = ",".join("?" * len(nodes))
    return [
        r[0]
        for r in conn.execute(
            f"SELECT section_id FROM node_members WHERE node_id IN ({marks}) ORDER BY section_id",
            nodes,
        )
    ]


def stored_condensation(conn, sid: int) -> str:
    row = conn.execute(
        "SELECT d.text FROM sections s JOIN condensations d "
        "ON d.content_hash = s.content_hash AND d.model_name = 'condense-contracts' "
        "WHERE s.id = ?",
        (sid,),
    ).fetchone()
    return row[0] if row else ""


def _condense(sids: list[int], out_name: str) -> None:
    conn = c.connect()
    tpl = c.template(conn)
    done = load(out_name)
    todo = [s for s in sids if str(s) not in done]
    items = [c.section(conn, s) for s in todo]

    def one(item: dict) -> tuple[str, dict]:
        got = ask(
            tpl.replace("{content}", item["body"]) + DEFINES_USES,
            HAIKU,
            SCHEMA,
        )
        return str(item["id"]), {
            "path": f"{item['source']}/{item['path']}",
            **got,
        }

    for n, (sid, got) in enumerate(run_pool(one, items), 1):
        done[sid] = got
        if n % 10 == 0:
            save(out_name, done)
    save(out_name, done)
    ok = [v for v in done.values() if v.get("structured")]
    print(
        out_name,
        "sections",
        len(done),
        "ok",
        len(ok),
        "cost",
        round(sum(v.get("cost") or 0 for v in done.values()), 2),
    )


def condense(limit: int | None = None) -> None:
    conn = c.connect()
    sids = members(conn, slice_leaves(conn))
    _condense(sids[:limit] if limit else sids, "condensed.json")


# --- names and matching ------------------------------------------------------


def words(name: str) -> str:
    """A name as plain words: `PaymentService.create_invoice` and
    `paymentService/createInvoice` both become `payment service create
    invoice`. FTS5 does not split code names, so this runs before indexing
    and before searching."""
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return " ".join(re.findall(r"[A-Za-z0-9]+", name)).lower()


def variants(name: str) -> list[str]:
    """The names inside what the model wrote: `current_app.config.get(
    'PAYMENT_SVC_URL')` holds `PAYMENT_SVC_URL`, and "A, B, C" is three."""
    out = []
    for part in re.split(r",\s+|\s+and\s+", name):
        part = part.strip()
        inner = re.findall(r"['\"]([^'\"]{3,})['\"]", part)
        out += inner
        out += re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", part)
        bare = re.sub(r"\(.*\)$", "", part).strip()
        if bare and not inner:
            out.append(bare)
    return list(dict.fromkeys(o for o in out if words(o)))


def specific(name: str) -> bool:
    """Whether a name can mean one thing: a single plain word ("invoice",
    "filing") matches everywhere, a compound or path does not."""
    w = words(name).split()
    return len(w) >= 2 or (len(w) == 1 and len(w[0]) >= 12)


def light(token: str) -> str:
    """A word less a plural ending only. Porter finds the candidates, but it
    also makes "filing" "file", so the final check uses this lighter form."""
    for end in ("ies", "es", "s"):
        if token.endswith(end) and len(token) - len(end) >= 3:
            return token[: -len(end)] + ("y" if end == "ies" else "")
    return token


def segments(name: str) -> list[str]:
    """A name's qualified parts: `PaymentService.create_invoice` is
    [`payment service`, `create invoice`], each lightly normalized."""
    out = []
    for seg in re.split(r"[./:#]", name):
        w = [light(t) for t in words(seg).split()]
        if w:
            out.append(" ".join(w))
    return out


def same_name(used: str, other: str) -> bool:
    """The whole name matches, or the shorter is the qualified tail of the
    longer (`create_invoice` and `PaymentService.create_invoice`); a phrase
    inside a longer word run (`transaction schema` in `EFTTransactionSchema`)
    does not."""
    a, b = segments(used), segments(other)
    if not a or not b:
        return False
    if a == b:
        return True
    short, long_ = (a, b) if len(a) < len(b) else (b, a)
    return long_[-len(short) :] == short and specific(".".join(short))


def all_condensed() -> dict[str, dict]:
    out = {}
    for name in ("condensed.json", "condensed-expand.json"):
        for sid, got in load(name).items():
            if got.get("structured"):
                out[sid] = got
    return out


def leaf_map(conn) -> dict[int, int]:
    return sl.leaves_of(conn)


def is_test(path: str) -> bool:
    return bool(c.TEST.search(path or ""))


def build_index(conn, condensed: dict[str, dict]) -> sqlite3.Connection:
    """Two FTS5 tables over every defined and used name: porter-stemmed
    words (plural, tense, case, accents) and trigrams (near spellings)."""
    if NAMES_DB.exists():
        NAMES_DB.unlink()
    db = sqlite3.connect(NAMES_DB)
    for table, tokenizer in (
        ("names", "porter unicode61 remove_diacritics 2"),
        ("names_tri", "trigram"),
    ):
        db.execute(
            f"CREATE VIRTUAL TABLE {table} USING fts5(text, raw UNINDEXED, "
            f"section UNINDEXED, leaf UNINDEXED, kind UNINDEXED, "
            f"direction UNINDEXED, tokenize='{tokenizer}')"
        )
    leaf = leaf_map(conn)
    rows = []
    for sid, got in condensed.items():
        if is_test(got["path"]):
            continue
        s = got["structured"]
        for name in s.get("defines", []):
            for v in variants(name):
                rows.append(
                    (words(v), v, int(sid), leaf.get(int(sid)), "def", "")
                )
        for use in s.get("uses", []):
            for v in variants(use["name"]):
                rows.append(
                    (
                        words(v),
                        v,
                        int(sid),
                        leaf.get(int(sid)),
                        "use",
                        use["direction"],
                    )
                )
    for table in ("names", "names_tri"):
        db.executemany(
            f"INSERT INTO {table} VALUES (?, ?, ?, ?, ?, ?)",
            [r for r in rows if r[0]],
        )
    db.commit()
    return db


def tree_leaves(conn, name: str, page_of: dict[int, int | None]) -> set[int]:
    """The non-test leaves whose raw sources hold a name anywhere in the
    tree: how rare it really is, not just inside the slice."""
    # passages_fts splits on "_" and "." but keeps camelCase whole, so try
    # the name as written and as words; the larger count wins
    forms = {
        '"' + " ".join(re.findall(r"[A-Za-z0-9]+", name)).lower() + '"',
        '"' + words(name) + '"',
    }
    best: set[int] = set()
    for q in forms:
        if q == '""':
            continue
        hits = conn.execute(
            "SELECT passage_id FROM passages_fts WHERE passages_fts MATCH ? LIMIT 5000",
            (q,),
        ).fetchall()
        got = {page_of[p] for (p,) in hits if page_of.get(p) is not None}
        if len(got) > len(best):
            best = got
    return best


def passage_pages(conn) -> dict[int, int | None]:
    leaf = leaf_map(conn)
    out: dict[int, int | None] = {}
    for pid, path, kind, sid in conn.execute(
        "SELECT id, path, source_type, section_id FROM passages"
    ):
        out[pid] = (
            None if kind == "node" or is_test(path or "") else leaf.get(sid)
        )
    return out


MAX_LEAVES = 3  # a name on more leaves than this is common, not a link
MAX_TREE = 15  # nor one the whole tree's sources hold on more leaves


def find(db, table: str, text: str) -> list[tuple]:
    if table == "names":
        q = '"' + text + '"'
    else:
        if len(text) < 3:
            return []
        q = '"' + text.replace('"', "") + '"'
    try:
        return db.execute(
            f"SELECT raw, section, leaf, kind, direction FROM {table} "
            f"WHERE {table} MATCH ?",
            (q,),
        ).fetchall()
    except sqlite3.OperationalError:
        return []


def counterparts(rows: list[tuple], own: int, direction: str) -> list[tuple]:
    """Of the sections that hold the same name, the ones at the other end:
    a definition, or a receiver of what this sends (and the reverse). Two
    senders of one name are co-callers and do not link."""
    out = []
    for raw, section, leaf, kind, theirs in rows:
        if leaf is None or leaf == own:
            continue
        if kind == "def":
            out.append((raw, section, leaf, "def"))
        elif {direction, theirs} == {"sends", "receives"}:
            out.append((raw, section, leaf, theirs))
        elif CHANNEL.search(raw):
            # a topic, subject, queue or service URL ties everyone who
            # touches it: the other publishers and consumers of a channel
            out.append((raw, section, leaf, "shares"))
    return out


CHANNEL = re.compile(
    r"TOPIC|SUBJECT|QUEUE|_URL\b|SVC|/api/|bc\.registry|subscription", re.I
)


def match_all(
    conn, condensed: dict[str, dict]
) -> tuple[list[dict], list[dict]]:
    db = build_index(conn, condensed)
    leaf = leaf_map(conn)
    pages = passage_pages(conn)
    rare_cache: dict[str, int] = {}
    links, misses = [], []
    for sid, got in condensed.items():
        if is_test(got["path"]):
            continue
        own = leaf.get(int(sid))
        if own is None:
            continue
        for use in got["structured"].get("uses", []):
            for name in variants(use["name"]):
                found, how = match_one(db, name, own, use["direction"])
                if not found:
                    if specific(name):
                        misses.append(
                            {
                                "section": int(sid),
                                "own": own,
                                **use,
                                "name": name,
                            }
                        )
                    continue
                text = words(name)
                if text not in rare_cache:
                    rare_cache[text] = len(tree_leaves(conn, name, pages))
                if rare_cache[text] > MAX_TREE:
                    continue
                for raw, section, to, kind in found:
                    links.append(
                        {
                            "from_section": int(sid),
                            "from_leaf": own,
                            "to_section": section,
                            "to_leaf": to,
                            "name": name,
                            "matched": raw,
                            "how": how,
                            "kind": kind,
                            "direction": use["direction"],
                            "what": use["what"],
                            "tree_leaves": rare_cache[text],
                        }
                    )
    return links, misses


MAX_SHARED = 6  # a channel may tie a few more parts than a definition


def match_one(db, name: str, own: int, direction: str) -> tuple[list, str]:
    text = words(name)
    if not text or not specific(name):
        return [], ""
    how = "porter"
    found = [
        f
        for f in counterparts(find(db, "names", text), own, direction)
        if same_name(name, f[0])
    ]
    if not found:
        how = "trigram"
        found = [
            f
            for f in counterparts(find(db, "names_tri", text), own, direction)
            if SequenceMatcher(
                None, " ".join(segments(name)), " ".join(segments(f[0]))
            ).ratio()
            >= 0.9
        ]
    direct = [f for f in found if f[3] != "shares"]
    shared = [f for f in found if f[3] == "shares"]
    if len({f[2] for f in direct}) > MAX_LEAVES:
        direct = []
    if len({f[2] for f in shared}) > MAX_SHARED:
        shared = []
    return direct + shared, how


def expand() -> None:
    """Uses the slice cannot resolve, looked up in the whole tree's sources:
    the non-test sections outside the slice that hold a rare name are
    condensed too, as a full build would have them."""
    conn = c.connect()
    slice_secs = set(members(conn, slice_leaves(conn)))
    _, misses = match_all(conn, all_condensed())
    leaf = leaf_map(conn)
    pages = passage_pages(conn)
    want: dict[int, str] = {}
    for miss in misses:
        if not specific(miss["name"]):
            continue
        q = '"' + words(miss["name"]) + '"'
        hits = conn.execute(
            "SELECT p.section_id, p.path FROM passages_fts f JOIN passages p "
            "ON p.id = f.passage_id WHERE passages_fts MATCH ? LIMIT 200",
            (q,),
        ).fetchall()
        secs = {
            s
            for s, path in hits
            if s is not None
            and s not in slice_secs
            and not is_test(path)
            and leaf.get(s) != miss["own"]
        }
        if (
            not secs
            or len(secs) > 4
            or len({leaf.get(s) for s in secs}) > MAX_LEAVES
        ):
            continue
        for s in secs:
            want.setdefault(s, miss["name"])
    _ = pages
    save("expand.json", {str(k): v for k, v in sorted(want.items())})
    print("misses", len(misses), "sections to add", len(want))


def condense_expand() -> None:
    sids = [int(s) for s in load("expand.json")]
    _condense(sids, "condensed-expand.json")


def link() -> None:
    conn = c.connect()
    links, misses = match_all(conn, all_condensed())
    save("links.json", links)
    save("misses.json", misses)
    title = sl.titles(conn)
    slice_set = set(slice_leaves(conn))
    by_how: dict[str, int] = {}
    for item in links:
        by_how[item["how"]] = by_how.get(item["how"], 0) + 1
    pairs = {(i["from_leaf"], i["to_leaf"]) for i in links}
    print(
        "links",
        len(links),
        by_how,
        "leaf pairs",
        len(pairs),
        "unresolved uses",
        len(misses),
    )
    lines = []
    for item in sorted(links, key=lambda i: (i["from_leaf"], i["name"])):
        lines.append(
            f"{item['from_leaf']}{'*' if item['from_leaf'] in slice_set else ''} -> "
            f"{item['to_leaf']}{'*' if item['to_leaf'] in slice_set else ''} "
            f"[{item['direction']}->{item['kind']} {item['how']} tree:{item['tree_leaves']}] "
            f"{item['name']!r} = {item['matched']!r} | "
            f"{title.get(item['to_leaf'], '?')[:50]}"
        )
    (DATA / "links.txt").write_text("\n".join(lines) + "\n")


# --- briefs ------------------------------------------------------------------

CHECKS = sl.CHECKS

CONNECT = (
    "\n7. Its connections, from the CONNECTED ELSEWHERE block: notes on "
    "sources in other parts of the system that this part uses or that use "
    "it. They are not part of this part. For each connection that matters, "
    "one line: the other part and its source, what crosses and in which "
    "direction, and the condition each side checks - or that the notes show "
    "none. Where the two sides together support a conclusion, state it (for "
    "example which credential the receiving side therefore sees, or a case "
    "one side sends that the other does not handle). Describe the other part "
    "only as far as the connection needs."
)

RATE = (
    "Return the description in markdown as `brief`. Then, in `linked`, rate "
    "each source of the CONNECTED ELSEWHERE block by its label ([L1], [L2], "
    "...): `used` true if it shaped what you wrote about a connection, false "
    "if it only shares a name with this part and does not matter to it; "
    "`why` in a few words."
)
RATED = {
    "type": "object",
    "properties": {
        "brief": {"type": "string"},
        "linked": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "used": {"type": "boolean"},
                    "why": {"type": "string"},
                },
                "required": ["label", "used", "why"],
            },
        },
    },
    "required": ["brief", "linked"],
}

WORDS = 220  # of a linked section's notes shown in a block
LINKED = 12  # linked sections at most per leaf


def brief_template(conn, variant: str) -> str:
    template = json.loads(
        conn.execute(
            "SELECT config FROM registry WHERE collection = 'prompts' AND name = 'brief'"
        ).fetchone()[0]
    )["template"]
    template = template.replace(
        "\n\nOutput only the description",
        CHECKS + "\n\nOutput only the description",
        1,
    )
    if variant in ("B", "BL"):
        template = template.replace(
            "\n\nLeave out:", CONNECT + "\n\nLeave out:", 1
        )
    if variant == "BL":
        template = template.replace(
            "Output only the description in markdown, nothing else.",
            RATE,
            1,
        )
        assert RATE in template
    assert CHECKS in template
    return template


def clip(text: str, n: int = WORDS) -> str:
    w = text.split()
    return text if len(w) <= n else " ".join(w[:n]) + " …"


def linked_block(
    node: int,
    links: list[dict],
    condensed: dict,
    title: dict,
    conn,
    notes=None,
    labels: bool = False,
) -> str:
    """The notes of sections in other leaves this leaf is linked to, either
    way, rarest name first."""
    seen: dict[int, tuple] = {}

    def area(sid: int) -> str:
        got = condensed.get(str(sid))
        return "/".join((got["path"] if got else "").split("/")[:2])

    def order(item: dict) -> tuple:
        # links into another area of the corpus first, then rarer names
        return (
            area(item["from_section"]) == area(item["to_section"]),
            item["tree_leaves"],
        )

    for item in sorted(links, key=order):
        if item["from_leaf"] == node:
            other, other_leaf, how = (
                item["to_section"],
                item["to_leaf"],
                f"this part {item['direction']} `{item['name']}`"
                f" ({'defined there' if item['kind'] == 'def' else item['kind'] + ' there'}): {item['what']}",
            )
        elif item["to_leaf"] == node:
            other, other_leaf, how = (
                item["from_section"],
                item["from_leaf"],
                f"it {item['direction']} `{item['name']}` here: {item['what']}",
            )
        else:
            continue
        if other not in seen:
            seen[other] = (other_leaf, how)
        if len(seen) >= LINKED:
            break
    blocks = []
    for n, (sid, (other_leaf, how)) in enumerate(seen.items(), 1):
        got = condensed.get(str(sid))
        text = (
            notes(sid)
            if notes
            else got["structured"]["condensed"]
            if got
            else stored_condensation(conn, sid)
        )
        path = got["path"] if got else "?"
        label = f"[L{n}] " if labels else ""
        blocks.append(
            f'--- {label}{path}, in "{title.get(other_leaf, "?")[:80]}"\n'
            f"Link: {how}\n{clip(text)}"
        )
    return "\n\n".join(blocks)


def brief(variant: str) -> None:
    sys.path.insert(0, str(HERE.parents[3] / "src"))
    from hrono.summarize.briefs import labeled

    conn = c.connect()
    template = brief_template(conn, variant)
    condensed = all_condensed()
    links = load("links.json") if variant in ("B", "BL") else []
    ledger = load("ledger.json") if variant == "BL" else {}
    title = sl.titles(conn)
    out_name = f"briefs-{variant}.json"
    out = load(out_name)

    def one(node: int) -> tuple[str, dict]:
        conn2 = c.connect()
        rows = conn2.execute(
            "SELECT s.id, s.path FROM node_members m JOIN sections s ON s.id = m.section_id "
            "WHERE m.node_id = ? ORDER BY s.uri, s.id",
            (node,),
        ).fetchall()

        def notes(sid: int) -> str:
            if ledger:
                if str(sid) in ledger:
                    return ledger[str(sid)]["text"]
                return stored_condensation(conn2, sid)
            got = condensed.get(str(sid))
            return (
                got["structured"]["condensed"]
                if got
                else stored_condensation(conn2, sid)
            )

        pairs = [(path, notes(sid)) for sid, path in rows]
        content = labeled(pairs)
        block = ""
        if variant in ("B", "BL"):
            block = linked_block(
                node,
                links,
                condensed,
                title,
                conn2,
                notes if ledger else None,
                variant == "BL",
            )
            if block:
                content += (
                    "\n\n=== CONNECTED ELSEWHERE (not part of this part) ===\n"
                    + block
                )
        if variant == "BL":
            got = ask(template.replace("{content}", content), SONNET, RATED)
            rated = got.get("structured") or {}
            got["text"] = rated.get("brief")
            got["linked"] = rated.get("linked")
        else:
            got = ask(template.replace("{content}", content), SONNET)
        return str(node), {**got, "block": block}

    todo = [n for n in slice_leaves(conn) if str(n) not in out]
    for node, got in run_pool(one, todo, 4):
        out[node] = got
        save(out_name, out)
    print(
        out_name,
        len(out),
        "errors",
        sum("error" in v for v in out.values()),
        "cost",
        round(sum(v.get("cost") or 0 for v in out.values()), 2),
    )


# --- parents -----------------------------------------------------------------

UPPER_LINKS = (
    "\n\nAfter the parts comes a LINKS block, computed from the sources: "
    "each line says that one part uses a name another part defines or "
    "receives, inside this area or in another one. Use it to tell the flows "
    "that cross parts: as numbered steps across the parts, keeping at each "
    "hand-off what crosses and the condition each side checks, as the part "
    "descriptions give it. Name a part in another area by its title and say "
    "it is outside this area. Never state a check without its condition."
)


def parents_of(conn, nodes: list[int]) -> dict[int, int]:
    marks = ",".join("?" * len(nodes))
    return dict(
        conn.execute(
            f"SELECT child_id, parent_id FROM node_children WHERE child_id IN ({marks})",
            nodes,
        )
    )


def upper() -> None:
    conn = c.connect()
    template = json.loads(
        conn.execute(
            "SELECT config FROM registry WHERE collection = 'prompts' AND name = 'brief-upper'"
        ).fetchone()[0]
    )["template"]
    template = template.replace(
        " Output only the description",
        UPPER_LINKS + " Output only the description",
        1,
    )
    assert UPPER_LINKS in template
    title = sl.titles(conn)
    stored = dict(conn.execute("SELECT node_id, text FROM briefs"))
    new = {
        int(k): v["text"]
        for k, v in load("briefs-B.json").items()
        if v.get("text")
    }
    links = load("links.json")
    leaves = slice_leaves(conn)
    parent = {
        child: p
        for child, p in conn.execute(
            "SELECT child_id, parent_id FROM node_children"
        )
    }
    targets = sorted({parent[n] for n in leaves})
    out = load("upper-C.json")

    def one(p: int) -> tuple[str, dict]:
        conn2 = c.connect()
        kids = [
            r[0]
            for r in conn2.execute(
                "SELECT child_id FROM node_children WHERE parent_id = ? ORDER BY child_id",
                (p,),
            )
        ]
        parts = [
            f"=== {title.get(k, '?')} ===\n{new.get(k) or stored.get(k, '')}"
            for k in kids
        ]
        kidset = set(kids)
        lines = []
        for item in links:
            a, b = item["from_leaf"], item["to_leaf"]
            if a not in kidset and b not in kidset:
                continue
            where_a = "" if a in kidset else " (other area)"
            where_b = "" if b in kidset else " (other area)"
            verb = {
                "def": "uses",
                "receives": "sends to",
                "sends": "receives from",
                "shares": "shares a channel with",
            }[item["kind"]]
            lines.append(
                f'- "{title.get(a, "?")[:70]}"{where_a} {verb} "{title.get(b, "?")[:70]}"{where_b} via `{item["name"]}`: {clip(item["what"], 40)}'
            )
        lines = list(dict.fromkeys(lines))[:80]
        content = "\n\n".join(parts) + "\n\n=== LINKS ===\n" + "\n".join(lines)
        got = ask(template.replace("{content}", content), SONNET)
        return str(p), {**got, "links": len(lines)}

    todo = [p for p in targets if str(p) not in out]
    for p, got in run_pool(one, todo, 4):
        out[p] = got
        save("upper-C.json", out)
    print(
        "parents",
        len(out),
        "cost",
        round(sum(v.get("cost") or 0 for v in out.values()), 2),
    )


# --- claims and judge --------------------------------------------------------

SPLIT = """Split each fact below into short claims a reader can check one at a time against a document: yes, the document states it, or no. One claim per condition, outcome, name or link; keep names verbatim; no claim that only repeats another. Tag each claim:
- "local": about one component on its own (what it does, checks, stores, names)
- "connection": about how two or more components relate, or a conclusion that needs both (who calls or consumes what, whose token arrives, which side checks, what one sends that the other mishandles)

QUESTION:
{question}

FACTS:
{facts}"""

CLAIMS = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "fact": {"type": "integer"},
                    "claims": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "kind": {"enum": ["local", "connection"]},
                            },
                            "required": ["claim", "kind"],
                        },
                    },
                },
                "required": ["fact", "claims"],
            },
        }
    },
    "required": ["facts"],
}


def claims() -> None:
    qs = sl.questions()

    def one(q: dict) -> tuple[str, dict]:
        facts = "\n".join(f"{i}. {f['fact']}" for i, f in enumerate(q["facts"]))
        got = ask(
            SPLIT.format(question=q["question"], facts=facts), SONNET, CLAIMS
        )
        return q["qid"], got

    out = {}
    for qid, got in run_pool(one, qs, 3):
        out[qid] = got
    save("claims.json", out)
    for qid, got in out.items():
        rows = [cl for f in got["structured"]["facts"] for cl in f["claims"]]
        print(
            qid,
            len(rows),
            "connection",
            sum(r["kind"] == "connection" for r in rows),
        )


JUDGE = """You check whether a map of a software system states some claims. Judge each claim on its own: "yes" only if the pages state it - same meaning, names may differ slightly; "no" if they do not state it, state only part of it, or only make it guessable. A claim the pages contradict is "no". For each "yes" quote the words that state it.

CLAIMS:
{claims}

MAP PAGES:
{pages}"""

VERDICTS = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "integer"},
                    "stated": {"type": "boolean"},
                    "quote": {"type": "string"},
                },
                "required": ["claim", "stated", "quote"],
            },
        }
    },
    "required": ["verdicts"],
}


def arm_pages(conn) -> dict[str, dict[int, str]]:
    """Each arm's text for every node it may show: leaves, and the parents
    of the slice's leaves (stored ones except in arm C)."""
    stored = dict(conn.execute("SELECT node_id, text FROM briefs"))

    def texts(name: str) -> dict[int, str]:
        return {
            int(k): v["text"] for k, v in load(name).items() if v.get("text")
        }

    old = json.loads((sl.DIR / "briefs2.json").read_text())
    v3x = {int(k): v["text"] for k, v in old.items() if v.get("text")}
    b0, b, up = (
        texts("briefs-B0.json"),
        texts("briefs-B.json"),
        texts("upper-C.json"),
    )
    return {
        "A-v3": stored,
        "A-v3x": {**stored, **v3x},
        "B0": {**stored, **b0},
        "B": {**stored, **b},
        "C": {**stored, **b, **up},
        "BL": {**stored, **texts("briefs-BL.json")},
        "W": {**stored, **texts("briefs-W.json")},
        "I": {**stored, **texts("briefs-W.json"), **texts("briefs-I.json")},
    }


def judge(run: str) -> None:
    conn = c.connect()
    leaf = leaf_map(conn)
    parent = dict(conn.execute("SELECT child_id, parent_id FROM node_children"))
    secs: dict[str, list[int]] = {}
    for sid, source, path in conn.execute(
        "SELECT id, source, path FROM sections"
    ):
        secs.setdefault(f"{source}/{path}", []).append(sid)
    arms = arm_pages(conn)
    split = load("claims.json")
    jobs = []
    for q in sl.questions():
        for f in split[q["qid"]]["structured"]["facts"]:
            fact = q["facts"][f["fact"]]
            leaves = sorted(
                {
                    leaf[s]
                    for p in fact["files"]
                    for s in secs.get(p, [])
                    if s in leaf
                }
            )
            nodes = leaves + sorted({parent[n] for n in leaves if n in parent})
            listing = "\n".join(
                f"{i}. {cl['claim']}" for i, cl in enumerate(f["claims"])
            )
            for arm, texts in arms.items():
                pages = "\n\n".join(
                    f"--- page ---\n{texts.get(n, '')}" for n in nodes
                )
                jobs.append(
                    (
                        q["qid"],
                        f["fact"],
                        arm,
                        JUDGE.format(claims=listing, pages=pages),
                    )
                )
            # the ceiling: the new condensations of the fact's own files
            notes = []
            cond = all_condensed()
            for p in fact["files"]:
                for s in secs.get(p, []):
                    got = cond.get(str(s))
                    text = (
                        got["structured"]["condensed"]
                        if got
                        else stored_condensation(conn, s)
                    )
                    notes.append(f"--- {p} ---\n{text}")
            jobs.append(
                (
                    q["qid"],
                    f["fact"],
                    "notes",
                    JUDGE.format(claims=listing, pages="\n\n".join(notes)),
                )
            )

    out_name = f"judged-{run}.json"
    done = {(r["qid"], r["fact"], r["arm"]): r for r in load(out_name) or []}
    todo = [j for j in jobs if (j[0], j[1], j[2]) not in done]

    def one(job):
        qid, fact, arm, prompt = job
        got = ask(prompt, SONNET, VERDICTS)
        return {
            "qid": qid,
            "fact": fact,
            "arm": arm,
            "verdicts": (got.get("structured") or {}).get("verdicts"),
            "error": got.get("error"),
            "cost": got.get("cost"),
        }

    rows = list(done.values())
    for n, row in enumerate(run_pool(one, todo, 8), 1):
        rows.append(row)
        if n % 20 == 0:
            save(out_name, rows)
    save(out_name, rows)
    print(
        out_name, len(rows), "cost", round(sum(r["cost"] or 0 for r in rows), 2)
    )


def report() -> None:
    split = load("claims.json")
    kinds = {
        (qid, f["fact"], i): cl["kind"]
        for qid, got in split.items()
        for f in got["structured"]["facts"]
        for i, cl in enumerate(f["claims"])
    }
    runs = sorted(DATA.glob("judged-*.json"))
    table: dict[str, dict[str, list[float]]] = {}
    for path in runs:
        for r in json.loads(path.read_text()):
            if not r.get("verdicts"):
                continue
            by_kind = {"local": [0, 0], "connection": [0, 0]}
            for v in r["verdicts"]:
                k = kinds.get((r["qid"], r["fact"], v["claim"]))
                if k is None:
                    continue
                by_kind[k][0] += bool(v["stated"])
                by_kind[k][1] += 1
            arm = table.setdefault(r["arm"], {})
            for k, (yes, n) in by_kind.items():
                arm.setdefault(f"{path.stem}:{k}", [0, 0])
                arm[f"{path.stem}:{k}"][0] += yes
                arm[f"{path.stem}:{k}"][1] += n
    for arm, cells in table.items():
        print(
            arm,
            {
                k: f"{y}/{n} = {y / n:.2f}"
                for k, (y, n) in sorted(cells.items())
                if n
            },
        )


if __name__ == "__main__":
    cmd = sys.argv[1]
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    {
        "condense": lambda: condense(int(arg) if arg else None),
        "expand": expand,
        "condense-expand": condense_expand,
        "link": link,
        "brief": lambda: brief(arg),
        "upper": upper,
        "claims": claims,
        "judge": lambda: judge(arg),
        "report": report,
    }[cmd]()
