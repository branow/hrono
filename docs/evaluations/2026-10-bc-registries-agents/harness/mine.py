# ruff: noqa: E501, E741, B904, B905, B023, E402, SIM115
"""Mine post-snapshot commits whose changes span several pre-existing files."""

import json
import re
import subprocess
from pathlib import Path

UP = Path.home() / "hrono-eval" / "upstream"
CORPUS = Path.home() / "hrono-deep" / "corpus"
REPOS = ["lear", "sbc-auth", "sbc-pay", "business-filings-ui"]
NOISE = re.compile(
    r"(^|/)(tests?|__tests__|spec|e2e|cypress|migrations?|devops|\.github|openshift|docs?)/|"
    r"(test_|_test\.|\.spec\.|\.test\.|conftest)|"
    r"(package(-lock)?\.json|requirements.*\.txt|poetry\.lock|pyproject\.toml|version\.py|CHANGELOG|\.md$|\.lock$|setup\.cfg|\.ya?ml$|\.env|Dockerfile|Makefile)"
)


def git(r, *a):
    return subprocess.run(
        ["git", "-C", str(UP / r), *a], capture_output=True, text=True
    ).stdout


out = []
for r in REPOS:
    for line in git(
        r,
        "log",
        "--first-parent",
        "--since=2024-09-28",
        "--until=2025-04-30",
        "--reverse",
        "--format=%H\t%cs\t%s",
        "HEAD",
    ).splitlines():
        sha, date, subj = line.split("\t", 2)
        stat = git(
            r, "diff", "--name-status", "--no-renames", f"{sha}^1", sha
        ).splitlines()
        mod = [l.split("\t")[1] for l in stat if l.startswith("M\t")]
        mod = [
            p for p in mod if not NOISE.search(p) and (CORPUS / r / p).exists()
        ]
        add = [
            l.split("\t")[1]
            for l in stat
            if l.startswith("A\t") and not NOISE.search(l.split("\t")[1])
        ]
        dirs = {str(Path(p).parent) for p in mod}
        if 3 <= len(mod) <= 15 and len(dirs) >= 2:
            out.append(
                {
                    "repo": r,
                    "sha": sha,
                    "date": date,
                    "subject": subj,
                    "modified": mod,
                    "added": add,
                    "n_dirs": len(dirs),
                }
            )
json.dump(
    out, open(Path.home() / "hrono-deep/data/candidates.json", "w"), indent=1
)
from collections import Counter

print(len(out), Counter(c["repo"] for c in out))
for c in out[:40]:
    print(
        c["repo"], c["date"], len(c["modified"]), c["n_dirs"], c["subject"][:80]
    )
