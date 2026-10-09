---
id: 207
title: ask a question in the panel — recall with its evidence
priority: high
size: medium
depends_on: []
spec_refs: [REQUIREMENTS.md#5 (31-34)]
---

## Context
Recall is one of the product's two doors and it is reachable only from the CLI and the API. Confirmed: the panel is a place to ask, for every role.

## Description
An Ask page. Type a question; see what `POST /trees/{name}/recall` returns, as an agent would receive it.

Each passage shows its text, its source file and position, its score, and the topic it belongs to, linked to the topic page. When nothing clears the confidence floor, say so plainly and offer the topics to explore instead — that strictness is the design, and the page must not make it look like a failure.

The question is in the URL, so an answer can be shared. Keep the last few questions of the session for comparing before and after a fix.

If the embedding backend is not installed or not loaded, the page says what to do rather than showing a 503.

## Acceptance criteria
- [ ] a reader can ask and gets passages with source, score and owning topic
- [ ] a no-answer question shows the refusal as a result, with where to look next
- [ ] the URL reproduces the result
- [ ] missing embedding backend produces an actionable message
- [ ] driven in a real browser against real weights, with one answerable and one unanswerable question

## Out of scope
Generating a prose answer with an LLM. Logging what agents ask.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
- 2026-10-03 dev: started (moved late — code was in flight when the session was rate-limited).
- 2026-10-03 dev: done in 0907d7e. `recall/ask.py` is the one door both the API's `POST /trees/{n}/recall` and the page call (resolve the embedding model, take the query encoder only if loaded, run the recipe). Hits gain `start`/`end` (byte range) and `topic` (a source passage's leaf topic in this tree; a brief passage's own node) — additive to the API. Page `/ui/trees/{t}/ask?q=` (Reader, "Ask" tab; GET, so the URL is the answer): search box; each passage as an agent receives it — kind (source/brief), file path, structure path, bytes, version, fused score, "in <topic>" linked to the topic page, full body; a refusal is a result ("Nothing here answers that confidently ... That is the answer an agent gets too") with the topics under the root as links and the map; a still-loading model says so with "Ask again"; a missing/broken backend says what to install (`pip install 'hrono[embed]'` / `uv sync --extra embed`) and points to Settings — page stays 200; the last 6 questions this browser asked are kept in a cookie and shown as links. Tests (tests/server/test_ui_ask.py, over a maintain-built tree with a deterministic text-hash encoder, as a READER): passages with source/bytes/score/topic; the page shows exactly the API's hits and topics; refusal with topics to explore; URL reproduces the passages; history order + cookie; loading and missing-backend messages (200); a brief passage renders with its own topic. Mutations, all KILLED: topic always None; no explore list on refusal; history not updated; Unavailable not caught; EmbedError not caught; brief passage topic None (survived first — fixed with the brief-passage test). Real browser + REAL WEIGHTS (sentence-transformers all-MiniLM-L6-v2 from the local HF cache, uvicorn, Chromium, signed in as a reader, tree of six distinct docs): "How long does a session token last?" -> 1 passage, auth.md bytes 0–152, the token-expiry text, its topic linked; "What is the capital of Mongolia?" -> the refusal with two topics to explore; a shared URL for "How are uploads stored?" opened directly -> storage.md first. Screenshots: .autodev/board/evidence/207/ask-0.png (answer), ask-1.png (refusal), ask-800.png (800px). Topic titles in the shots all read alike because the build used a stub writer — #212's subject. Gate: clean, 1662 passed.
- 2026-10-03 qa: KICKBACK (tests only, two small gaps; the feature works). Gated 0907d7e in a worktree (import path asserted inside it, bytecode off): ruff format --check clean, ruff check clean, pytest 1662 passed / 4 skipped. Drove it in Chromium as the READER on a copy of the local test database, worktree server: first with the main venv (no sentence-transformers) -> every question gives "Recall cannot run on this server yet … in-process embedding backend is not installed" with the install command and a Settings link, page 200 (AC 4, seen for real). Then with the embed extra and REAL weights (all-MiniLM-L6-v2, offline cache): "How do I make an option prompt the user for a password?" -> 10 passages, first docs/option-decorators.md "Password Option" bytes 213–963, score, "in <topic>" linked; `POST /trees/click/recall` with the same question -> the same 10, same first hit/bytes/topic 4. "What is the capital of Mongolia?" -> the refusal as a result with the 7 top topics + map link. `<script>alert(1)</script>` as a question -> escaped, no script in the DOM. The shared URL opened in a fresh session (800px) reproduces the first passage; "Asked before" lists the three most recent first; 800px no overflow (1440px's 4px is #215's shell defect). Screenshots in evidence/207-qa/. Re-ran dev's "topic always None" -> killed (3 tests).
  FINDING — two behaviours the page has and claims are unguarded; both mutations leave tests/server/test_ui_ask.py green (8 passed):
  (1) the kind chip: src/hrono/server/ui/ask.py:107 `"kind": "brief" if hit.kind == "summary" else "source"` -> `"kind": "source"` survives, though the Review log says "a brief passage renders with its own topic" — that test checks the topic, not that it is labelled a brief. An agent-facing view that labels a brief as source text misleads the reader about what they are looking at. Assert the chip text in the brief-passage test and in a source-passage test.
  (2) the history cap: removing `[:HISTORY]` at ask.py:50 and :149 survives. The cap is what keeps the cookie under the browser's ~4 KB limit — past it the browser silently drops the cookie and the whole history disappears. Add a test that asks HISTORY+2 distinct questions and asserts the page lists exactly HISTORY, newest first, and the cookie holds no more.
  Re-run both mutations after and state them killed.
  Polish, not blocking: the `sp:` path is shown URL-encoded (`sp:/Options%20Shortcut%20Decorators/Password%20Option`); decoding it would read as the heading it is. In a first card the score wraps under the path at 1440px.
- 2026-10-03 dev: kickback fixed in c8d2fea. (1) `test_each_passage_is_labelled_as_what_it_is`: a node passage renders kind "brief" and a git passage "source" through the page's own `_shown`, and the answer page carries the `source` chip. (2) `test_the_history_keeps_only_the_newest_few`: HISTORY+2 questions -> the cookie holds exactly the newest HISTORY, newest first, and the page lists exactly those; plus `test_a_long_history_cookie_is_read_only_as_far_as_the_cap` for the read side (the cookie is browser input; an older or edited one is cut to the cap). Mutations re-run, all KILLED: kind always "source"; no cap on write; no cap on read. Polish taken: the `sp:` path is shown decoded; the score no longer wraps (`nowrap`). Gate: clean, 1670 passed.
- 2026-10-03 qa: PASS at c8d2fea (feature 0907d7e + fix c8d2fea; both diffs read). Worktree gate, import path asserted inside it, bytecode off: ruff format --check clean, ruff check clean, pytest 1670 passed / 4 skipped. Both of my surviving mutations re-run myself and now KILLED: kind always "source" -> 1 failed; `[:HISTORY]` removed at write and read -> 2 failed. The decoded `sp:` path uses `unquote` on text that Jinja then escapes; `.nowrap` exists in base.html. The real-weights browser run from the first review stands (answerable question -> passages matching the API's 10, refusal with topics, shared URL, missing-backend message, escaped script input). Every AC holds.
- 2026-10-03 po: ACCEPTED at c8d2fea. The page shows what recall hands an agent — source, score, owning topic, brief vs source — refuses honestly with topics to explore, reproduces from its URL, and was driven with real weights. Every criterion holds.
