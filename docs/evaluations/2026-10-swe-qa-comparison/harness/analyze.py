# ruff: noqa: E501, E741, B904, B905, B007, B023
"""Turn answers, judgments and call logs into the results tables.

    uv run python analyze.py > ../runs/results.md

Statistics: mean judge total (5 dimensions x 1-20 = 100) with a 95% percentile
bootstrap CI (10,000 resamples, seed 0); paired comparisons against hrono on
the questions both answered, as the mean difference with a paired bootstrap
CI and a two-sided Wilcoxon signed-rank p, Holm-corrected across the
comparisons in each table.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict

import common
import numpy as np
from scipy.stats import wilcoxon

RNG = np.random.default_rng(0)
B = 10_000
DIMS = ["correctness", "completeness", "relevance", "clarity", "reasoning"]
SINGLE = ["closed-book", "bm25", "dense", "raptor", "lightrag", "hrono"]
AGENTS = ["agent-repo", "agent-hrono", "agent-hrono-first"]


SUBSET = None  # restrict every load to these question ids


def load(kind, system):
    path = common.RUNS / kind / f"{system}.jsonl"
    if not path.exists():
        return {}
    rows = {}
    for line in path.open():
        r = json.loads(line)
        if SUBSET is None or r["qid"] in SUBSET:
            rows[r["qid"]] = r
    return rows


def boot_ci(x):
    x = np.asarray(x, float)
    means = x[RNG.integers(0, len(x), (B, len(x)))].mean(1)
    return np.percentile(means, [2.5, 97.5])


def holm(ps):
    order = np.argsort(ps)
    out = [0.0] * len(ps)
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        out[i] = running
    return out


FILE_RE = re.compile(
    r"[\w./-]*\w\.(?:py|rst|md|txt|toml|cfg|ini|yml|yaml|json|html)\b"
)


def ref_files(text):
    return {m.strip("./") for m in FILE_RE.findall(text) if "/" in m}


def file_recall(answer_row, reference):
    refs = ref_files(reference)
    if not refs:
        return None
    ctx = answer_row.get("context", "").replace("__", "/")
    return sum(1 for f in refs if f in ctx) / len(refs)


def table(systems, base, title, refs):
    print(f"\n### {title}\n")
    data = {s: (load("answers", s), load("judgments", s)) for s in systems}
    data = {s: v for s, v in data.items() if v[1]}
    print(
        "| System | n | Score /100 [95% CI] | "
        + " | ".join(d.capitalize() for d in DIMS)
        + " | File recall | Context chars |"
    )
    print("|---|---|---|" + "---|" * len(DIMS) + "---|---|")
    for s, (ans, jud) in data.items():
        rows = [j for j in jud.values() if j["scores"]]
        tot = [j["total"] for j in rows]
        lo, hi = boot_ci(tot)
        dims = [np.mean([j["scores"][d] for j in rows]) for d in DIMS]
        fr = [
            file_recall(ans[q], refs[q]["reference"]) for q in jud if q in ans
        ]
        fr = [f for f in fr if f is not None]
        ctx = np.mean([ans[q]["context_chars"] for q in jud if q in ans])
        frs = (
            f"{np.mean(fr):.2f} (n={len(fr)})"
            if fr and s != "closed-book" and not s.startswith("agent")
            else "–"
        )
        print(
            f"| {s} | {len(tot)} | **{np.mean(tot):.1f}** [{lo:.1f}, {hi:.1f}] | "
            + " | ".join(f"{d:.1f}" for d in dims)
            + f" | {frs} | {ctx:.0f} |"
        )
    if base not in data:
        return
    print(f"\nPaired against **{base}** (positive = {base} better):\n")
    print(
        "| vs | n pairs | Mean diff [95% CI] | Wins / ties / losses | Wilcoxon p | Holm p |"
    )
    print("|---|---|---|---|---|---|")
    lines, ps = [], []
    bj = data[base][1]
    for s, (_, jud) in data.items():
        if s == base:
            continue
        common_q = [
            q for q in jud if q in bj and jud[q]["scores"] and bj[q]["scores"]
        ]
        d = np.array(
            [bj[q]["total"] - jud[q]["total"] for q in common_q], float
        )
        if len(d) < 2:
            continue
        means = d[RNG.integers(0, len(d), (B, len(d)))].mean(1)
        lo, hi = np.percentile(means, [2.5, 97.5])
        p = wilcoxon(d).pvalue if np.any(d != 0) else 1.0
        ps.append(p)
        lines.append(
            (
                s,
                len(d),
                d.mean(),
                lo,
                hi,
                int((d > 0).sum()),
                int((d == 0).sum()),
                int((d < 0).sum()),
                p,
            )
        )
    for (s, n, m, lo, hi, w, t, l, p), hp in zip(lines, holm(ps)):
        print(
            f"| {s} | {n} | {m:+.1f} [{lo:+.1f}, {hi:+.1f}] | {w} / {t} / {l} | {p:.3g} | {hp:.3g} |"
        )


def per_repo(systems):
    print("\n### Score by repository (mean /100)\n")
    repos = common.REPO_NAMES
    print("| System | " + " | ".join(repos) + " |")
    print("|---|" + "---|" * len(repos))
    for s in systems:
        jud = load("judgments", s)
        if not jud:
            continue
        cells = []
        for r in repos:
            t = [
                j["total"]
                for j in jud.values()
                if j["repo"] == r and j["scores"]
            ]
            cells.append(f"{np.mean(t):.1f} (n={len(t)})" if t else "–")
        print(f"| {s} | " + " | ".join(cells) + " |")


def hrono_hits():
    ans = load("answers", "hrono")
    n = [len(r["labels"]) for r in ans.values()]
    zero = sum(1 for x in n if x == 0)
    print("\n### hrono recall hit counts\n")
    print(
        f"- questions: {len(n)}; zero hits: {zero} ({zero / max(len(n), 1):.0%}); "
        f"mean hits {np.mean(n):.1f}; median {np.median(n):.0f}"
    )
    by = defaultdict(list)
    jud = load("judgments", "hrono")
    for q, r in ans.items():
        if q in jud and jud[q]["scores"]:
            by[len(r["labels"]) == 0].append(jud[q]["total"])
    if by:
        print(
            f"- hrono score when recall returned nothing: "
            f"{np.mean(by[True]) if by[True] else float('nan'):.1f} "
            f"(n={len(by[True])}); when it returned passages: "
            f"{np.mean(by[False]) if by[False] else float('nan'):.1f} (n={len(by[False])})"
        )


def costs():
    print("\n### LLM calls by role (benchmark harness)\n")
    agg = defaultdict(lambda: defaultdict(float))
    for line in (common.RUNS / "calls.jsonl").open():
        r = json.loads(line)
        a = agg[r["role"]]
        a["calls"] += 1
        for k in (
            "input_tokens",
            "output_tokens",
            "cache_read",
            "cache_creation",
            "seconds",
        ):
            a[k] += r.get(k) or 0
        a["cost"] += r.get("cost_usd") or 0
    print(
        "| Role | Calls | Input | Output | Cache read | Cache write | Model seconds | API-equiv. $ |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for role in sorted(agg):
        a = agg[role]
        print(
            f"| {role} | {a['calls']:.0f} | {a['input_tokens']:.0f} | {a['output_tokens']:.0f} | "
            f"{a['cache_read']:.0f} | {a['cache_creation']:.0f} | {a['seconds']:.0f} | {a['cost']:.2f} |"
        )
    conn = sqlite3.connect(f"file:{common.HRONO_DB}?mode=ro", uri=True)
    print("\n### hrono build (from hrono's own ledger)\n")
    print("| Role | Calls | Input | Output | Cache read | Model seconds |")
    print("|---|---|---|---|---|---|")
    for row in conn.execute(
        "SELECT role, count(*), sum(input_tokens), sum(output_tokens), "
        "sum(cache_read_tokens), sum(duration_ms)/1000 FROM llm_calls "
        "WHERE role != 'embedding' GROUP BY role"
    ):
        print("| " + " | ".join(str(x or 0) for x in row) + " |")


def agents():
    print("\n### Agent effort per question\n")
    print(
        "| Arm | n | Turns (mean) | Wall s (mean) | Output tokens (mean) | Cache read (mean) | API-equiv. $ (mean) | Hit max turns |"
    )
    print("|---|---|---|---|---|---|---|---|")
    for a in AGENTS:
        ans = load("answers", a)
        if not ans:
            continue
        rows = list(ans.values())
        print(
            f"| {a} | {len(rows)} | {np.mean([r['num_turns'] or 0 for r in rows]):.1f} | "
            f"{np.mean([r['seconds'] for r in rows]):.0f} | "
            f"{np.mean([r['usage']['output_tokens'] for r in rows]):.0f} | "
            f"{np.mean([r['usage']['cache_read'] for r in rows]):.0f} | "
            f"{np.mean([r['usage']['cost_usd'] or 0 for r in rows]):.3f} | "
            f"{sum(1 for r in rows if r['subtype'] != 'success')} |"
        )


def main():
    refs = {q["qid"]: q for r in common.REPO_NAMES for q in common.questions(r)}
    print("## Results\n")
    table(
        SINGLE, "hrono", "Single-shot retrieval + answer, all questions", refs
    )
    per_repo(SINGLE + AGENTS)
    hrono_hits()
    agent_q = set(load("answers", "agent-repo")) & set(
        load("answers", "agent-hrono")
    )
    if agent_q:
        # restrict every system to the agent subset for a like-for-like view
        global SUBSET
        SUBSET = agent_q
        table(
            SINGLE + AGENTS,
            "agent-repo",
            f"Agent subset ({len(agent_q)} questions), every system",
            refs,
        )
        SUBSET = None
        agents()
    costs()


if __name__ == "__main__":
    main()
