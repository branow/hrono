---
id: 197
title: UX review — can a human actually use this?
priority: high
size: medium
depends_on: []
spec_refs: []
---

## Context
1404 tests pass and every ticket is done. None of that answers whether a person
who has never seen hrono can install it, point it at a repo, and get an answer
— or whether the dashboard is a page you can click.

## Description
Walk it as a new user, from an empty directory, on a REAL repository with REAL
embedding weights, and drive the dashboard in a real browser rather than with
curl. Record everything that is confusing, broken, or merely strange.

## Acceptance criteria
- [ ] First run from nothing: what does a person see, and is it enough?
- [ ] The CLI's help, error messages and output read like a tool, not a trace.
- [ ] A real source ingests, embeds and clusters.
- [ ] Every dashboard page renders and every control does what it says.
- [ ] Findings written up with severity, and anything cheap fixed.

## Review log
- 2026-09-28 po: authored at the user's request — "check that a human can click
  it and it does a job".

## Findings (2026-09-28)

Walked from an empty directory to a built tree over **hrono's own repository**
(394 sections, 3639 passages) with **real MiniLM weights**, and drove the
dashboard in a real browser. What works, honestly: the pipeline built a
26-topic tree three levels deep with nothing parked; recall answered "how does
the master key get rotated" with `crypto/rotate.py` in 124 ms; export wrote 423
navigable files; a rename typed into the dashboard landed in the store, pinned
the brief, and came back green; a reader saw no edit panel and a forged POST
got 403.

### Blockers for a new user

1. **You cannot start it.** `hrono serve` says "No master key provided. Supply
   it with --key-file <path> or the HRONO_MASTER_KEY environment variable" —
   and nothing anywhere says how to MAKE one. The README never mentions a
   master key; `serve --help` lists `--key-file <path>` with no description;
   there is no command that generates one. I had to write a Fernet one-liner
   in Python. A person who has just installed this is stuck at the first step.
2. **The CLI throws the server's error away.** `hrono sources set` on a config
   with a missing field prints exactly `invalid body`. The server sent
   `details.errors` naming the field and the reason — `client/http.py:_detail`
   reads only `error.message` and drops the rest. Two words, no next step.
3. **Nothing teaches a config shape.** `sources set --help` says "JSON config
   file, or stdin" and stops. No example, no schema, no `--example`. Combined
   with (2), the second step is unlearnable from the tool.

### The map's main affordance does not work

4. **The "+" on a closed topic intercepts its own click.** The page says "click
   a topic to open or close it"; the `+` is drawn dead centre on the circle
   (`<text class="more">` over `cx=40 cy=40`) and swallows the pointer, so
   clicking the most inviting pixel does nothing. Playwright's click timed out
   on it, which is exactly what a person's mouse does. One CSS line.
5. **Long topic labels are clipped off the left edge.** Labels are
   centre-anchored under the first column at `x=MARGIN` (40), so anything wider
   than 80px runs to negative x and the SVG cuts it. The root's label rendered
   as "…up covers Summarize,".

### Costly failures that could be cheap

6. **`tree maintain` spends the whole ingest and embed budget before checking
   it can brief.** With no text model configured it cloned, split 394 sections
   and embedded 4321 vectors — minutes — then failed with `llm-error: no text
   model available`. The precondition is knowable at second zero. (The work IS
   kept, which is the saving grace, but nothing tells the user that either.)
7. **A build failed once with `cluster-error: clustering produced no clusters`
   and succeeded on the next identical run.** Not reproducible on demand; the
   same 394 vectors clustered into 26 topics when I ran the recipe directly.
   Unexplained, and the message gives an operator nothing to do. Needs its own
   investigation — recorded rather than guessed at.
8. **Registering a local embedding model reports a timeout and then succeeds.**
   Validation loads the real weights, which takes longer than the client's 10s
   budget, so the user sees "did not answer within 10s" for a write that
   landed. The message is honest (#168's wording) but leaves them not knowing
   whether to retry.

### Leaks and polish

9. **Internal ticket numbers are shown to users.** The triage page — the most
   demo-able screen — prints "a subtree that is not in the export (#124,
   #163)" and "forced in rather than matched (#113)". `serve --help` carries
   "(#098)".
10. **The runs table has no time and no job id**, so three `maintain` rows are
    indistinguishable and nothing cross-references `hrono jobs get`.
11. **Child topics are listed as bare ids** ("topic 27", "topic 28") on the
    topic page, though every one has a title the map already shows.
12. **A truncated title just stops** — `_titled` cuts at 80 characters with no
    ellipsis, so the heading read "…higher. It also touches".
13. `<form>` nested inside `<p>` on the overview: invalid HTML, and the browser
    leaves two phantom empty paragraphs in the accessibility tree.
14. **No favicon** — every page load logs a 404, and a tab shows a broken icon.
15. **The overview is one sentence and a button.** The spec wanted the front
    page to be the triage queue; triage lives on its own page and the front
    page says "29 topic(s) across 3 level(s)".
16. `hrono jobs list` is oldest-first, so the job you just started is at the
    bottom; the dashboard's runs view is newest-first. Same data, opposite
    order.
17. **Recall's output is dominated by `sp:` structure paths** — one hit's
    header carried nine `sp:/.string/.string_content/.~blank-line[2]/.~line`
    fragments before the content. For an agent that may be fine; on a terminal
    it buries the answer.
18. No `--version`.
19. The bootstrap message tells you how to use the CLI and the API and never
    mentions that a **dashboard** is running at `/ui`.

## Fixed (2026-09-28), each with a test and a killed mutation

1, 2, 3 (first run) — `hrono admin new-key` writes a 0600 key and refuses to
overwrite one; `KeyNotProvided` names it and `hrono serve --key-file`;
`--key-file` has help text; the README opens with the three commands.
2 (errors) — `client/http.py` renders `details.errors` as `field: reason`
lines. The guess that started this review now answers "git.auth: Field
required".
4, 5 (map) — `pointer-events: none` on the `+`, verified by re-driving the
click in Playwright (it timed out before, it navigates now); `MARGIN` 40 -> 90
and labels fitted to `LABEL_CHARS`, so nothing is clipped or collides.
6 — `maintain` resolves the embedding model and all three text roles before
the first source is cloned, and says which role is missing.
9 — ticket numbers out of `triage.py` and `serve --help`; a test greps the
page for `(#\d+)` so they cannot come back.
10, 11, 12, 13, 14, 19 — runs table has started/took/id; children listed by
title; a clipped title ends at a word with an ellipsis; the `<form>` came out
of the `<p>`; a favicon; the boot message points at `/ui`.

Also improved while there: the map legend was one run-on sentence — the
toggles are chips and the colour key is a list.

## Not fixed, and why

- **7 — the non-deterministic `clustering produced no clusters`.** One
  occurrence, not reproducible: the same 394 vectors clustered into 26 topics
  when I ran the recipe directly, and the next identical `maintain` succeeded.
  Guessing at a cause would be worse than recording the evidence. Its own
  ticket, with the corpus kept.
- **8 — registering a local embedding model reports a timeout and succeeds.**
  The 10s client budget against a first weight-load is a real mismatch, but the
  fix is a judgement about which writes get a longer budget, not a one-liner.
- **15 — the overview is one sentence.** The spec wants the front page to be
  the triage queue; triage exists on its own page, so this is a layout decision
  rather than a defect.
- **16 — `hrono jobs list` is oldest-first** while the dashboard is
  newest-first. Changing the CLI's order is a small breaking change to anyone
  scripting it; worth doing, worth saying out loud first.
- **17 — recall's `sp:` paths dominate its output.** They are addressing data
  an agent may want and a human never does; the fix is a `--verbose` split, and
  that is a CLI design decision.
- **18 — no `--version`.**
