"""E2 RQ2: do the threads add knowledge? Single-shot answers from recall.

For each question in data/questions.json: recall 10 hits from tree A (code
only, port 8801) and tree B (code + threads, port 8802), have Sonnet answer
from those hits alone, and also answer with no context (the memory check).
A blind Opus judge then marks each reference fact as covered or not, with
the three answers shuffled and unlabelled. Writes data/answers.json and
data/grades.json.

Usage: python3 qa.py answer | grade | report
"""

import json
import random
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
CONFIG = (Path.home() / "hrono-weberp" / "home" / "config.toml").read_text()
TOKEN = next(
    line.split('"')[1] for line in CONFIG.splitlines() if line.startswith("token")
)
PORTS = {"A": 8801, "B": 8802}


def claude(prompt, model):
    out = subprocess.run(
        ["claude", "-p", prompt, "--model", model, "--setting-sources", "",
         "--strict-mcp-config", "--tools", "", "--output-format", "json"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, check=True,
    )
    reply = json.loads(out.stdout)
    return reply["result"], reply.get("total_cost_usd", 0.0)


def recall(port, question):
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/trees/weberp/recall",
        data=json.dumps({"question": question, "limit": 10}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}",
                 "content-type": "application/json"},
    )
    hits = json.load(urllib.request.urlopen(request))["hits"]
    return [
        {"path": h["path"], "source": h["source"], "kind": h["kind"],
         "text": f"{h['header']}\n{h['body']}"}
        for h in hits
    ]


ANSWER = """Answer a developer's question about the webERP project{ctx}.
Answer in 2-5 sentences; if the material does not say, answer "unknown".

Question: {question}
{material}"""

JUDGE = """You grade answers to a question about the webERP project against
a list of reference facts. For each answer and each fact, say whether the
answer states that fact (paraphrase is fine; a vague gesture is not). Do
not reward extra content.

Question: {question}

Reference facts:
{facts}

{answers}

Reply with JSON only: {{"<answer label>": [true/false per fact, in order]}}"""


def answer():
    questions = json.loads((DATA / "questions.json").read_text())
    out, usd = [], 0.0
    for q in questions:
        row = {"id": q["id"], "half": q["half"], "hits": {}, "answers": {}}
        for arm, port in PORTS.items():
            hits = recall(port, q["question"])
            row["hits"][arm] = [(h["source"], h["path"]) for h in hits]
            material = "\n\n".join(
                f"[{i}] {h['path']}\n{h['text']}" for i, h in enumerate(hits, 1)
            )
            text, c = claude(
                ANSWER.format(ctx=", using only the material below",
                              question=q["question"],
                              material=f"\nMaterial:\n{material}"),
                "sonnet")
            row["answers"][arm] = text
            usd += c
        text, c = claude(
            ANSWER.format(ctx=" from what you already know", question=q["question"],
                          material=""), "sonnet")
        row["answers"]["none"] = text
        usd += c
        out.append(row)
        print(q["id"], f"${usd:.2f}", flush=True)
    (DATA / "answers.json").write_text(json.dumps(out, indent=1))


def grade():
    questions = {q["id"]: q for q in json.loads((DATA / "questions.json").read_text())}
    rows = json.loads((DATA / "answers.json").read_text())
    rng = random.Random(7)
    grades, usd = [], 0.0
    for row in rows:
        q = questions[row["id"]]
        arms = list(row["answers"])
        rng.shuffle(arms)
        labels = {arm: f"Answer {chr(65 + i)}" for i, arm in enumerate(arms)}
        text, c = claude(
            JUDGE.format(
                question=q["question"],
                facts="\n".join(f"{i}. {f}" for i, f in enumerate(q["facts"], 1)),
                answers="\n\n".join(
                    f"{labels[a]}:\n{row['answers'][a]}" for a in arms
                ),
            ),
            "opus",
        )
        usd += c
        verdict = json.loads(text[text.index("{"): text.rindex("}") + 1])
        verdict = {k.replace("Answer", "").strip(): v for k, v in verdict.items()}
        grades.append({
            "id": row["id"], "half": row["half"], "labels": labels,
            "facts": len(q["facts"]),
            "covered": {
                a: verdict[labels[a].replace("Answer", "").strip()] for a in arms
            },
        })
        print(row["id"], f"${usd:.2f}", flush=True)
    (DATA / "grades.json").write_text(json.dumps(grades, indent=1))


def report():
    grades = json.loads((DATA / "grades.json").read_text())
    rng = random.Random(0)
    for half in ("thread", "code"):
        rows = [g for g in grades if g["half"] == half]
        recall_of = {
            arm: [sum(g["covered"][arm]) / g["facts"] for g in rows]
            for arm in ("A", "B", "none")
        }
        diffs = [b - a for a, b in zip(recall_of["A"], recall_of["B"])]
        boots = sorted(
            sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(10000)
        )
        print(
            half, len(rows),
            {arm: round(sum(v) / len(v), 3) for arm, v in recall_of.items()},
            "B-A", round(sum(diffs) / len(diffs), 3),
            "95% CI", (round(boots[249], 3), round(boots[9749], 3)),
        )


{"answer": answer, "grade": grade, "report": report}[sys.argv[1]]()
