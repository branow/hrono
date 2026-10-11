# ruff: noqa: E501, E741, B904, B905, B023, E402, SIM115
"""Write the architecture question set from the code alone (never from hrono).

One Opus agent per area explores the snapshot checkouts with Read, Grep and
Glob and writes questions a developer new to the system would ask, whose
answers are spread over many files: end-to-end flows, cross-repository
integration, and how a concept is modeled and enforced. Each answer is a list
of key facts, each with the files that prove it.
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import common

AREAS = {
    "lear-filings": "lear's legal-api: how a business filing (incorporation, change of address, annual report, dissolution, amalgamation, continuation...) moves from submission through validation, payment, processing and outputs",
    "lear-async": "lear's queue services, emailer, COLIN synchronization, scheduled jobs and data pipelines: what triggers them, what they consume and produce, how they connect to the legal-api",
    "auth": "sbc-auth: accounts/orgs, users, memberships, roles and permissions, affiliations of businesses to accounts, and the auth-web front end",
    "pay": "sbc-pay: fee schedules, invoices, payment methods (credit card, online banking, PAD, BC Online, EFT, internal), refunds, reconciliation, queues and jobs",
    "ui": "business-filings-ui: how the Vue front end is structured, how it loads a business and its filings, drafts and to-dos, and how it talks to the back-end APIs",
    "cross": "integration ACROSS repositories: how legal-api, auth-api, pay-api and the UIs depend on each other (authorization checks, fee/payment for filings, affiliations, notifications/events between services)",
}

PROMPT = """You are writing a benchmark that tests whether a coding agent understands the architecture of a large, unfamiliar codebase. The current directory holds four repositories of BC Registries (the British Columbia business registry): lear/, sbc-auth/, sbc-pay/, business-filings-ui/ (about 5,000 files).

Your area: {area}.

Explore the code in your area thoroughly with your tools. Then write {n} questions that a senior developer joining the team would ask, of these kinds:
- "flow": how something works end to end (a pipeline or lifecycle spanning several components);
- "concept": how a domain concept or cross-cutting rule is modeled and enforced across the code (where it lives, what enforces it, what depends on it);
- "change": where and how one would implement a described change, and what else it would affect.

Rules:
- Every question must need at least 4 different files to answer well, ideally across directories. No single-function or single-file lookups.
- Phrase questions in domain terms, as a newcomer would; do not put exact identifiers in the question text.
- The answer is 4-8 key facts. Each fact is one checkable sentence naming the concrete components (modules, classes, functions, queues, endpoints) and lists the file paths (relative to the current directory, e.g. lear/legal-api/src/...) that prove it. Only state what you verified in the code.

Reply with only a JSON array: [{{"kind": "flow|concept|change", "question": "...", "facts": [{{"fact": "...", "files": ["..."]}}]}}]"""


def gen(area):
    r = common.run_agent(
        PROMPT.format(area=AREAS[area], n=6),
        model="opus",
        role="gen-questions",
        key=area,
        max_turns=120,
        tools=["Read", "Grep", "Glob"],
        timeout=5400,
    )
    m = re.search(r"\[.*\]", r["answer"], re.S)
    qs = json.loads(m.group(0)) if m else []
    for i, q in enumerate(qs):
        q["qid"] = f"{area}-{i}"
        q["area"] = area
    print(area, len(qs), r["usage"], flush=True)
    return qs, r


if __name__ == "__main__":
    areas = sys.argv[1:] or list(AREAS)
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(gen, areas))
    for area, (qs, r) in zip(areas, res):
        json.dump(
            {"questions": qs, "raw": r},
            open(common.DATA / f"gen-{area}.json", "w"),
            indent=1,
        )
