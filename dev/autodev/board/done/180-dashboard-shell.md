---
id: 180
title: the dashboard shell — server-rendered, logged in, role-gated
priority: medium
size: medium
depends_on: [006, 054, 139]
spec_refs: [build-order.md#T49, implementation-notes.md]
---

## Context
M10 opens. T49: "App shell + auth + context/tree switcher + role-gated views."

**Stack, decided by the stakeholder on 2026-09-27: server-rendered, Jinja +
HTMX.** No Node toolchain, no build step — the dashboard ships inside the one
`hrono` binary, which is what "one binary, `hrono`" and "minimum surface" have
meant everywhere else. T50's graph will need a small vendored JS library; that
is T50's problem and it is a smaller one than a second release artifact.

## The one real design question: how a BROWSER authenticates
The API takes `Authorization: Bearer <token>`, which a browser cannot send from
a plain navigation. So:

- A login page takes the same API token the CLI uses — no second credential,
  no user/password store, nothing new to keep secret.
- It goes in an **HttpOnly, SameSite=Strict cookie**, so page JavaScript cannot
  read it and another site cannot send it. Secure flag when the request is
  https, so a local http dev server still works.
- Dashboard routes resolve the cookie through the SAME `require_role`
  machinery as the API. Roles are enforced server-side from day one (CLAUDE.md)
  and a second auth path is how that stops being true.
- Logout clears the cookie.

## Description
- `GET /ui` — the shell: a tree switcher, the current role, nav, and an
  outlet HTMX swaps into.
- `GET /ui/login`, `POST /ui/login`, `POST /ui/logout`.
- A reader sees read-only views; write and admin actions are absent from the
  page AND refused by the route. A button nobody can see is not a permission.
- The tree switcher lists the trees the `trees` registry declares (#054),
  falling back to `default` when none are.
- HTMX vendored as a file this repo serves, not a CDN link: the server is
  expected to run where there is no internet.

## Acceptance criteria
- [x] `GET /ui` without a cookie redirects to the login page, not a 401 page.
- [x] A valid token logs in; the cookie is HttpOnly and SameSite=Strict.
- [x] A bad token is refused with a message and no cookie is set.
- [x] A reader gets no admin controls in the HTML AND a 403 from the route if
      they ask for one anyway.
- [x] The tree switcher lists declared trees, and `default` when none are.
- [x] Logout clears the cookie; the next request redirects to login.
- [x] No token is ever rendered into a page, a URL, or a log line.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Out of scope
Every view (T50-T56). This is the shell they hang in.

## Review log
- 2026-09-27 po: authored. Stack decided by the stakeholder: Jinja + HTMX.

- 2026-09-27 dev: done, commit d5c8a45. Driven in a real session against a real
  server:

      GET /ui (no cookie)   303 -> /ui/login
      GET /ui/login         the form
      POST /ui/login        303, cookie stored
      GET /ui (cookie)      tree switcher listing alpha/beta/gamma/watchtest,
                            "admin (admin)", "2 topic(s)"
      the token in the page 0 occurrences

  **One auth path, two carriers.** `_authenticate` now falls back to the cookie
  when there is no Authorization header, so the dashboard resolves through the
  same `require_role` every API route uses. What differs is only the FAILURE: a
  browser gets the login page, an API caller still gets 401, and a test asserts
  both of those on the same missing credential. Accepting a cookie on the API
  is safe because of SameSite=Strict — a cross-site post arrives without it.

  **No new dependency for forms.** `Form(...)` and `request.form()` both
  require `python-multipart`, even for the urlencoded body a plain HTML form
  actually sends. `urllib.parse.parse_qs` is the standard library and reads
  exactly that, so the whole dashboard costs one dependency (jinja2) rather
  than two. The day something needs a file upload is the day multipart earns
  its place.

  **HTMX is not vendored yet, deliberately.** The shell is login, logout, a
  switcher and a link — plain forms do all of it. HTMX earns its place at the
  first view that swaps a pane (T51), and vendoring a file nothing uses would
  be the speculative structure the conventions forbid. When it lands it is a
  vendored file this repo serves, not a CDN link: the server is expected to run
  where there is no internet.

  Checked the thing that works in a checkout and breaks on install: built a
  wheel and confirmed the templates are inside it. `uv_build` includes them;
  had it not, `/ui` would have 500'd on every installed copy while every test
  here passed.

  Mutations, all killed: the cookie readable by page scripts -> 1 fail;
  SameSite=none -> 1; a reader shown the write control -> 1; a tab getting a
  401 instead of the login page -> 2; the cookie carrier not accepted -> 3.

  One environment note: adding jinja2 and running `uv sync` silently dropped
  the `embed` and `cluster` EXTRAS from the venv, which turned the real-weights
  tests into skips. Restored with `uv sync --all-extras`. Worth knowing before
  someone reads a green run that quietly stopped exercising the real backends.

  Gate clean: 1254 passed, 2 skipped.

- 2026-09-27 qa: PASS, to po-review, with one defect found and fixed in place.

  Gate at 2b58882: ruff clean, 1256 passed. Drove the whole session against a
  real server — redirect, login page, cookie, shell with four declared trees,
  the role, the topic count, and zero occurrences of the token in the HTML.

  **The defect: the "sync this tree" button posted to a route that did not
  exist.** It rendered, it was role-gated in the template, and clicking it gave
  a 404. So the ticket's own demonstration of role gating demonstrated nothing
  — the control was hidden from readers and broken for everyone. Now the route
  exists, takes a WRITER dependency, redirects-after-POST so a refresh does not
  start a second run, and two tests cover both halves: a writer really enqueues
  a `sync-tree`, and a reader posting it anyway gets 403 with no job created.

  That is the AC's own wording — "a 403 from the route if they ask for one
  anyway" — and it could not have been true, because there was no route. A
  criterion about a route nobody wrote.

  Three more security-shaped checks, all correct:
  - the cookie works on the API too (200), which is intended and documented —
    one authentication path, and SameSite=Strict is what makes it safe;
  - `GET /ui/logout` is 405, so a link or an image tag cannot log someone out;
  - the API still answers 401 for the same missing credential that sends a
    browser to the login page.

  Dev's environment note deserves repeating: `uv sync` after adding jinja2
  dropped the `embed` and `cluster` extras, turning the real-weights tests into
  skips. A green run that has quietly stopped exercising the real backends is
  the failure mode this project has been bitten by three times.

- 2026-09-27 po: CLOSED. M10 has a shell, and it is inside the one binary with
  one new dependency.

  The decisions I want kept:

  **One authentication path.** The browser carries the same token in a cookie
  and resolves through the same `require_role`. A dashboard is exactly where a
  second auth system gets built by accident, and "roles enforced server-side
  from day one" would have become a sentence about the API only.

  **One dependency, not two.** `parse_qs` over `python-multipart` for a form
  with one field. The comment says what would change that (a file upload),
  which is the difference between a decision and an omission.

  **Nothing vendored that nothing uses.** HTMX waits for T51, the first view
  that swaps a pane. The stack is "Jinja + HTMX" and shipping the H before
  anything needs it would be structure for its own sake.

  qa's find is this ticket's lesson: an acceptance criterion said "a 403 from
  the route", and there was no route. The criterion read as satisfied because
  the button was correctly hidden — the visible half was right and the half
  that is the actual permission did not exist. Hiding a control is courtesy;
  the route is the permission.

  T50 (node graph) is next and is the one that needs HTMX and a small vendored
  graph library.
