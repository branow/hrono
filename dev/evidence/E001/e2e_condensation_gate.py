"""E001 T2a: the condensation gate, end to end over a real ``hrono serve``.

Fresh scratch home with its own generated master key; a small git corpus; a
local openai-compatible stub (``stub_llm.py``) as the only provider. Builds a
tree, plants 4 talking-back condensations, then over HTTP:

1. ``GET /trees/default/unusable-condensations`` lists exactly those 4;
2. one ``POST /trees/default/sync`` re-condenses exactly those 4 and rewrites
   exactly the briefs above them — every other condensation and brief is
   byte-identical.

Run from the epic worktree:  uv run python <this file> <scratch dir> <out dir>
Writes transcript.md and node-diff.json to <out dir>; exits non-zero on any
failed check.
"""

from __future__ import annotations

import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
TREE = "default"
PLANTED = "Could you paste the file you would like me to condense for you?"
TOPICS = {
    "billing": "invoice payment charge refund currency ledger tax receipt",
    "search": "query index token ranking score document retrieval inverted",
    "network": "socket packet retry timeout connection handshake latency",
    "storage": "disk block volume snapshot replica checksum compaction",
    "render": "pixel shader texture frame canvas sprite raster",
    "audit": "event trail actor permission policy evidence retention",
}

log: list[str] = []
CHILDREN: list[subprocess.Popen] = []


def say(line: str = "") -> None:
    print(line, flush=True)
    log.append(line)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def make_corpus(root: Path) -> None:
    root.mkdir(parents=True)
    for topic, words in TOPICS.items():
        vocab = words.split()
        for i in range(8):
            lines = [f'"""The {topic} module {i}: {words}."""', ""]
            for j in range(6):
                a, b = vocab[(i + j) % len(vocab)], vocab[(i + 2 * j) % len(vocab)]
                lines += [
                    f"def {a}_{b}_{j}(value):",
                    f'    """Handle the {a} and the {b} for {topic}."""',
                    f"    return value  # {a} {b} {topic} step {i} {j}",
                    "",
                ]
            path = root / topic / f"{topic}_{i}.py"
            path.parent.mkdir(exist_ok=True)
            path.write_text("\n".join(lines))
    git = ["git", "-C", str(root)]
    subprocess.run([*git, "init", "-q", "-b", "main"], check=True)
    subprocess.run([*git, "add", "."], check=True)
    subprocess.run(
        [*git, "-c", "user.name=e2e", "-c", "user.email=e2e@local",
         "commit", "-qm", "corpus"],
        check=True,
    )


def start_server(db: Path, key: Path, port: int, out: Path) -> subprocess.Popen:
    handle = open(out, "a")  # noqa: SIM115 - lives as long as the process
    proc = subprocess.Popen(
        ["uv", "run", "hrono", "serve", "--port", str(port), "--db", str(db),
         "--key-file", str(key)],
        stdout=handle,
        stderr=subprocess.STDOUT,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    CHILDREN.append(proc)
    for _ in range(120):
        try:
            if httpx.get(f"http://127.0.0.1:{port}/health").status_code < 500:
                return proc
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    raise SystemExit("hrono serve did not come up; see " + str(out))


def stop(proc: subprocess.Popen) -> None:
    proc.terminate()
    proc.wait(timeout=30)


class Api:
    def __init__(self, base: str, token: str) -> None:
        self.http = httpx.Client(
            base_url=base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=120,
        )

    def call(self, method: str, path: str, body: object = None) -> object:
        response = self.http.request(method, path, json=body)
        say(f"\n```\n{method} {path}")
        if body is not None:
            say(json.dumps(body, indent=2))
        say(f"-> {response.status_code}")
        try:
            data = response.json()
        except ValueError:
            data = response.text
        say(json.dumps(data, indent=2)[:6000])
        say("```")
        if response.status_code >= 400:
            raise SystemExit(f"{method} {path} failed: {response.status_code}")
        return data

    def wait(self, job_id: str) -> dict:
        while True:
            job = self.http.get(f"/jobs/{job_id}").json()
            if job["status"] in ("succeeded", "failed", "canceled"):
                return self.call("GET", f"/jobs/{job_id}")  # type: ignore
            time.sleep(1)


def snapshot(db: Path) -> dict[str, dict]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cond = dict(conn.execute("SELECT content_hash, text FROM condensations"))
        briefs = {
            str(node): text
            for node, text in conn.execute(
                "SELECT b.node_id, b.text FROM briefs b "
                "JOIN nodes n ON n.id = b.node_id WHERE n.tree = ?",
                (TREE,),
            )
        }
    finally:
        conn.close()
    return {"condensations": cond, "briefs": briefs}


def readers(db: Path, digests: list[str]) -> list[str]:
    """Every node holding a section with one of ``digests``, and its ancestors."""
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "WITH RECURSIVE up(id) AS ("
            "SELECT m.node_id FROM node_members m JOIN sections s "
            "ON s.id = m.section_id WHERE s.content_hash IN "
            "(SELECT value FROM json_each(?)) "
            "UNION SELECT c.parent_id FROM node_children c "
            "JOIN up ON c.child_id = up.id) "
            "SELECT up.id FROM up JOIN briefs b ON b.node_id = up.id",
            (json.dumps(digests),),
        ).fetchall()
    finally:
        conn.close()
    return sorted(str(r[0]) for r in rows)


def plant(db: Path) -> list[str]:
    """Overwrite 4 single-path condensations in 2 topics with talk-back text.

    The server is stopped while this writes: it is the single writer, and the
    plant stands in for condensations a past run stored before the gate.
    """
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            "SELECT m.node_id, s.content_hash FROM sections s "
            "JOIN node_members m ON m.section_id = s.id "
            "JOIN nodes n ON n.id = m.node_id AND n.tree = ? "
            "JOIN condensations c ON c.content_hash = s.content_hash "
            "WHERE s.content_hash IN (SELECT content_hash FROM sections "
            "GROUP BY content_hash HAVING COUNT(DISTINCT path) = 1) "
            "ORDER BY m.node_id, s.content_hash",
            (TREE,),
        ).fetchall()
        by_leaf: dict[int, list[str]] = {}
        for node, digest in rows:
            by_leaf.setdefault(node, []).append(digest)
        # two from each of two topics: the other topics are the control group
        leaves = sorted(by_leaf)[:2]
        chosen = [d for leaf in leaves for d in by_leaf[leaf][:2]]
        conn.executemany(
            "UPDATE condensations SET text = ? WHERE content_hash = ?",
            [(PLANTED, d) for d in chosen],
        )
        conn.commit()
    finally:
        conn.close()
    return chosen


def diff(before: dict, after: dict) -> dict[str, list[str]]:
    keys = before.keys() | after.keys()
    return {
        "changed": sorted(k for k in keys if k in before and k in after
                          and before[k] != after[k]),
        "added": sorted(after.keys() - before.keys()),
        "removed": sorted(before.keys() - after.keys()),
        "identical": sorted(k for k in keys if before.get(k) == after.get(k)),
    }


def main() -> int:
    scratch, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    if scratch.exists():
        raise SystemExit(f"{scratch} exists; give a fresh scratch dir")
    home, corpus = scratch / "home", scratch / "corpus"
    home.mkdir(parents=True)
    db, key = home / "hrono.db", home / "master.key"
    make_corpus(corpus)
    subprocess.run(
        ["uv", "run", "hrono", "admin", "new-key", "--out", str(key)],
        check=True,
        capture_output=True,
    )
    stub_port, port = free_port(), free_port()
    calls = scratch / "stub-calls.jsonl"
    stub = subprocess.Popen(
        [sys.executable, str(HERE / "stub_llm.py"), str(stub_port), str(calls)]
    )
    CHILDREN.append(stub)
    serve_log = scratch / "serve.log"
    checks: list[tuple[str, bool]] = []
    server = start_server(db, key, port, serve_log)
    try:
        token = re.search(r"token:\s*(\S+)", serve_log.read_text()).group(1)
        api = Api(f"http://127.0.0.1:{port}", token)
        say("# E001 T2a: the condensation gate over a real `hrono serve`")
        say(f"\nScratch home `{home}`, its own key from `hrono admin new-key`;"
            f" provider: local openai-compatible stub on :{stub_port}.")
        say("\n## Setup and cold build")
        endpoint = f"http://127.0.0.1:{stub_port}/v1"
        api.call("POST", "/connections", {
            "name": "stub", "provider": "openai-compatible",
            "endpoint": endpoint, "auth": {"method": "none"}})
        api.call("POST", "/models", {
            "name": "stub-embed", "kind": "embedding", "connection": "stub",
            "model": "bow-64", "params": {"dims": 64}})
        api.call("POST", "/models", {
            "name": "stub-text", "kind": "text", "connection": "stub",
            "model": "stub-1"})
        api.call("POST", "/sources", {
            "name": "corpus", "type": "git", "url": str(corpus),
            "auth": {"method": "none"}})
        api.call("POST", "/trees", {"name": TREE, "sources": ["corpus"]})
        job = api.call("POST", f"/trees/{TREE}/maintain")
        built = api.wait(job["job_id"])  # type: ignore[index]
        if built["status"] not in ("succeeded",):
            raise SystemExit("maintain failed")
        api.call("GET", f"/trees/{TREE}/unusable-condensations")
    finally:
        stop(server)

    planted = plant(db)
    say("\n## Plant")
    say(f"\nServer stopped; 4 condensations overwritten with `{PLANTED}`:")
    for digest in planted:
        say(f"- `{digest}`")
    expected_briefs = readers(db, planted)
    say(f"\nBriefs that read them (their topics and every ancestor): "
        f"{expected_briefs}")
    before = snapshot(db)

    server = start_server(db, key, port, serve_log)
    try:
        say("\n## List, then one sync")
        listed = api.call("GET", f"/trees/{TREE}/unusable-condensations")
        got = sorted(c["content_hash"] for c in listed["condensations"])
        checks.append(("list shows exactly the 4 planted",
                       listed["count"] == 4 and got == sorted(planted)))
        calls_before = calls.read_text().count("\n")
        job = api.call("POST", f"/trees/{TREE}/sync")
        synced = api.wait(job["job_id"])  # type: ignore[index]
        checks.append(("sync succeeded",
                       synced["status"] in ("succeeded",)))
        after_list = api.call("GET", f"/trees/{TREE}/unusable-condensations")
        checks.append(("list is empty after the sync",
                       after_list["count"] == 0))
        api.call("GET", f"/trees/{TREE}/unusable-briefs")
    finally:
        stop(server)
        stub.terminate()

    after = snapshot(db)
    cond = diff(before["condensations"], after["condensations"])
    brief = diff(before["briefs"], after["briefs"])
    sync_calls = calls.read_text().splitlines()[calls_before:]
    checks += [
        ("re-condensed exactly the 4 planted",
         cond["changed"] == sorted(planted)
         and not cond["added"] and not cond["removed"]),
        ("no re-condensation is talk-back",
         all(after["condensations"][d] != PLANTED for d in planted)),
        ("rewrote exactly the briefs above them",
         brief["changed"] == expected_briefs
         and not brief["added"] and not brief["removed"]),
        ("the sync made one call per re-condensation and rewritten brief",
         len(sync_calls) == len(planted) + len(expected_briefs)),
    ]
    node_diff = {
        "planted_content_hashes": sorted(planted),
        "expected_briefs_node_ids": expected_briefs,
        "condensations": {k: v for k, v in cond.items() if k != "identical"}
        | {"identical_count": len(cond["identical"])},
        "briefs": {k: v for k, v in brief.items() if k != "identical"}
        | {"identical_node_ids": brief["identical"]},
        "brief_text": {
            node: {"before": before["briefs"][node],
                   "after": after["briefs"][node]}
            for node in brief["changed"]
        },
        "sync_llm_calls": [json.loads(c) for c in sync_calls],
    }
    say("\n## Before/after")
    say(f"\nCondensations: {len(cond['changed'])} changed "
        f"{cond['changed']}, {len(cond['identical'])} byte-identical.")
    say(f"\nBriefs: changed {brief['changed']}, identical "
        f"{brief['identical']}, added {brief['added']}, removed "
        f"{brief['removed']}.")
    say(f"\nLLM calls during the sync: {len(sync_calls)}.")
    say("\n## Checks")
    for name, ok in checks:
        say(f"- [{'x' if ok else ' '}] {name}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "transcript.md").write_text("\n".join(log) + "\n")
    (out / "node-diff.json").write_text(json.dumps(node_diff, indent=2) + "\n")
    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    os.environ.pop("HRONO_MASTER_KEY", None)
    try:
        sys.exit(main())
    finally:
        for child in CHILDREN:
            if child.poll() is None:
                child.terminate()
