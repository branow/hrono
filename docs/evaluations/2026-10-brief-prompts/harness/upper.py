"""Brief one group's leaves with the leaf pick, then the group with each
upper prompt, and score the upper briefs against the architecture facts.

The leaves are the group's leaves in the clustering's `assignment.npz`. Each
is condensed (`CONDENSE_PROMPT`, default `purpose-decisions`) and briefed
with `LEAF_PROMPT` (default `core-states`), as `pilot.py` does. The upper
input is hrono's: the leaf briefs under `=== title ===`, the title being
the brief's first line. Every upper prompt is sampled twice; each sample is
judged twice (`judge.score`) on all facts citing the group's files, and
separately on the facts whose files sit in two or more of its leaves - the
ones only an upper brief can tell. The leaf briefs themselves, joined, are
judged as the ceiling.

Writes `<out>/group-<id>/{input.md, uppers.md, table.md}`.

Usage: uv run python upper.py DB ASSIGNMENT GROUP OUT CACHE [PROMPT ...]
"""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from judge import leaf_facts, noise, score
from pilot import (
    BRIEF_MODEL,
    CONDENSE,
    CONDENSE_MODEL,
    Models,
    _labeled,
    _members,
)
from prompts import BRIEF
from upper_prompts import UPPER

LEAF_PROMPT = os.environ.get("LEAF_PROMPT", "core-states")
CONDENSE_PROMPT = os.environ.get("CONDENSE_PROMPT", "purpose-decisions")
SAMPLES = 2


def main(db_path, assignment, group, out, cache, *names) -> None:
    clustering = np.load(assignment)
    leaves = sorted(
        {
            int(leaf)
            for leaf, g in zip(
                clustering["leaf"], clustering["group"], strict=True
            )
            if g == int(group)
        }
    )
    models = Models(Path(cache))
    with ThreadPoolExecutor(4) as pool:
        briefs = [
            _leaf_brief(models, pool, db_path, clustering, leaf)
            for leaf in leaves
        ]
        models.save()
        print(f"{models.calls} new model calls for {len(leaves)} leaf briefs")
        source = _labeled((_title(b), b) for _, b in briefs)
        prompts = {n: UPPER[n] for n in names} if names else UPPER
        jobs = [(n, k) for n in prompts for k in range(SAMPLES)]
        texts = pool.map(
            lambda job: models.ask(
                BRIEF_MODEL,
                prompts[job[0]].replace("{content}", source) + "\n" * job[1],
            ),
            jobs,
        )
        uppers = dict(zip(jobs, texts, strict=True))
    models.save()

    leaf_files = {
        leaf: {f"{s['source']}/{s['path']}" for s in files}
        for leaf, files in briefs_files(db_path, clustering, leaves).items()
    }
    facts = leaf_facts(set().union(*leaf_files.values()))
    spanning = [
        f
        for f in facts
        if len(
            {
                leaf
                for leaf, fs in leaf_files.items()
                for p in f["here"]
                if p in fs
            }
        )
        > 1
    ]
    rows = {}
    for (name, _), text in uppers.items():
        rows.setdefault(name, []).append(
            (
                len(text.split()),
                score(models, text, facts, 0)["facts"],
                score(models, text, spanning, 0)["facts"],
                noise(models, text),
            )
        )
    rows["(leaf briefs)"] = [
        (
            len(source.split()),
            score(models, source, facts)["facts"],
            score(models, source, spanning)["facts"],
            "",
        )
    ]
    models.save()
    print(f"{models.calls} new model calls in all")

    out_dir = Path(out) / f"group-{group}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "input.md").write_text(source + "\n")
    (out_dir / "uppers.md").write_text(
        "\n".join(
            f"# {name} (sample {k + 1})\n\n{text.strip()}\n"
            for (name, k), text in uppers.items()
        )
    )
    table = [
        f"{len(leaves)} leaves; {len(facts)} facts cite the group's files, "
        f"{len(spanning)} of them files in two or more leaves.\n",
        "| prompt | words | facts conveyed | spanning facts conveyed "
        "| detail share |",
        "|---|---|---|---|---|",
    ]
    for name, samples in rows.items():
        cols = list(zip(*samples, strict=True))
        table.append(
            f"| `{name}` | " + " | ".join(_cell(c) for c in cols) + " |"
        )
    (out_dir / "table.md").write_text("\n".join(table) + "\n")
    print("\n".join(table))


def _leaf_brief(models, pool, db_path, clustering, leaf):
    sections = _members(db_path, clustering, leaf)
    condense = CONDENSE[CONDENSE_PROMPT]
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
    source = _labeled(
        (s["path"], n) for s, n in zip(sections, notes, strict=True)
    )
    template = BRIEF[LEAF_PROMPT].replace("{context}", "")
    return leaf, models.ask(BRIEF_MODEL, template.replace("{content}", source))


def briefs_files(db_path, clustering, leaves) -> dict[int, list[dict]]:
    return {leaf: _members(db_path, clustering, leaf) for leaf in leaves}


def _title(brief: str) -> str:
    for line in brief.splitlines():
        stripped = line.strip().strip("#*").strip()
        if stripped:
            return stripped[:120]
    return "untitled"


def _cell(values) -> str:
    """One column over samples: the mean, and the range when they differ."""
    if values[0] == "":
        return ""
    mean = sum(values) / len(values)
    shown = f"{mean:.0f}" if mean > 1 else f"{mean:.2f}"
    if len(set(values)) > 1 and mean <= 1:
        shown += f" ({min(values):.2f}-{max(values):.2f})"
    return shown


if __name__ == "__main__":
    main(*sys.argv[1:])
