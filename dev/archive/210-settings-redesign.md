---
id: 210
title: rebuild the Settings page — one collection at a time, forms a person can fill
priority: high
size: big
depends_on: []
spec_refs: [REQUIREMENTS.md#9 (63-69), #2 (10)]
---

## Context
The user's verdict is "looks terrible", and the review agrees: five collections on one 3000px page, a delete disclosure under every item taking more room than the item, field labels that are raw config paths, and an edit form that opens in the middle of everything.

## Description
Rebuild the page; keep the routes' behaviour and the descriptor-driven forms.

Structure: one collection visible at a time (Trees, Sources, Connections, Models, Prompts as sub-navigation), each as a table with real columns — models show role, connection, upstream model; sources show type, URL, filter summary. Edit and add open as their own view, not inline in the list. Delete is a row action that leads to a confirmation showing the impact preview (what it invalidates, what re-running costs) before anything is removed.

Forms: every field has a human label and a one-line help text, sourced from the descriptor so API validation and the form cannot drift; the raw key is secondary. Inputs match their type — a URL is a single-line input, a boolean is a labelled checkbox, a glob list says "one per line" and shows an example. Group source fields as Location, Access, Which files.

Completeness: the page says what is missing for a build to run — a role with no model, a model whose connection is gone.

A read-only block for what the environment sets: version, database path, LLM concurrency.

Keep the JSON view, labelled as the advanced alternative.

Screenshots of the current state are in `.autodev/board/ui-review-2026-10-03/` (`admin-config-*`, `s-cfg-*`).

## Findings from the UI review (2026-10-03)
Seen by driving the dashboard in headless Chromium against a copy of the `~/hrono-click` database (tree `click`: 8 topics, 2 levels, 126 sections, 3 runs), as admin and reader, at 1440px and 800px, light and dark. Screenshots are in `.autodev/board/ui-review-2026-10-03/`. Severity: **A** wrong or broken, **B** confusing enough to cost time, **C** polish. The tree is small, so anything that only breaks at scale was not seen; forms were opened, not submitted.

- **A** Five collections on one endless page; opening one edit form pushes everything else down and the form sits in the middle of a 3000px page. Screenshot: `s-cfg-edit-source.png`.
- **A** Every item has a "Delete this ..." disclosure on its own row, fenced by two rules, directly under it — the delete control takes more room than the item. Five models = five delete rows. Screenshot: `admin-config-1440-light.png`.
- **A** Field labels are raw config paths: `auth.method`, `filter.only`, `filter.replace_defaults`. No field says what it does.
- **B** A one-line git URL is edited in a five-row textarea; a boolean is a checkbox labelled "yes" inside an input-shaped box.
- **B** An item's settings are one grey run-on line ("kind text, connection cc, model sonnet, role brief"). Models should read as a table: role, connection, upstream model.
- **B** "Add a connection" replaces the Add button with a provider picker at the TOP of the list, above existing items, and the button disappears. Screenshot: `s-cfg-add-conn.png`.
- **B** Headings are lowercase collection keys (`trees`, `sources`); the Form/JSON switch sits under the title with no label; the chip "looking at it" is not a state anyone would name.
- **C** Default prompts show an orange "(default)" chip that looks like a warning; "What it ships as" is unclear.
- **B** Nothing shows which role has no model, or which model has no working connection — the page lists config and never says if it is complete.

## Acceptance criteria
- [ ] each collection is its own view with a table of named columns; no page is longer than its content needs
- [ ] no field is labelled only by its config path; every field has help text, and a test fails if a descriptor field lacks one
- [ ] add and edit never reorder or displace the list they came from
- [ ] delete shows the impact preview before confirming
- [ ] the page states whether configuration is complete enough to build, and what is missing
- [ ] environment-set values are visible read-only
- [ ] secrets are still never rendered back; the existing settings tests pass
- [ ] before/after screenshots at 1440px and 800px, light and dark, attached to the Review log

## Out of scope
New config options. Connection testing (#219). Changing the registry API.

## Review log
- 2026-10-03 po: authored from the requirements review and the UI review of the same day, at the user's request.
