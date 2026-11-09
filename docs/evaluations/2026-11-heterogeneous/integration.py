"""E2 RQ1: does the webERP code+threads tree mix source types in its topics?

Reads a copy of the tree database (sections, nodes, node_members,
node_children) and data/pr-files.tsv (each PR's changed files, from the
GitHub API). Prints JSON: leaf mix against a permutation baseline, and how
often a thread sits in the same leaf or area as the files it is about.

Usage: python3 integration.py <tree.db> [permutations]
"""

import collections
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).parent
DB = sys.argv[1]
PERMUTATIONS = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
THREADS = Path.home() / "hrono-weberp" / "threads-2026-02-27"

db = sqlite3.connect(DB)
leaf_of = {}  # section id -> leaf id
for section, leaf in db.execute(
    "select nm.section_id, n.id from node_members nm"
    " join nodes n on n.id = nm.node_id where n.level = 0"
):
    leaf_of[section] = leaf
area_of_leaf = dict(
    db.execute(
        "select c.child_id, c.parent_id from node_children c"
        " join nodes p on p.id = c.parent_id where p.level = 1"
    )
)
kind = {}  # section id -> 'code' | 'thread'
path = {}
for sid, stype, spath in db.execute(
    "select id, source_type, path from sections where source_type != 'node'"
):
    kind[sid] = "thread" if stype == "github-threads" else "code"
    path[sid] = spath

placed = [s for s in kind if s in leaf_of]
leaves = collections.defaultdict(list)
for s in placed:
    leaves[leaf_of[s]].append(kind[s])


def mix(groups):
    mixed = sum(1 for g in groups if len(set(g)) > 1)
    purity = sum(
        max(collections.Counter(g).values()) / len(g) for g in groups
    ) / len(groups)
    return mixed, purity


groups = list(leaves.values())
mixed, purity = mix(groups)
sizes = [len(g) for g in groups]
pool = [kind[s] for s in placed]
rng = random.Random(0)
null_mixed, null_purity = [], []
for _ in range(PERMUTATIONS):
    rng.shuffle(pool)
    shuffled, i = [], 0
    for n in sizes:
        shuffled.append(pool[i : i + n])
        i += n
    m, p = mix(shuffled)
    null_mixed.append(m)
    null_purity.append(p)

by_type = collections.Counter()
for g in groups:
    types = set(g)
    by_type["mixed" if len(types) > 1 else types.pop() + " only"] += 1

areas = collections.defaultdict(collections.Counter)
for s in placed:
    areas[area_of_leaf.get(leaf_of[s])][kind[s]] += 1

# Thread -> linked files: a PR's changed files; for issues and discussions,
# file names from the repository that the thread's text mentions.
code_paths = {path[s] for s in placed if kind[s] == "code"}
basename = collections.defaultdict(set)
for p in code_paths:
    basename[Path(p).name].add(p)
pr_files = {}
for line in (HERE / "data" / "pr-files.tsv").read_text().splitlines():
    number, _, files = line.partition("\t")
    pr_files[f"pulls/pull-{number}.md"] = [f for f in files.split(",") if f]
name_re = re.compile(r"[\w./-]+\.(?:php|js|sql|css|xml|inc|html)\b")

thread_sections = collections.defaultdict(list)
for s in placed:
    if kind[s] == "thread":
        thread_sections[path[s]].append(s)
code_sections = collections.defaultdict(list)
for s in placed:
    if kind[s] == "code":
        code_sections[path[s]].append(s)

rows = collections.Counter()
code_list = sorted(code_paths)
random_area = []  # per linked thread: chance a random file set shares an area
for tpath, sids in thread_sections.items():
    if tpath in pr_files:
        linked = {f for f in pr_files[tpath] if f in code_paths}
        how = "pr"
    else:
        text = (THREADS / tpath).read_text(errors="replace")
        linked = set()
        for m in name_re.findall(text):
            linked |= {m} & code_paths or basename.get(Path(m).name, set())
        how = "text"
    if not linked:
        rows[how, "no linked file"] += 1
        continue
    t_leaves = {leaf_of[s] for s in sids}
    t_areas = {area_of_leaf.get(x) for x in t_leaves}
    f_leaves = {leaf_of[s] for f in linked for s in code_sections[f]}
    f_areas = {area_of_leaf.get(x) for x in f_leaves}
    rows[how, "linked"] += 1
    rows[how, "same leaf"] += bool(t_leaves & f_leaves)
    rows[how, "same area"] += bool(t_areas & f_areas)
    hits = 0
    for _ in range(100):
        sample = rng.sample(code_list, len(linked))
        r_areas = {
            area_of_leaf.get(leaf_of[s]) for f in sample for s in code_sections[f]
        }
        hits += bool(t_areas & r_areas)
    random_area.append((how, hits / 100))
for how in ("pr", "text"):
    rows[how, "same area, random files (expected)"] = round(
        sum(p for h, p in random_area if h == how), 1
    )

print(
    json.dumps(
        {
            "sections_placed": collections.Counter(pool),
            "leaves": len(groups),
            "leaves_by_type": by_type,
            "mixed_leaves": mixed,
            "mixed_leaves_random_mean": sum(null_mixed) / PERMUTATIONS,
            "mixed_leaves_random_min": min(null_mixed),
            "purity_mean": round(purity, 4),
            "purity_random_mean": round(sum(null_purity) / PERMUTATIONS, 4),
            "areas": {str(a): dict(c) for a, c in areas.items()},
            "colocation": {" / ".join(k): v for k, v in sorted(rows.items())},
        },
        indent=1,
    )
)
