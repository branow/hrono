# ruff: noqa: E501 - experiment harness; prompts read best whole
"""Round 7: flow topics, a second parent for leaf topics, grouped by links.

The similarity tree splits a flow across areas (pay-api, business-pay, the
filer, the emailer, a job), and no brief states the flow end to end. Here
the leaf topics are grouped by the link graph (Louvain over the defines/uses
links, channel links weighted up, common names down), and each group gets a
flow brief written from its members' briefs and the links between them,
short enough for recall to attach whole.

Usage: uv run --with networkx python flows.py groups
       uv run --with claude-agent-sdk python flows.py brief
"""

from __future__ import annotations

import sys

import exp
from exp import c, sl

FLOW = """Below are the briefs of the topics that make up one flow of a larger system - topics grouped because their code calls, publishes to, consumes from or shares names with each other - followed by the links between them, computed from the code. Write the brief of this flow: what a reader (human or AI agent) needs to understand how work moves across these topics and where it can go wrong.

Write, in this order:
1. One or two sentences: what this flow does end to end.
2. The end-to-end paths, each as numbered steps from what starts it to what it ends with. At each step name the topic and the function, the message, queue subject or endpoint that carries the work to the next step, the state a record moves to, and the condition that decides the branch (copy lists and statuses verbatim).
3. Hand-offs: for each place where work crosses from one topic to another, one line - what crosses, which credential is sent, which side checks what, and what happens when the hand-off fails (retried, recorded, only logged, swallowed). Say which job or path, if any, repairs a lost hand-off; say so when none does.
4. Divergences: two implementations of the same step (an old and a new listener, copies of a model, a v1 and a v2), and what each does differently.
5. Where to look: the topic briefs and source files to open for each path.

Every check comes with its condition, or "(condition not in the briefs)"; never let a check's name stand for a guarantee. Keep names, values and lists verbatim. At most 1,400 words: keep what crosses topics, leave what stays inside one topic to its brief. Mention only what the briefs and links say. Write about the flow itself, never about the text you were given. Output only the brief in markdown.

{content}"""


def graph():
    import networkx as nx

    g = nx.Graph()
    for it in exp.load("links.json"):
        a, b = it["from_leaf"], it["to_leaf"]
        w = (
            2.0 if it["kind"] in ("shares", "sends", "receives") else 1.0
        ) / max(1, it["tree_leaves"]) ** 0.5
        g.add_edge(
            a, b, weight=g.get_edge_data(a, b, {"weight": 0})["weight"] + w
        )
    return g


def groups() -> None:
    import networkx as nx

    g = graph()
    comms = [
        sorted(x)
        for x in nx.community.louvain_communities(g, weight="weight", seed=1)
    ]
    comms = [x for x in sorted(comms, key=len, reverse=True) if len(x) >= 5]
    exp.save("flow-groups.json", comms)
    print([len(x) for x in comms])


def brief() -> None:
    conn = c.connect()
    title = sl.titles(conn)
    stored = dict(conn.execute("SELECT node_id, text FROM briefs"))
    wide = {int(k): v["text"] for k, v in exp.load("briefs-W.json").items()}
    links = exp.load("links.json")
    out = exp.load("flow-briefs.json")

    def one(job):
        i, members = job
        mset = set(members)
        parts = [
            f"=== {title.get(n, n)} ===\n{wide.get(n) or stored.get(n, '')}"
            for n in members
        ]
        lines = []
        for it in sorted(links, key=lambda x: x["tree_leaves"]):
            a, b = it["from_leaf"], it["to_leaf"]
            if a in mset and b in mset:
                lines.append(
                    f'- "{title.get(a, a)[:70]}" {it["direction"]} `{it["name"]}` ({it["kind"]} in "{title.get(b, b)[:70]}"): {exp.clip(it["what"], 30)}'
                )
        lines = list(dict.fromkeys(lines))[:150]
        content = "\n\n".join(parts) + "\n\n=== LINKS ===\n" + "\n".join(lines)
        got = exp.ask(FLOW.replace("{content}", content), exp.SONNET)
        return str(i), {**got, "members": members}

    jobs = [
        (i, m)
        for i, m in enumerate(exp.load("flow-groups.json"))
        if str(i) not in out
    ]
    for i, got in exp.run_pool(one, jobs, 4):
        out[i] = got
        exp.save("flow-briefs.json", out)
    for k, v in out.items():
        print(
            k,
            len(v["members"]),
            "topics",
            len((v.get("text") or "").split()),
            "words",
            v.get("error"),
        )
    print("cost", round(sum(v.get("cost") or 0 for v in out.values()), 2))


if __name__ == "__main__":
    {"groups": groups, "brief": brief}[sys.argv[1]]()
