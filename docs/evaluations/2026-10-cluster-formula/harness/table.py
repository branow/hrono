"""Turn the per-seed summaries into one table: mean of the seeds per formula.

Only formulas scored on every seed are listed, sorted by how often the files
of one fact share a leaf.

Usage: python table.py DATA_DIR > DATA_DIR/results.md
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

COLUMNS = (
    ("component_purity", "one-service leaves", 3),
    ("component_in_one_group", "service in its biggest group", 3),
    ("fact_pairs_same_leaf", "fact files share a leaf", 3),
    ("fact_pairs_same_group", "fact files share a group", 3),
    ("q_median_groups", "groups per answer", 1),
    ("pct_multisection_files_split", "split files %", 0),
    ("leaves", "leaves", 0),
    ("max_leaf", "largest leaf", 0),
)


def main(data_dir: str) -> None:
    seeds = {
        path.stem.removeprefix("summary-seed"): json.loads(path.read_text())
        for path in sorted(Path(data_dir).glob("summary-seed*.json"))
    }
    names = set.intersection(*(set(summary) for summary in seeds.values()))
    rows = []
    for name in names:
        means = [
            statistics.mean(
                seed[name]["summary"][key] for seed in seeds.values()
            )
            for key, _, _ in COLUMNS
        ]
        per_seed = "/".join(
            str(seed[name]["summary"]["fact_pairs_same_leaf"])
            for seed in seeds.values()
        )
        rows.append((name, means, per_seed, seeds["42"][name].get("weights")))
    rows.sort(key=lambda row: -row[1][2])

    print(f"Mean over seeds {', '.join(seeds)}.\n")
    print(
        "| formula | weights | "
        + " | ".join(h for _, h, _ in COLUMNS)
        + " | fact files share a leaf, per seed |"
    )
    print("|---" * (len(COLUMNS) + 3) + "|")
    for name, means, per_seed, weights in rows:
        cells = [
            f"{value:.{digits}f}"
            for value, (_, _, digits) in zip(means, COLUMNS, strict=True)
        ]
        shown = (
            ", ".join(f"{k} {v}" for k, v in (weights or {}).items())
            or "as built"
        )
        print(
            f"| `{name}` | {shown} | " + " | ".join(cells) + f" | {per_seed} |"
        )


if __name__ == "__main__":
    main(sys.argv[1])
