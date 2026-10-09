---
id: 171
title: the engineering conventions live in a gitignored file and reach nobody
priority: medium
size: small
depends_on: [170]
spec_refs: []
---

## Context
From #170's qa review and the PO ruling on it.

`CLAUDE.md` opens by saying what it is: "**local-only working memory** for
development. It is listed in `.gitignore` and must **never be committed**.
Anything meant to be shared belongs in the repo's real docs, not here."

It is also where every engineering convention this board has learned now lives:

- the SEAM rule and its real-SIZE extension (#094, #108, #166, #168);
- mutation-checking, and what a surviving mutation means (#125, #128, #162,
  #163, #166, #168);
- fixtures must write what production writes (#144, #125, #126, #128);
- the URI decision and why fragments were rejected (#144);
- the baked operating constants and where they came from;
- the code-quality rules the `engineering:*` skills are held to.

None of that is working memory. It is how the codebase is built, each line of
it was learned from a defect that cost a round or more, and by the file's own
rule it is in the wrong place. Today it survives exactly as long as one working
copy of one machine — a fresh clone gets none of it, and neither does anyone
else.

## What it needs
- A committed home for the durable conventions. `CONTRIBUTING.md` and
  `docs/conventions.md` are the obvious candidates; the repo has neither yet.
- `CLAUDE.md` keeps what it says it keeps — current position, local paths, the
  throwaway-prototype pointer, anything genuinely per-machine — and POINTS at
  the committed doc rather than restating it. A convention in two places drifts.
- Each convention keeps its ticket citations. They are the evidence, and a rule
  whose reason is lost gets deleted by the next person who finds it
  inconvenient.

## For the stakeholder to decide
Which file, and whether the conventions are for this repo's contributors only
or belong in its public docs. The PO authored this rather than acting, because
it is a question about the project's shape.

## Acceptance criteria
- [x] The durable conventions live in a COMMITTED file, with their citations.
- [x] `CLAUDE.md` points at it and no longer duplicates it.
- [x] Nothing that is genuinely local (paths, current ticket) moves.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-26 po: authored from #170's qa review.

- 2026-09-26 dev: done, commit 44ccdc6. `CONTRIBUTING.md`, committed, carrying
  the eleven convention bullets moved VERBATIM with all nine ticket citations
  intact (#094, #108, #125, #128, #144, #162, #163, #166, #168) — they are the
  evidence, and a rule whose reason is lost gets deleted by the next person who
  finds it inconvenient.

  **The ticket named the symptom; the mechanism was one line down.**
  `.gitignore` is deny-by-default — `*` on line 2, then a whitelist of the five
  root files the repo tracks. So `CLAUDE.md` is not ignored by a rule about
  `CLAUDE.md`; NOTHING at the root is tracked unless it is named. Creating
  `CONTRIBUTING.md` changed nothing until it was added to that list, which I
  only found because `git check-ignore` said so after I had written the file
  and assumed it was done.

  That also answers the ticket's open question better than either option it
  offered. The choice was never "which file" — it was that the repo carries
  five root files and nobody had decided the conventions were a sixth.

  **The decision I made, and it is reversible in one line.**
  `CONTRIBUTING.md` over `docs/conventions.md`: it is where a contributor looks
  without being told, and the repo has no `docs/` to start one for. Linked from
  the README so it is reachable rather than merely present.

  **The one thing I would not do blindly.** `CLAUDE.md` is auto-loaded each
  session and `CONTRIBUTING.md` is not, so moving the rules out and leaving
  nothing behind would have made them LESS visible to the agent that has to
  follow them — the opposite of the ticket's point. `CLAUDE.md` now carries a
  pointer that says to read it and says why the rules moved, and keeps only
  what it describes itself as keeping: this machine's paths, the ticket in
  flight, the spec pointers.

  Gate clean: 1174 passed, 2 skipped. Nothing in `src/` or `tests/` changed.

- 2026-09-26 qa: PASS, to po-review. I verified the thing the ticket is
  actually about rather than the file existing: **cloned the repo into a temp
  directory and read what arrives.**

      $ git clone . /tmp/clone-check && ls
      CONTRIBUTING.md  README.md  pyproject.toml  src  tests  uv.lock
      $ grep -o "#[0-9]\{3\}" CONTRIBUTING.md | sort -u
      #094 #108 #125 #128 #144 #162 #163 #166 #168
      $ ls CLAUDE.md
      (absent, as designed)

  Nine citations, all of them, in a clone that has never seen this machine.
  That is the whole ticket, and until the `.gitignore` line it would have been
  a file nobody else ever sees — dev is right that writing the file was the
  easy half and finding the deny-by-default whitelist was the ticket.

  Gate at 44ccdc6: ruff clean, 1174 passed, nothing under `src/` or `tests/`
  touched.

  The judgement I want to endorse is the one about visibility. The literal AC
  said `CLAUDE.md` should "no longer duplicate it", and a literal reading would
  have left the agent that must FOLLOW these rules no longer reading them —
  `CLAUDE.md` is auto-loaded, `CONTRIBUTING.md` is not. A pointer that says
  read it, and says why they moved, satisfies the criterion and the intent. A
  test would not have caught the difference; only asking what the rule is FOR
  does.

- 2026-09-26 po: CLOSED. Everything this project has learned about how to build
  it now survives a clone. It did not yesterday.

  **The stakeholder question I handed up came back answered by the code.** I
  authored this saying "which file, and whether these are contributor-facing or
  public" was a decision about the project's shape and not mine to make. It was
  the wrong question. `.gitignore` is deny-by-default with a whitelist of five
  root files — so there was never a choice between locations, only a fact that
  nobody had decided the conventions were worth tracking. Naming the real
  mechanism turned a decision into an obvious line.

  I am recording that because I will hand something up again: a question that
  looks like it needs a stakeholder sometimes needs ten more minutes of
  reading. Dev found it with `git check-ignore` after writing the file and
  assuming the job was done.

  The one genuine judgement — `CONTRIBUTING.md` over a new `docs/` — is
  conventional, reversible in one line, and linked from the README so it is
  reachable rather than merely present. If the stakeholder wants it elsewhere
  it is a `git mv`.

  And dev declining the LITERAL acceptance criterion in favour of its intent
  was right. "CLAUDE.md no longer duplicates it" read strictly would have left
  the agent that must follow these rules no longer reading them, since
  `CLAUDE.md` is auto-loaded and `CONTRIBUTING.md` is not. The criterion was
  written to stop DRIFT between two copies, not to hide the rules; a pointer
  that says read this, and why it moved, serves both.

  Board is clear. Nine of the ten remaining backlog items are hygiene or
  YAGNI-gated; the two that matter — #051's job DAG and #077's ANN shadow
  index — are DESIGN work that wants a milestone and, for #077, a measurement
  before any code.
