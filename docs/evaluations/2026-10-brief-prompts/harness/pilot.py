# ruff: noqa: E501 - report tables and SQL read best on one line
"""Brief one leaf with each prompt and compare the results.

The leaf comes from a clustering's `assignment.npz` (the chosen formula of
`../2026-10-cluster-formula/`). Its sections are condensed with the chosen
condense prompt (`purpose-budget`, `../2026-10-condense-prompts/`) by Haiku,
then briefed by Sonnet with every prompt of `prompts.py`. The input is
shaped as hrono's brief op shapes it: condensations under `=== path ===`
headers, consecutive sections of one file merged. Calls are cached by
request, so reruns are free.

Per prompt it reports words, whether the brief opens by describing its
input ("This group ..."), how many lines are about licences, server setup or
environment defaults, and the identifiers hrono's faithfulness check finds
in the brief but not in its input.

Writes `<out>/leaf-<id>/input.md`, `briefs.md` and `table.md`.

Usage: uv run python pilot.py DB ASSIGNMENT LEAF OUT CACHE [PROMPT ...]
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from prompts import BRIEF

from hrono.llm.claude_code import ClaudeCodeClient
from hrono.llm.client import CompletionRequest, Unfinished
from hrono.summarize.faithfulness import faithfulness


def _condense_prompts() -> dict[str, str]:
    """The condense experiment's prompts (a module also named `prompts`)."""
    import importlib.util

    path = (
        Path(__file__).parents[2]
        / "2026-10-condense-prompts/harness/prompts.py"
    )
    spec = importlib.util.spec_from_file_location("condense_prompts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PROMPTS


CONDENSE = _condense_prompts()

CONDENSE_PROMPT = os.environ.get("CONDENSE_PROMPT", "purpose-budget")
CONDENSE_MODEL = {"model": "haiku"}
BRIEF_MODEL = {"model": "sonnet"}
META = re.compile(
    r"^\W*(this (group|set|batch|collection|is)|these\b|here is|the following)",
    re.I,
)
BOILERPLATE = re.compile(
    r"licen[cs]e|copyright|gunicorn|wsgi|sentry|dotenv|\.env\b|dockerfile|"
    r"makefile|setup\.py|requirements",
    re.I,
)


class Models:
    def __init__(self, cache_path: Path) -> None:
        self._path = cache_path
        self.cache = (
            json.loads(cache_path.read_text()) if cache_path.exists() else {}
        )
        self._client = ClaudeCodeClient(cache_path.parent / "claude-workdir")
        self.calls = 0
        self._lock = threading.Lock()

    def ask(self, model: dict, rendered: str) -> str:
        key = hashlib.sha256(
            f"{model['model']}\n{rendered}".encode()
        ).hexdigest()
        if key not in self.cache:
            request = CompletionRequest(
                model=model, system="", content=rendered
            )
            try:
                result = self._client.complete(request)
            except Unfinished:
                # The CLI now and then refuses one call; one retry, then the
                # call is skipped (not cached) instead of ending the run.
                try:
                    result = self._client.complete(request)
                except Unfinished as error:
                    print(f"skipped a call: {error}")
                    return "(no output)"
            with self._lock:
                self.cache[key] = result.text
                self.calls += 1
                # Save as it goes: a failed call must not lose paid ones.
                if self.calls % 10 == 0:
                    self._write()
        return self.cache[key]

    def save(self) -> None:
        with self._lock:
            self._write()

    def _write(self) -> None:
        self._path.write_text(json.dumps(self.cache))


def main(db_path, assignment, leaf, out, cache, *names) -> None:
    clustering = np.load(assignment)
    sections = _members(db_path, clustering, int(leaf))
    context = _neighbours(db_path, clustering, int(leaf))
    prompts = {n: BRIEF[n] for n in names} if names else BRIEF
    models = Models(Path(cache))
    condense = CONDENSE[CONDENSE_PROMPT]
    with ThreadPoolExecutor(4) as pool:
        notes = list(
            pool.map(
                lambda s: models.ask(
                    CONDENSE_MODEL,
                    condense.replace(
                        "{content}", f"File: {s['path']}\n\n{s['body']}"
                    ),
                ),
                sections,
            )
        )
        models.save()
        source = _labeled(
            (s["path"], n) for s, n in zip(sections, notes, strict=True)
        )
        briefs = dict(
            zip(
                prompts,
                pool.map(
                    lambda t: models.ask(
                        BRIEF_MODEL,
                        t.replace("{context}", context).replace(
                            "{content}", source
                        ),
                    ),
                    prompts.values(),
                ),
                strict=True,
            )
        )
    models.save()
    print(f"{models.calls} new model calls")

    out_dir = Path(out) / f"leaf-{leaf}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "input.md").write_text(source + "\n")
    (out_dir / "context.md").write_text(context + "\n")
    briefs = _merge_briefs(out_dir, briefs)
    (out_dir / "prompts.json").write_text(json.dumps(list(briefs)))
    (out_dir / "briefs.md").write_text(
        "\n".join(
            f"# {name}\n\n{text.strip()}\n" for name, text in briefs.items()
        )
    )
    table = _table(
        briefs, source, len(sections), len({s["path"] for s in sections})
    )
    (out_dir / "table.md").write_text(table)
    print(table)


def _members(db_path: str, assignment, leaf: int) -> list[dict]:
    ids = [
        int(i)
        for i, member_leaf in zip(
            assignment["section_id"], assignment["leaf"], strict=True
        )
        if member_leaf == leaf
    ]
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    marks = ",".join("?" * len(ids))
    return [
        {
            "source": source,
            "path": path,
            "body": body.decode("utf-8", "replace"),
        }
        for source, path, body in conn.execute(
            f"SELECT s.source, s.path, c.body FROM sections s JOIN contents c "
            f"USING (content_hash) WHERE s.id IN ({marks}) ORDER BY s.uri, s.id",
            ids,
        )
    ]


def _neighbours(db_path: str, clustering, leaf: int) -> str:
    """The other leaves of this leaf's group, each as its sources' folder and
    up to four file names: what a brief op can know before any brief exists.
    """
    group = int(clustering["group"][list(clustering["leaf"]).index(leaf)])
    lines = []
    for other in sorted(
        {
            int(other)
            for other, g in zip(
                clustering["leaf"], clustering["group"], strict=True
            )
            if g == group
        }
        - {leaf}
    ):
        paths = sorted(
            {
                f"{s['source']}/{s['path']}"
                for s in _members(db_path, clustering, other)
            }
        )
        prefix = (
            os.path.commonpath(paths)
            if len(paths) > 1
            else os.path.dirname(paths[0])
        )
        names = ", ".join(os.path.relpath(p, prefix) for p in paths[:4])
        more = f" and {len(paths) - 4} more" if len(paths) > 4 else ""
        lines.append(f"- {prefix}/: {names}{more}")
    return "\n".join(lines)


def _merge_briefs(out_dir: Path, briefs: dict) -> dict:
    """Keep earlier prompts' briefs in `briefs.md`, so runs add prompts."""
    if not (out_dir / "prompts.json").exists():
        return briefs
    from judge import _read_briefs

    return {**_read_briefs(out_dir / "briefs.md"), **briefs}


def _labeled(pairs) -> str:
    """hrono's brief input: texts under `=== label ===`, runs merged."""
    blocks, current = [], None
    for label, text in pairs:
        if label != current:
            blocks.append(f"=== {label} ===")
            current = label
        blocks.append(text)
    return "\n\n".join(blocks)


def _table(briefs: dict, source: str, sections: int, files: int) -> str:
    lines = [
        f"{sections} sections in {files} files; input {len(source.split())} words.\n",
        "| prompt | words | opens by describing its input | boilerplate lines | unsupported names |",
        "|---|---|---|---|---|",
    ]
    for name, text in briefs.items():
        body = [line for line in text.splitlines() if line.strip()]
        opening = " ".join(text.split())[:80]
        unsupported = faithfulness(text, source)
        lines.append(
            f"| `{name}` | {len(text.split())} | "
            f"{'yes' if META.search(opening) else 'no'} | "
            f"{sum(1 for line in body if BOILERPLATE.search(line))} | "
            f"{len(unsupported)}: {', '.join(unsupported[:6])} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main(*sys.argv[1:])
