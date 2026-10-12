# ruff: noqa: E501
"""Write hard architecture questions: what an agent gets wrong in a real system.

Round 3 (docs/evaluations/2026-10-bc-registries-v2/) found "how does X work"
questions answered by a strong agent with grep: the answer sits in the files
the question's words lead to. The mistakes agents make in a real system come
from what is NOT in those files: a second implementation of the same rule,
another service that depends on a behaviour, a check made in one place and
missing in another. One Opus agent per theme explores the checkout (never
hrono) and writes questions whose answer needs that wider context. They are
then verified (verify.py) and calibrated: a code-only agent answers each
once, and the ones it does worst on are kept.

Writes data/gen-hard-<theme>.json.

Usage: python3 gen_hard.py [THEME ...]
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import common

THEMES = {
    "inconsistency": "one business rule or invariant implemented in two or more places (front end and back end, two services, two API versions, a job and an endpoint) where the implementations disagree, drift, or cover different cases",
    "authorization": "how access is enforced across services and entry points: which paths check permissions, which rely on another service or on the UI to have checked, and where a caller could do something the rules elsewhere would forbid",
    "impact": "a realistic change in one place (a renamed status, a new entity or filing type, a changed message or payload shape, a changed fee rule) and everything across the repositories that must change with it or would silently break",
    "failure": "a flow that spans services (payment and filing, queues, scheduled jobs, emails) and where a step can fail or repeat halfway: what partial or inconsistent state results, what retries or duplicates happen, and what, if anything, repairs it",
    "legacy": "two implementations of the same job (an old and a new service, a v1 and a v2 API, a queue listener and a job): which is live for what, how they differ in behaviour, and what goes wrong if one is changed and not the other",
}

PROMPT = """You are writing the hardest part of a benchmark that tests whether a coding agent understands a large, unfamiliar enterprise codebase well enough to work in it safely. The current directory holds four repositories of BC Registries (the British Columbia business registry): lear/, sbc-auth/, sbc-pay/, business-filings-ui/ (about 5,000 files).

Theme: {theme}.

Explore the code thoroughly. Then write {n} questions a senior engineer would need answered before making a change or signing off a security review, on this theme. A strong agent that greps for the question's words and reads the few files it finds must get them WRONG or badly incomplete: the answer must depend on code the question's words do not lead to (another service, another repository, the other implementation, the caller, the consumer).

Rules:
- Each answer needs at least 6 files from at least 2 different services or repositories.
- Phrase each question as an engineer would, in domain words; never put an identifier, file, class, function, endpoint, queue or status name in it.
- The answer is 5-8 key facts. Each fact is one checkable sentence naming the concrete components and lists the file paths (relative to the current directory) that prove it. Only state what you verified in the code; include the non-obvious facts (the disagreement, the missing check, the second place) that make the question hard.

Reply with only a JSON array: [{{"kind": "{kind}", "question": "...", "facts": [{{"fact": "...", "files": ["..."]}}]}}]"""


def gen(theme):
    r = common.run_agent(
        PROMPT.format(theme=THEMES[theme], n=2, kind=theme),
        model="opus",
        role="gen-hard",
        key=theme,
        max_turns=120,
        tools=["Read", "Grep", "Glob"],
        timeout=5400,
    )
    m = re.search(r"\[.*\]", r["answer"], re.S)
    qs = json.loads(m.group(0)) if m else []
    for i, q in enumerate(qs):
        q["qid"] = f"hard-{theme}-{i}"
        q["area"] = f"hard-{theme}"
    (common.DATA / f"gen-hard-{theme}.json").write_text(
        json.dumps({"questions": qs, "raw": r}, indent=1)
    )
    print(theme, len(qs), r["usage"]["cost_usd"], flush=True)
    return qs


if __name__ == "__main__":
    themes = sys.argv[1:] or list(THEMES)
    with ThreadPoolExecutor(5) as ex:
        list(ex.map(gen, themes))
