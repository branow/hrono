# ruff: noqa: E501, E741, B904, B905, B023, E402, SIM115
"""Results tables: paired arm comparison per question set.

    uv run --project ~/hrono-bench/harness python analyze.py > ../runs/results.md

Mean with a 95% percentile bootstrap CI (10,000 resamples, seed 0); paired
differences (hrono - repo) on the questions both arms answered, with a paired
bootstrap CI and a two-sided Wilcoxon signed-rank p.
"""

import json
from collections import defaultdict

import common
import numpy as np
from scipy.stats import wilcoxon

RNG = np.random.default_rng(0)
B = 10_000
ARMS = ["repo", "hrono"]


def ci(x):
    x = np.asarray(x, float)
    m = x[RNG.integers(0, len(x), (B, len(x)))].mean(1)
    return np.percentile(m, [2.5, 97.5])


def load(path):
    return (
        {json.loads(l)["qid"]: json.loads(l) for l in open(path)}
        if path.exists()
        else {}
    )


def usage_of(tools):
    rec = sum(
        1 for t in tools if t["tool"] == "Bash" and "recall" in t["input"]
    )
    brief = sum(1 for t in tools if "export-bcreg" in t["input"])
    return rec, brief


def report(kind, metrics):
    runs = {a: load(common.RUNS / f"{kind}-{a}.jsonl") for a in ARMS}
    sc = {a: load(common.RUNS / f"{kind}-{a}.scores.jsonl") for a in ARMS}
    qs = sorted(set(sc["repo"]) & set(sc["hrono"]))
    print(f"\n## {kind} ({len(qs)} questions, paired)\n")
    print("| Metric | repo | hrono | hrono - repo [95% CI] | Wilcoxon p |")
    print("|---|---|---|---|---|")
    rows = {}
    for m in metrics:
        rows[m] = {a: [sc[a][q][m] for q in qs] for a in ARMS}
    for a in ARMS:
        rows.setdefault("turns", {})[a] = [
            runs[a][q]["usage"]["num_turns"] or 0 for q in qs
        ]
        rows.setdefault("wall s", {})[a] = [
            runs[a][q]["usage"]["seconds"] for q in qs
        ]
        rows.setdefault("output tokens", {})[a] = [
            runs[a][q]["usage"]["output_tokens"] for q in qs
        ]
        rows.setdefault("context read (tokens)", {})[a] = [
            runs[a][q]["usage"]["cache_read"]
            + runs[a][q]["usage"]["cache_creation"]
            + runs[a][q]["usage"]["input_tokens"]
            for q in qs
        ]
        rows.setdefault("API-equiv. $", {})[a] = [
            runs[a][q]["usage"]["cost_usd"] or 0 for q in qs
        ]
    for m, v in rows.items():
        r, h = np.array(v["repo"], float), np.array(v["hrono"], float)
        d = h - r
        lo, hi = ci(d)
        p = wilcoxon(d).pvalue if np.any(d != 0) else 1.0
        fmt = (
            (lambda x: f"{x:.3f}")
            if np.mean(np.abs(r)) < 10
            else (lambda x: f"{x:,.0f}")
        )
        rl, rh = ci(r)
        hl, hh = ci(h)
        print(
            f"| {m} | {fmt(r.mean())} [{fmt(rl)}, {fmt(rh)}] | {fmt(h.mean())} [{fmt(hl)}, {fmt(hh)}] | "
            f"{fmt(d.mean())} [{fmt(lo)}, {fmt(hi)}] | {p:.3g} |"
        )
    w = sum(
        1 for q in qs if sc["hrono"][q][metrics[0]] > sc["repo"][q][metrics[0]]
    )
    l = sum(
        1 for q in qs if sc["hrono"][q][metrics[0]] < sc["repo"][q][metrics[0]]
    )
    print(
        f"\n{metrics[0]}: hrono better on {w}, worse on {l}, tied on {len(qs) - w - l}."
    )
    u = [usage_of(runs["hrono"][q]["tools"]) for q in qs]
    print(
        f"hrono arm: recall calls per question {np.mean([x[0] for x in u]):.1f}, "
        f"tree files opened per question {np.mean([x[1] for x in u]):.1f} "
        f"(questions that opened any: {sum(1 for x in u if x[1])})."
    )
    return qs, sc


def by_group(kind, qs, sc, metric, key):
    items = {q["qid"]: q for q in json.load(open(common.DATA / f"{kind}.json"))}
    g = defaultdict(lambda: {"repo": [], "hrono": []})
    for q in qs:
        for a in ARMS:
            g[items[q][key]][a].append(sc[a][q][metric])
    print(f"\n{metric} by {key}:\n")
    print(f"| {key} | n | repo | hrono |")
    print("|---|---|---|---|")
    for k, v in sorted(g.items()):
        print(
            f"| {k} | {len(v['repo'])} | {np.mean(v['repo']):.3f} | {np.mean(v['hrono']):.3f} |"
        )


def extra_arms():
    print("\n## arch, all arms (unpaired summary)\n")
    print(
        "| Arm | n | Fact coverage [95% CI] | Errors | Turns | Recall calls | Brief reads | API-equiv. $ |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for a in ["none", "tree", "hrono", "repo"]:
        sc = load(common.RUNS / f"arch-{a}.scores.jsonl")
        rn = load(common.RUNS / f"arch-{a}.jsonl")
        if not sc:
            continue
        c = [x["coverage"] for x in sc.values()]
        lo, hi = ci(c)
        u = [usage_of(r["tools"]) for r in rn.values()]
        briefs = [
            sum(
                1
                for t in r["tools"]
                if "brief.md" in t["input"] or "root.md" in t["input"]
            )
            for r in rn.values()
        ]
        print(
            f"| {a} | {len(c)} | {np.mean(c):.3f} [{lo:.3f}, {hi:.3f}] | "
            f"{np.mean([x['errors'] for x in sc.values()]):.2f} | "
            f"{np.mean([r['usage']['num_turns'] or 0 for r in rn.values()]):.1f} | "
            f"{np.mean([x[0] for x in u]):.1f} | {np.mean(briefs):.1f} | "
            f"{np.mean([r['usage']['cost_usd'] or 0 for r in rn.values()]):.3f} |"
        )


if __name__ == "__main__":
    print("# Results: agents with and without hrono on BC Registries")
    if (common.RUNS / "locate-hrono.scores.jsonl").exists():
        qs, sc = report("locate", ["recall", "precision", "f1"])
        by_group("locate", qs, sc, "recall", "repo")
    if (common.RUNS / "arch-hrono.scores.jsonl").exists():
        qs, sc = report("arch", ["coverage", "errors"])
        by_group("arch", qs, sc, "coverage", "kind")
        by_group("arch", qs, sc, "coverage", "area")
        extra_arms()
