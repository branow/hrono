---
id: 219
title: from an empty install to a built tree, in the panel
priority: medium
size: big
depends_on: [210, 202]
spec_refs: [REQUIREMENTS.md#2 (7-13), README.md]
---

## Context
The empty state of the home page prints CLI commands. Everything a first build needs can be configured in Settings, but nothing leads a person through it or tells them what it will cost before they start.

## Description
A setup path shown while the install is incomplete, each step a real form that reuses the Settings forms of #210:

1. Connection — choose a provider, enter the key, and test it with one real minimal call before saving. Explain the `claude-code` versus API-key trade-off the README documents, in two sentences.
2. Models — offer a sensible default assignment per role for the chosen provider, editable.
3. Source — location, access, which files. Preview what the filter keeps: file count, total size, the largest files, what was excluded and why — computed from a fetch, with no model call.
4. Estimate — sections to condense, calls, tokens, and time and cost from the price table of #202, with the subscription caveat. Stated as an estimate with its basis.
5. Build — start `maintain` and land on its run page.

Each step can be left and resumed; the path disappears once a tree is built and is reachable again from Settings for adding a second source.

## Acceptance criteria
- [ ] a new install reaches a built tree using only the browser — driven end to end on a real small repository
- [ ] a wrong API key is caught at step 1 with the provider's reason, before anything is saved
- [ ] the file preview matches what ingest then actually reads — same filter code, asserted
- [ ] the estimate is within a stated tolerance of the real run, and the Review log records both numbers
- [ ] abandoning midway leaves valid config and no half-built tree
- [ ] nothing on the path tells the user to open a terminal

## Out of scope
Non-git sources. Generating the master key or the first admin token (that precedes the panel).

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
