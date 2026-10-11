# ruff: noqa: E501, E741, B904, B905, B023, E402, SIM115
"""Turn each mined commit into a change request without file or code names.

Opus reads the commit's subject and diff (test files left out) and writes the
ticket a developer would have been handed, then says whether the commit is a
coherent change worth keeping (not a merge, rebase, version bump or grab bag).
"""

import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

import common

PROMPT = """You are building a benchmark for code-navigation agents. Below is one real commit from the {repo} repository of BC Registries (the British Columbia business registry, a set of repositories: lear = legal-api, colin-api, queue services, jobs; sbc-auth = auth-api and auth-web; sbc-pay = pay-api, pay-queue, bcol-api; business-filings-ui = Vue front end).

Commit subject: {subject}

Diff (test files omitted, may be truncated):
{diff}

Task 1: decide KEEP or DROP. KEEP only if the commit is one coherent behavior change (a feature, a fix, a business rule) whose files a developer could find by understanding how the system works. DROP merges, rebases, release roll-ups, version bumps, formatting, pure renames, dependency updates, or grab bags of unrelated tweaks.

Task 2 (only if KEEP): write the change request a developer would have been given, 2-5 sentences, describing the desired behavior and why, in product and domain terms. It must NOT contain file names, paths, function, class, variable, constant or table names, ticket numbers, or anything that could be grepped verbatim from the code. Name services and concepts in plain words (for example "the legal API", "the payment service", "the filing UI", "the COLIN synchronization job"). Do not say which repository.

Reply with only JSON: {{"verdict": "KEEP" or "DROP", "reason": "<one sentence>", "task": "<change request or empty>"}}"""


def diff_for(c):
    up = common.ROOT.parent / "hrono-eval" / "upstream" / c["repo"]
    files = subprocess.run(
        [
            "git",
            "-C",
            str(up),
            "diff",
            "--name-only",
            "--no-renames",
            f"{c['sha']}^1",
            c["sha"],
        ],
        capture_output=True,
        text=True,
    ).stdout.split()
    keep = [
        f
        for f in files
        if not re.search(r"(^|/)tests?/|test_|\.spec\.|\.test\.", f)
    ]
    d = subprocess.run(
        [
            "git",
            "-C",
            str(up),
            "diff",
            "--no-renames",
            "-U2",
            f"{c['sha']}^1",
            c["sha"],
            "--",
            *keep,
        ],
        capture_output=True,
        text=True,
    ).stdout
    return d[:40000]


def one(c):
    text = common.llm(
        PROMPT.format(repo=c["repo"], subject=c["subject"], diff=diff_for(c)),
        system="You write precise benchmark items. Reply with JSON only.",
        model="opus",
        role="describe",
    )
    m = re.search(r"\{.*\}", text, re.S)
    try:
        j = json.loads(m.group(0))
    except Exception:
        j = {"verdict": "DROP", "reason": "unparseable", "task": ""}
    return {**c, **j}


if __name__ == "__main__":
    cands = json.load(open(common.DATA / "candidates.json"))
    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(one, cands))
    json.dump(rows, open(common.DATA / "described.json", "w"), indent=1)
    keep = [r for r in rows if r["verdict"] == "KEEP"]
    print(len(rows), "kept", len(keep))
