"""E1: measure each sync from consecutive database copies and job reports.

Reads <work>/db/step-NN.db (step 00 is the cold build) and
<work>/jobs/step-NN.json (the `hrono jobs get` report), and writes steps.csv
next to this file. Cost is API-equivalent, from the llm_calls ledger and
hrono's own price table.

Usage: python3 measure.py <work>     (e.g. ~/hrono-incremental)
"""

import collections
import csv
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3] / "src"))
from hrono.usage.prices import price_for  # noqa: E402

WORK = Path(sys.argv[1]).expanduser()
TREE = "streamlink"


def snapshot(path):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    sections = dict(
        db.execute(
            "select id, content_hash from sections where source_type != 'node'"
        )
    )
    leaf = dict(
        db.execute(
            "select nm.section_id, n.id from node_members nm join nodes n"
            " on n.id = nm.node_id where n.tree = ? and n.level = 0",
            (TREE,),
        )
    )
    nodes = {
        nid: level
        for nid, level in db.execute(
            "select id, level from nodes where tree = ?", (TREE,)
        )
    }
    briefs = {
        nid: (created, stale, judged, unfaithful, flagged)
        for nid, created, stale, judged, unfaithful, flagged in db.execute(
            "select node_id, created_at, stale, judged_signature, unfaithful,"
            " flagged from briefs"
        )
    }
    calls = list(
        db.execute(
            "select id, role, upstream_model, input_tokens, output_tokens,"
            " cache_read_tokens, cache_creation_tokens, duration_ms, ok"
            " from llm_calls"
        )
    )
    verdicts = list(
        db.execute(
            "select id, node_id, verdict, action from update_log where tree = ?",
            (TREE,),
        )
    )
    misfit = db.execute(
        "select coalesce(sum(misfits), 0), coalesce(sum(members), 0)"
        " from misfit where tree = ?",
        (TREE,),
    ).fetchone()
    return dict(
        sections=sections,
        leaf=leaf,
        nodes=nodes,
        briefs=briefs,
        calls=calls,
        verdicts=verdicts,
        misfit=misfit,
    )


def cost(calls):
    by_role = collections.defaultdict(lambda: [0, 0.0])
    for _, role, upstream, i, o, cr, cw, _, _ in calls:
        price = price_for(upstream)
        usd = price.cost(i or 0, o or 0, cr or 0, cw or 0) if price else 0.0
        by_role[role][0] += 1
        by_role[role][1] += usd
    return by_role


def walk(report):
    """Every stage result in a job report, flattened."""
    out = collections.Counter()
    for stage in report.get("stages", []):
        for key, value in (stage.get("result") or {}).items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                out[f"{stage['op']}.{key}"] += value
            elif isinstance(value, bool):
                out[f"{stage['op']}.{key}"] = int(value)
    return out


def main():
    copies = sorted((WORK / "db").glob("step-*.db"))
    rows = []
    prev = snapshot(copies[0])
    build_cost = sum(v[1] for v in cost(prev["calls"]).values())
    for path in copies[1:]:
        step = path.stem.split("-")[1]
        cur = snapshot(path)
        report = json.loads((WORK / "jobs" / f"{path.stem}.json").read_text())
        stages = walk(report.get("result", report))
        seen = {c[0] for c in prev["calls"]}
        calls = [c for c in cur["calls"] if c[0] not in seen]
        roles = cost(calls)
        before, after = prev["sections"], cur["sections"]
        added = after.keys() - before.keys()
        deleted = before.keys() - after.keys()
        kept = before.keys() & after.keys()
        moved = moved_by_repair = 0
        for s in kept:
            a, b = prev["leaf"].get(s), cur["leaf"].get(s)
            if a is not None and b is not None and a != b:
                if a in cur["nodes"]:
                    moved += 1
                else:
                    moved_by_repair += 1
        members = collections.defaultdict(set)
        for s in added | deleted:
            for leaf in (prev["leaf"].get(s), cur["leaf"].get(s)):
                if leaf is not None:
                    members[leaf].add(s)
        changed_leaves = {leaf for leaf in members if leaf in cur["nodes"]}
        rebriefed = {
            n
            for n, b in cur["briefs"].items()
            if n not in prev["briefs"] or b[0] != prev["briefs"][n][0]
        }
        old_verdicts = {v[0] for v in prev["verdicts"]}
        new_verdicts = [v for v in cur["verdicts"] if v[0] not in old_verdicts]
        judged = {v[1] for v in new_verdicts}
        stale_left = sorted(
            leaf
            for leaf in changed_leaves
            if leaf not in rebriefed and leaf not in judged
        )
        levels = cur["nodes"]
        usd = sum(v[1] for v in roles.values())
        row = {
            "step": int(step),
            "sections_added": len(added),
            "sections_deleted": len(deleted),
            "sections_total": len(after),
            "leaves": sum(1 for lv in levels.values() if lv == 0),
            "leaves_with_changed_members": len(changed_leaves),
            "unchanged_sections_moved": moved,
            "unchanged_sections_moved_by_repair": moved_by_repair,
            "changed_leaves_unbriefed_unjudged": len(stale_left),
            "briefs_rewritten_leaf": sum(
                1 for n in rebriefed if levels.get(n) == 0
            ),
            "briefs_rewritten_upper": sum(
                1 for n in rebriefed if (levels.get(n) or 0) > 0
            ),
            "verdicts": dict(collections.Counter(v[2] for v in new_verdicts)),
            "misfit": round(cur["misfit"][0] / cur["misfit"][1], 4)
            if cur["misfit"][1]
            else "",
            "calls": {r: v[0] for r, v in sorted(roles.items())},
            "usd": round(usd, 4),
            "usd_by_role": {r: round(v[1], 4) for r, v in sorted(roles.items())},
            "share_of_build": round(usd / build_cost, 4) if build_cost else "",
            "model_seconds": round(sum(c[7] for c in calls) / 1000, 1),
            "failed_calls": sum(1 - c[8] for c in calls),
            "stages": dict(stages),
        }
        rows.append(row)
        prev = cur
    out = Path(__file__).with_name("steps.csv")
    with out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(v) if isinstance(v, dict) else v
                    for k, v in row.items()
                }
            )
    print(f"build ${build_cost:.2f}; {len(rows)} steps -> {out}")


main()
