---
id: E013
title: from an empty install to a built tree, in the panel
priority: medium
depends_on: [E006]
requirements: [7, 8, 11, 12]
---

## Goal
The empty home prints CLI commands. Lead a new admin through connection,
models, source, estimate and build, reusing E006's forms. Detail: archive/219.

## Tickets

### 1 connection tested before saving
Done when:
- [ ] a wrong key is caught with the provider's reason before anything is saved
- [ ] claude-code vs API-key trade-off explained in two sentences

### 2 models and source with a free preview
Change: default role assignment per provider; preview of what the filter keeps
(count, size, largest, excluded and why) from a fetch, no model call.
Done when:
- [ ] the preview matches what ingest then reads — same filter code, asserted

### 3 estimate, then build
Change: sections, calls, tokens, time, cost from #202's price table with the
subscription caveat; start maintain, land on its run page.
Done when:
- [ ] estimate vs real run, both numbers in the Log, within a stated tolerance
- [ ] abandoning midway leaves valid config and no half-built tree
- [ ] driven end to end in a browser on a real small repo; no step says
  "open a terminal"

### 4 the delete preview's registry copy comes from the real schema
Change: `completeness._registry_without` builds its in-memory copy from the
real registry schema (backup or migration DDL), not hand-written CREATE
TABLEs, and closes the connection.
Done when:
- [ ] a test fails if a registry migration adds a column the copy lacks
- [ ] the copy's connection is closed (no ResourceWarning under -W error)
Look at: src/hrono/registry/completeness.py

## Out of scope
- scheduling (skipped)

## Log
- 2026-10-03 po: created from #219.
- 2026-10-03 po: T4 folded from backlog (qa E006 r3, registry-copy-restates-schema).
- 2026-10-03 po: starting — E008 merged (cf801a6), price table and home/overview.py on main.
- 2026-10-03 dev T4 b2261bc: the delete preview's copy is created from `sqlite_master` DDL and closed; tests add a column to the real table and assert the copy has it, and run `gaps(without=)` under a ResourceWarning check. Mutations killed: copy not closed.
- 2026-10-03 dev T1 e2244f4: the provider's own reason ("authentication failed: invalid x-api-key", read off the real answer from api.anthropic.com in a browser) with the key masked out of it; the two-sentence trade-off is asserted. Mutations killed: key not masked. Real backend: `_get` against a stub server.
- 2026-10-03 dev T2+T3 99142fa (one commit: the four steps are one page): `filter.survey` is the one filter and `ingestable` is built on it; the preview and the estimate's section count are asserted against the sections the real sync+split ops stored. Mutations killed: preview keeps refused files, topic size, subscription priced as metered, price ignored, resume re-probes, double build, step lock, build with a step open, empty-file gate, home gap check on a built tree.
- 2026-10-03 dev estimate vs real, claude-code (haiku condense, sonnet briefs), through the browser wizard, constants fitted on repo A then held out on repo B. Held-out chalk (27 sections): est 30 calls / 459,649 in / 31,022 out / 156 s / $0.4273; real 30 / 484,818 / 30,288 / 151 s / $0.4252 (subscription-equivalent). Fitting repo itsdangerous (50 sections): est 54 / 814,186 / 53,420 / 222 s / $0.7026; real 55 / 929,528 / 55,472 / 236 s / $0.7531. Stated tolerance 25% (worst seen 12%); pinned in `test_the_estimate_agrees_with_a_measured_build_within_a_quarter`. The API-key path is derived from the text written, not measured (no key here), and says so in the code.
- 2026-10-03 dev driven end to end in Chromium on :8912 and :8913 against real local git repos, from an empty database to a built tree and its run page; no step mentions a terminal (asserted over every step's text). Evidence in evidence/E013/. Gate: format and check clean; 1175 passed over server, registry, ingest, onboarding, usage; 1 failure is a pre-existing network-dependent test (backlog/syncer-dispatch-test-reaches-the-network.md).

- 2026-10-03 qa r1 99142fa: FAIL. Drove the wizard in Chromium from an empty db (wrong Anthropic key refused, nothing saved; claude-code, models, source preview, estimate, triple concurrent Build press = one run, built). Re-ran dev mutation (key not masked: killed); mine: preview/estimate ignore the source filter (setup.py _preview/_build) SURVIVED, upper fanout loop killed. Findings: untested filter wiring, partial key leak (truncate before mask), first build says sync "nothing to do", unencoded redirect params, T2+T3 in one commit. Backlog: setup-dead-ends-without-the-embed-extra, maintain-builds-an-unregistered-tree.
- round 2: fixed qa 1-4 in c325ad9 (filter wiring page test, mask-then-cut, fetch_source without pinning, urlencode); mutations A,B,key-cut,pin-in-preview all killed. Finding 5 (T2/T3 split) left: rewriting a commit qa saw is barred by dev.md; PO/orchestrator rules.
- 2026-10-03 qa r2 c325ad9: PASS. Round-1 findings 1-4 fixed. Drove the wizard in Chromium on a fresh db against a local git repo with filter.exclude docs/** (claude-code, models, preview: 2 kept and 1 left out by matched filter.exclude; estimate 3 calls over 2 sections; built with 3 real calls, 2 sections stored; the run page reads 'sync repo: 1 new version fetched'). Re-ran mutations, all killed: A (_preview ignores the filter), B (_build ignores the filter), mask after the cut, the preview pinning the version, _fetched redirect unencoded, sync_source never reporting a new version. Finding 5 (T2+T3 in one commit, 99142fa) is left for the PO to waive, as board.md does for a commit qa has already seen. Note: the sync_source docstring still says the setup path calls it; it now calls fetch_source.
- 2026-10-03 po review c325ad9: ACCEPT. All Done-when met per dev/qa Log (wrong key refused unsaved; preview and estimate on the same filter/split, asserted; estimate within 25%, 12% seen; abandon test; browser-driven, no terminal step). README/Guide/home updated. T2+T3 one commit waived (E008/E009 precedent). Stale sync_source docstring -> backlog.
- merged to main at 4495ae9
