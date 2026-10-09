---
id: 181
title: the dashboard's jobs view, live
priority: medium
size: medium
depends_on: [180, 172, 173, 174, 179]
spec_refs: [build-order.md#T53]
---

## Context
T53: "Jobs view + SSE live". Taken before T50 and T51 because it is the view an
operator opens most — a run is the thing you watch — and because everything
underneath it landed this week: derived parent status and progress (#172),
cancel (#173), the SSE endpoint (#174), and per-job tokens (#179).

## Description
- `GET /ui/jobs` — the runs for the current tree, newest first: op, status,
  progress, what it spent, and its children when it has them.
- LIVE without a library: `EventSource` is a browser built-in and
  `GET /jobs/<id>/events` already speaks it (#174). No HTMX and no vendored JS
  for this view.
- A cancel button on anything still running, writer-gated at the ROUTE and not
  only in the template (#180's lesson).
- A failed job shows its error CODE and message — #161 made those worth
  reading and the dashboard is where someone reads them.

## Acceptance criteria
- [x] The view lists the tree's jobs with status, progress and tokens.
- [x] A parent shows its children and their statuses.
- [x] A running job updates in the page without a reload.
- [x] Cancel works from the page, is refused for a reader at the route, and
      reports what it could not stop (#173).
- [x] A failed job's code and message are on the page.
- [x] No token in the HTML, no page script reading the cookie.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored.

- 2026-09-27 dev: done, commit 13f1de1. Live with **no library and nothing
  vendored**: `EventSource` is a browser built-in and `/jobs/<id>/events`
  already speaks it (#174), so the whole view is Jinja plus fourteen lines of
  inline script.

  **That is also the vindication of #180's auth decision, and I did not expect
  it.** `EventSource` cannot set an Authorization header — it can only send
  cookies. Had the dashboard used a bearer token in page memory, the live view
  would have been impossible without a second endpoint or a token in a query
  string. Driven: the stream authenticates from the same HttpOnly cookie the
  page does.

  The page derives nothing of its own — the same `rollup` and `total_spend` the
  API uses (#172, #179), so a dashboard cannot disagree with `hrono jobs get`.

  Driven on a real server against tree `alpha`: the run listed with `2/2`, its
  two children named by their source scope, the failure shown, and the SSE
  stream answering from the cookie.

  Mutations, all killed: nothing marked live -> 1 fail; a finished run watched
  forever -> 1; a reader cancelling at the route -> 1; children listed as
  top-level runs too -> 1 (that one needed a new assertion — `data-job=` count
  — because "the children appear" was true either way, which is the
  symmetric-fixture shape again).

  Gate clean: 1266 passed, 2 skipped.

- 2026-09-27 qa: PASS, to po-review. Gate: ruff clean, 1266 passed. Re-ran L3
  (a reader cancelling at the route) — fails. Drove the page and the stream
  against a real server from a real cookie jar.

  The finding I want on the record is dev's, and it is an argument rather than
  a defect: **`EventSource` cannot send an Authorization header.** The live
  view exists because #180 put the token in a cookie. Had that gone the other
  way — a token in page memory, sent as a header by fetch — T53 would have
  needed either a second auth mechanism or a token in a URL, and a token in a
  URL ends up in logs and history. A decision made for one reason turning out
  to be the only workable one for another is worth writing down.

  Checked that the page derives nothing itself: status, progress and spend all
  come from `rollup` and `total_spend`, the same functions `GET /jobs/<id>`
  uses. A dashboard with its own arithmetic is a dashboard that eventually
  disagrees with the CLI, and nobody can tell which is right.

- 2026-09-27 po: CLOSED. T53 done, and the dashboard is useful rather than
  merely present — a run is the thing an operator watches.

  Taking it before T50 and T51 was right: everything under it landed this week,
  so the view is thin, and it proves the shell carries weight before the
  expensive view (the graph) is attempted.

  The `EventSource` point goes in the M10 record: the cookie is not a
  convenience, it is what makes a live page possible at all. T50 will want the
  same and should not invent a second path.

  Two views down, six to go. T51 (node detail) next — the graph links into it,
  so it comes before the graph.
