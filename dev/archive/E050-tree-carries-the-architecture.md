---
id: E050
title: the tree carries the architecture — code grouped by what it does, briefs that explain it
priority: high
depends_on: []
requirements: []
---

## Goal
On a large, unknown corpus the tree does not help an agent answer
architecture questions. The agent A/B on BC Registries
(`docs/evaluations/2026-10-bc-registries-agents/`) measured it: fact
coverage was 0.692 with the code alone and 0.649 with the code plus hrono,
and an agent with only the tree scored 0.498. Two questions were then traced
through the tree (findings E23–E29 in
`docs/evaluations/2026-10-bc-registries/findings.md`). The information is
in the tree, but it is scattered, mixed with tests and boilerplate, and
never put together into an explanation.

The approach was chosen on 2026-10-12 from three pilots (see Log). The
tickets state the problems and how to tell whether they are fixed.

## Tickets

### 501 core code is not clustered with build, test and fixture files (E23)
Problem: core service code lands in leaves about other kinds of file. The
payment listener and the filer worker sit in a "python test suites helpers"
leaf. The future-effective job sits in "Dockerfile summaries" and "17
Makefiles". `models/filing.py` sits in "corpus fixtures".
Done when:
- [ ] on `bcreg`, each file of the `lear-filings-1` and `pay-3` answers
  sits in a leaf whose title names its service or feature
- [ ] no leaf mixes product code with tests, fixtures, or Docker, Make or CI
  files

### 502 one service is not scattered across the tree (E26)
Problem: the files that answer `pay-3` (pay-api, pay-queue, payment jobs)
sit in about 12 leaves under 5 top groups, one of them "lear ecosystem".
One file can be split across 3 leaves in different groups.
Done when:
- [ ] the files of one service sit under one top-level branch
- [ ] a file's sections are not spread over unrelated groups

### 503 a flow that crosses components is stated somewhere (E24)
Problem: "payment confirmed → filer queue → entity-filer applies the
filing; future-effective filings wait for a job" is stated by no brief at
any level. Its pieces live in five unrelated leaves.
Done when:
- [ ] reading root and at most 2 briefs below it gives the components and
  the order of the `lear-filings-1` flow

### 504 briefs explain behaviour instead of cataloguing files (E25, E28)
Problem: leaf briefs walk through files one by one (licence, gunicorn,
WSGI, Sentry, env defaults) and list identifiers without saying what they
do ("`unlock_frozen_accounts`, `delete_account`, `enable_eft` and the fee
methods"). The concept "account lock: set on NSF or overdue, blocks new
invoices, lifted by a card payment" is stated nowhere.
Done when:
- [ ] the leaf covering the pay-api account service states the account
  lock concept in one or two sentences
- [ ] boilerplate (licence, server config, env defaults) takes at most a
  line per brief

### 505 root and its children route (E17, E19, E27)
Problem: the top split with 4 levels has 2 children, and both say "the BC
Registries ecosystem". With `--levels 3`, root's 25 groups include 3
SchemaSpy groups, 2 Postman groups and "AJV internals". Some titles come
from boilerplate, such as
`apache-2-0-licensed-source-files-2024-province-of-british-co`.
Done when:
- [ ] given root alone, an agent picks the right branch for `lear-filings-1`
  and `pay-3`
- [ ] no title or node URI is meta text or a licence header

## How to check
- Trace by hand: `lear-filings-1` and `pay-3` from
  `docs/evaluations/2026-10-bc-registries-agents/data/arch.json`, plus 2–3
  others, through `hrono tree export bcreg --levels 3`.
- Then a few agent runs with the harness in that folder (`tree-L3` arm,
  code plus tree, Sonnet), and only after that the full 36-question suite.

## Out of scope
- recall quality (tested separately)

## Log
- 2026-10-11: created from the BC Registries agent A/B and two hand traces;
  solution left to the user.
- 2026-10-12: dropped 506 (E29): the "secret" was a test fixture value that
  the operator's canary hook flags; not a product problem.
- 2026-10-12: approach chosen and built, from pilots on `bcreg`:
  - clustering vector 0.6 x condensation embedding + 0.4 x leading folders
    weighted 1/depth, granite embeddings
    (`docs/evaluations/2026-10-cluster-formula/`), for 501 and 502;
  - condense `purpose-decisions`, leaf brief `core-states`, upper brief
    `area-flows` (`docs/evaluations/2026-10-condense-prompts/`,
    `docs/evaluations/2026-10-brief-prompts/`), for 503 and 504;
  - full rebuild started into `~/hrono-eval/db/hrono-v2.db` (server on port
    8789, profile `v2`); the old tree stays as the baseline.
  - Open: 505 untested; `update` places new sections before condensing
    them, so incremental placement reads raw content until the next
    rebuild; TAU (0.70) was set for the old vector space.
