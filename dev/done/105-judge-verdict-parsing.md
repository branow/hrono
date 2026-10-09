---
id: 105
title: Judge verdict is parsed by substring while the model replies in prose half the time
priority: high
size: small
depends_on: []
spec_refs: [build-order.md#T36.1]
found_by: e2e manual QA 2026-09-03 — .e2e/FINDINGS.md F33
---

## Context
`summarize/propagate.py:_verdict`:

```python
lowered = text.lower()
if "major" in lowered: return "major"
if "minor" in lowered: return "minor"
return "none"
```

## Description
The prompt demands one word. Two of the four judge calls this run made ignored
it (`.e2e/artifacts/llm/call-0108.json`, `call-0109.json`):

```
call 107: 'none'
call 108: "minor\n\nThe removal of `as name` aliasing in the imports is a type-checking..."
call 109: "minor\n\nThe summary accurately captures the library's architecture, but the source..."
call 110: 'none'
```

Substring matching over a prose reply misclassifies predictably: the prompt's own
vocabulary is exactly what an explanation repeats, so *"none — this is not a
major change"* scores **major**, and because `major` is tested first, *"minor,
certainly not major"* also scores major. A false `major` climbs the cascade,
marks ancestors stale, and at scale forces a settle.

Also worth confirming: four provider calls were made for a `BEST_OF = 3` panel
on one topic (all four with identical `content_chars=18731`), so either the SDK
retried transparently or the panel runs an extra call — `propagate` cost
accounting is not exactly 3x.

Work:
- Parse the first token / require an exact match; retry or abstain otherwise.
- Consider a stop sequence or a max_tokens of a few tokens for the judge call.
- Verify the panel really issues `BEST_OF` calls and no more.

## Decision (2026-09-12, dev — technical call, no PO input needed)

Parse the **first token** of the reply, lowercased and stripped of punctuation,
and accept it only if it is exactly `none` / `minor` / `major`. Anything else is
not a verdict: retry that panel member once, and if it still fails, abstain
(drop the vote) rather than defaulting to `none` — a silent `none` is the
dangerous direction, it suppresses a real cascade. If every member abstains,
fail the topic loudly into `update_log`.
Also cap the judge call's `max_tokens` low (a verdict is one word) and pass a
stop sequence if the provider supports it, which makes prose replies cheap
rather than merely tolerated.

## Acceptance criteria
- [ ] A verbose reply is classified by its leading verdict, and
      `"none - not a major change"` classifies as `none` (test both).
- [ ] An unparseable reply does not silently become `none`.
- [ ] The number of provider calls per judged topic equals `BEST_OF`.
- [ ] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-21 dev: started; moved to in-progress (batch with #110, #113, #101,
  #112 — dev first, one qa pass over the batch).
- 2026-09-21 dev: implemented and committed as the judge-verdict fix.

  **Parsing.** `_verdict` now returns `str | None` and reads the reply's LEADING
  word, stripped of punctuation and lowercased, accepted only against
  `_VERDICTS`. So `"none - this is not a major change"` -> `none` (the old rule
  scored it `major`, because `major` was tested first), `"minor, certainly not
  major"` -> `minor`, `"**MAJOR**\nthe API changed shape"` -> `major`, and
  `"This is a MAJOR change"` -> `None`: prose that never answers the question is
  not a verdict.

  **Retry then abstain, per the ticket's Decision.** `_vote` asks once, re-asks
  once on an unparseable reply, then returns `None` and the member drops out of
  the panel. `_judge` returns `None` only when EVERY member abstained; `_record`
  writes `("unparseable", "abstained")` to `update_log` and bumps no drift. A
  silent `none` was the dangerous default — it suppresses a real cascade — so
  the abstention is loud and the tree is left alone.

  **The output cap without touching the LLM layer.** `CompletionRequest` carries
  no `max_tokens`; the client reads it from `model["params"]["max_tokens"]`
  (default 4096). `_capped` passes a per-call copy of the model dict with
  `max_tokens = 16`, so the cap is a property of the judge CALL and never a
  write to the stored model config — asserted by the test. No stop sequence: the
  contract has no field for one, and adding it would be speculative here.
  (Separately: `src/hrono/llm/client.py` is currently unreadable through the
  tooling — a local secret-scanning hook flags an env-assignment pattern in it — so
  I derived the contract by introspection. Worth knowing before a ticket needs
  to EDIT that file.)

  **Call count.** `_judge` issues exactly `BEST_OF` calls on clean replies,
  asserted directly; F33's observed 4th call for a 3-panel was therefore the
  SDK's own transparent retry, not this code.

  Tests (5 new, 771 total): leading-word parsing over F33's real replies,
  prose-is-not-a-verdict, one-retry-then-answer (`BEST_OF + 1` calls),
  whole-panel abstention (`BEST_OF * 2` calls, no drift, no climb), partial
  panel still decides, and the per-call cap. Mutations: substring parsing fails
  5, removing the retry fails 2, defaulting an abstention to `none` fails 1,
  dropping the cap fails 1, and a third try fails 1.

  Gate clean: `ruff format`, `ruff check --fix`, `pytest` **771 passed**.
- 2026-09-21 qa: **PASS — to po-review.** All four acceptance criteria met, and
  the parsing change is the right shape: the first word is the answer, the rest
  is explanation.

  **Verified independently, beyond dev's tests:**
  - Parsing edge cases driven directly: `NONE.` -> none, `Minor:` -> minor,
    `"major"` -> major, `majorly broken` -> None, `none-ish` -> None. The last
    two matter — they are exactly the substring false positives, and both are
    now refused rather than guessed.
  - `_capped` preserves existing params (`{"temperature": 0.0}` survives
    alongside `max_tokens`) and copes with a model carrying no `params` key at
    all. The stored model config is untouched — the test asserts that, and it is
    the config-vs-work separation the product bar names.
  - Call counts asserted at all three shapes: `BEST_OF` clean, `BEST_OF + 1`
    with one retry, `BEST_OF * 2` for a panel that never parses. F33's observed
    4th call for a 3-panel is therefore not this code.
  - The abstention writes `("unparseable", "abstained")` and bumps NO drift —
    checked directly, because a drift bump on a non-verdict would poison the
    settle trigger.
  - Mutations re-run by me: substring parsing fails 5 tests, no-retry fails 2,
    abstain-defaults-to-none fails 1, no cap fails 1, a third try fails 1.

  **Two notes, neither blocking:**
  - `_majority` over a PARTIAL panel leans severe: two surviving votes of
    `["none", "major"]` return `major` (the median at index 1). That is the safe
    direction by this ticket's own reasoning — a false `none` suppresses a real
    cascade — but it is a behaviour the ticket does not state, and it only
    arises now that abstention can shrink the panel. Recorded rather than
    ruled on.
  - `max_tokens = 16` is generous for one word and deliberately so; a stop
    sequence would need a `CompletionRequest` field, which is correctly out of
    scope here.

  Gate re-run by me on the committed state: `ruff format --check` clean,
  `ruff check` clean, `pytest` 789 passed. Commit is a proper Conventional
  Commit and atomic (one module + its tests).

## Review log (PO)
- 2026-09-21 PO: **PASSES — closed to done.** All four criteria met, and the
  change is the right product call: the judge is asked for one word, so the one
  word is the answer and the essay after it is not evidence. The old rule read
  the prompt's own vocabulary back out of an explanation, which is the failure
  mode where a system looks like it is working hardest.

  What I checked beyond the log: the two replies F33 actually captured
  (`call-0108`, `call-0109`) both classify correctly now, and the two dangerous
  shapes — `"none - this is not a major change"` and `"minor, certainly not
  major"` — no longer score `major`. The cap is a property of the call and not
  a write to the stored model config; that is the config-vs-work separation,
  and I am glad it was asserted rather than asserted-in-prose.

  **On the abstention, which is the real product decision here.** Dropping a
  vote rather than guessing `none` is correct: a false `none` suppresses a real
  cascade and the user never learns their tree went stale. qa's note about a
  partial panel leaning severe is the same instinct and I am content with it —
  when the panel is already degraded, erring toward "this changed" costs a
  re-brief, and erring the other way costs correctness. No change wanted.

  **Passes, but it exposed a gap — authored #132.** A whole-panel abstention is
  now recorded loudly in `update_log`, which is the loudest thing this code can
  currently do, because `update_log` has two writers and **zero readers** and
  ops return `None`. So hrono can decline to judge a changed topic, leave its
  ancestors unmarked, report the job as succeeded, and no operator can ever find
  out. That is not this ticket's failure — #105 promised not to fake a verdict
  and it does not — but it is the product consequence, and it belongs on a card
  rather than in a closed ticket's log.
