# ruff: noqa: E501 - report tables and SQL read best on one line
"""Score one clustering: leaf shape, purity, scattering, question traces.

Writes, under the variant's folder:
- `leaves.md`: every leaf, largest first, with its dominant component and
  kinds and a few of its files, for reading by hand;
- `questions.md`: for each architecture question, every answer file with
  the leaves and level-1 groups its sections sit in.
Returns the summary numbers the report compares.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

OVERSIZE = 30  # MAX_CAP in docs/clustering.md
TRACED = ("lear-filings-1", "pay-3")


def score_variant(
    corpus: dict,
    questions: list[dict],
    leaves: np.ndarray,
    groups: np.ndarray,
    out_dir: Path,
) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = np.array(
        [
            f"{source}/{path}"
            for source, path in zip(
                corpus["source"], corpus["rel_path"], strict=True
            )
        ]
    )
    component, kind = corpus["component"], corpus["kind"]
    members = defaultdict(list)
    for index, leaf in enumerate(leaves):
        members[leaf].append(index)

    sizes = np.array([len(m) for m in members.values()])
    dominant = {
        leaf: Counter(component[m]).most_common(1)[0]
        for leaf, m in members.items()
    }
    majority_kind = {
        leaf: Counter(kind[m]).most_common(1)[0][0]
        for leaf, m in members.items()
    }
    code = kind == "code"
    summary = {
        "leaves": len(members),
        "median_leaf": int(np.median(sizes)),
        "max_leaf": int(sizes.max()),
        "pct_sections_in_oversize": _pct(
            (sizes * (sizes > OVERSIZE)).sum(), len(leaves)
        ),
        "groups": len(set(groups)),
        "component_purity": _weighted_purity(members, component),
        "kind_purity": _weighted_purity(members, kind),
        "pct_code_in_noncode_leaf": _pct(
            sum(majority_kind[leaves[i]] != "code" for i in np.where(code)[0]),
            code.sum(),
        ),
        **_file_split(files, leaves),
        "component_in_one_group": _concentration(
            component, groups, min_size=20
        ),
        **_question_scatter(questions, files, leaves, groups),
        **_fact_pairs(questions, files, leaves, groups),
    }
    (out_dir / "leaves.md").write_text(
        _leaves_report(members, dominant, kind, files)
    )
    (out_dir / "questions.md").write_text(
        _questions_report(questions, files, leaves, groups, dominant, members)
    )
    return {"summary": summary}


def _weighted_purity(members: dict, labels: np.ndarray) -> float:
    """Share of sections that carry their leaf's most common label."""
    top = sum(Counter(labels[m]).most_common(1)[0][1] for m in members.values())
    return round(top / sum(len(m) for m in members.values()), 3)


def _file_split(files: np.ndarray, leaves: np.ndarray) -> dict:
    leaves_of = defaultdict(set)
    for name, leaf in zip(files, leaves, strict=True):
        leaves_of[name].add(leaf)
    counts = Counter(files)
    multi = [name for name, count in counts.items() if count >= 2]
    split = [name for name in multi if len(leaves_of[name]) > 1]
    return {
        "pct_multisection_files_split": _pct(len(split), len(multi)),
        "max_leaves_per_file": max(len(leaves_of[name]) for name in multi),
    }


def _concentration(
    labels: np.ndarray, groups: np.ndarray, min_size: int
) -> float:
    """Section-weighted share of a component that sits in its biggest group."""
    kept = total = 0
    for label in set(labels):
        mask = labels == label
        if mask.sum() < min_size:
            continue
        kept += Counter(groups[mask]).most_common(1)[0][1]
        total += mask.sum()
    return round(kept / total, 3)


def _question_scatter(
    questions: list[dict],
    files: np.ndarray,
    leaves: np.ndarray,
    groups: np.ndarray,
) -> dict:
    leaf_hits, group_hits, top_group_share = [], [], []
    traced = {}
    for question in questions:
        mask = np.isin(files, _answer_files(question))
        if not mask.any():
            continue
        leaf_hits.append(len(set(leaves[mask])))
        group_hits.append(len(set(groups[mask])))
        top_group_share.append(
            Counter(groups[mask]).most_common(1)[0][1] / mask.sum()
        )
        if question["qid"] in TRACED:
            traced[question["qid"]] = (leaf_hits[-1], group_hits[-1])
    return {
        "q_median_leaves": float(np.median(leaf_hits)),
        "q_median_groups": float(np.median(group_hits)),
        "q_top_group_share": round(float(np.mean(top_group_share)), 3),
        **{
            f"{qid}_leaves_groups": f"{hits[0]} / {hits[1]}"
            for qid, hits in traced.items()
        },
    }


def _fact_pairs(
    questions: list[dict],
    files: np.ndarray,
    leaves: np.ndarray,
    groups: np.ndarray,
) -> dict:
    """How often two files one fact cites together share a leaf, a group.

    A fact names the files that do one thing together (a route, the service
    it calls, the model it writes), so this is "do the files of one
    behaviour sit together". A file split over leaves counts as its
    leaves' set; a pair shares a leaf when the sets meet.
    """
    leaf_sets, group_sets = defaultdict(set), defaultdict(set)
    for name, leaf, group in zip(files, leaves, groups, strict=True):
        leaf_sets[name].add(leaf)
        group_sets[name].add(group)
    pairs = same_leaf = same_group = 0
    for question in questions:
        for fact in question["facts"]:
            cited = sorted({f for f in fact["files"] if f in leaf_sets})
            for i, a in enumerate(cited):
                for b in cited[i + 1 :]:
                    pairs += 1
                    same_leaf += bool(leaf_sets[a] & leaf_sets[b])
                    same_group += bool(group_sets[a] & group_sets[b])
    return {
        "fact_pairs_same_leaf": round(same_leaf / pairs, 3),
        "fact_pairs_same_group": round(same_group / pairs, 3),
    }


def _answer_files(question: dict) -> list[str]:
    return sorted(
        {name for fact in question["facts"] for name in fact["files"]}
    )


def _leaves_report(members, dominant, kind, files) -> str:
    lines = [
        "| leaf | sections | files | main component (share) | kinds | sample files |",
        "|---|---|---|---|---|---|",
    ]
    for leaf, m in sorted(members.items(), key=lambda item: -len(item[1])):
        name, count = dominant[leaf]
        kinds = ", ".join(f"{k} {c}" for k, c in Counter(kind[m]).most_common())
        unique = list(dict.fromkeys(files[m]))
        sample = "<br>".join(f"`{f}`" for f in unique[:4])
        lines.append(
            f"| {leaf} | {len(m)} | {len(unique)} | {name} ({count / len(m):.0%}) "
            f"| {kinds} | {sample} |"
        )
    return "\n".join(lines) + "\n"


def _questions_report(
    questions, files, leaves, groups, dominant, members
) -> str:
    out = []
    for question in questions:
        answer = _answer_files(question)
        mask = np.isin(files, answer)
        out.append(f"## {question['qid']} ({question['kind']})\n")
        out.append(f"{question['question']}\n")
        out.append(
            f"{len(set(files[mask]))} of {len(answer)} answer files indexed, "
            f"{len(set(leaves[mask]))} leaves, {len(set(groups[mask]))} groups.\n"
        )
        out.append("| file | leaf: main component (share), size | group |")
        out.append("|---|---|---|")
        for name in answer:
            hit = np.where(files == name)[0]
            if not len(hit):
                out.append(f"| `{name}` | not indexed | |")
                continue
            cells = []
            for leaf in dict.fromkeys(leaves[hit]):
                comp, count = dominant[leaf]
                size = len(members[leaf])
                cells.append(f"{leaf}: {comp} ({count / size:.0%}), {size}")
            out.append(
                f"| `{name}` | {'<br>'.join(cells)} | "
                f"{', '.join(str(g) for g in dict.fromkeys(groups[hit]))} |"
            )
        out.append("")
    return "\n".join(out)


def _pct(part: float, whole: float) -> float:
    return round(100 * float(part) / float(whole), 1) if whole else 0.0
