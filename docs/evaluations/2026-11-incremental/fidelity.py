"""E1 RQ3/RQ4: the incrementally maintained tree against cold builds.

Matches sections across databases by (path, byte_start, content_hash) and
compares their section -> leaf assignment with ARI and AMI, pairwise. Also
reports leaf counts and, per tree, the share of briefs with an unfaithful
or copy-gate flag.

Usage: uv run python fidelity.py name=path.db [name=path.db ...]
"""

import itertools
import json
import sqlite3
import sys

from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score

TREE = "streamlink"


def load(path):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    leaf = {
        (p, start, h): node
        for p, start, h, node in db.execute(
            "select s.path, s.byte_start, s.content_hash, n.id from sections s"
            " join node_members m on m.section_id = s.id"
            " join nodes n on n.id = m.node_id"
            " where n.tree = ? and n.level = 0 and s.source_type != 'node'",
            (TREE,),
        )
    }
    briefs = db.execute(
        "select count(*), sum(unfaithful != '[]'), sum(flagged != '')"
        " from briefs b join nodes n on n.id = b.node_id where n.tree = ?",
        (TREE,),
    ).fetchone()
    levels = dict(
        db.execute(
            "select level, count(*) from nodes where tree = ? group by level",
            (TREE,),
        )
    )
    return leaf, briefs, levels


trees = dict(arg.split("=", 1) for arg in sys.argv[1:])
data = {name: load(path) for name, path in trees.items()}
out = {"trees": {}, "pairs": {}}
for name, (leaf, briefs, levels) in data.items():
    out["trees"][name] = {
        "sections_placed": len(leaf),
        "nodes_by_level": levels,
        "briefs": briefs[0],
        "briefs_unfaithful": briefs[1],
        "briefs_flagged": briefs[2],
    }
for a, b in itertools.combinations(data, 2):
    common = sorted(data[a][0].keys() & data[b][0].keys())
    x = [data[a][0][k] for k in common]
    y = [data[b][0][k] for k in common]
    out["pairs"][f"{a} vs {b}"] = {
        "common_sections": len(common),
        "ari": round(adjusted_rand_score(x, y), 4),
        "ami": round(adjusted_mutual_info_score(x, y), 4),
    }
print(json.dumps(out, indent=1))
