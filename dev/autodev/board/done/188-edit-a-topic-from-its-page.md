---
id: 188
title: edit a topic from its page — rename, brief, notes, hand back (T56 part)
priority: medium
size: medium
depends_on: [182, 156, 157, 154]
spec_refs: [build-order.md#T56]
---

## Context
T56: "Manual surgery in-UI (migrate, edit, notes)". Split in two, because the
EDIT half and the MIGRATE half have different failure modes: an edit is one
node and reversible, a migration moves structure and is not. This ticket is
the edit half; structure surgery and section moves are #189.

Every operation already exists as a domain function with its own tests
(#156, #157, #154). Nothing new is being decided here — the page calls
`edits.rename`, `edits.override_brief`, `notes.add`, `edits.release`, the same
functions `server/edits.py` calls. A SECOND implementation of any of them in
the UI layer would be the second auth path #180 refused, in another costume.

## Description
- On the topic page, for a writer: rename; write the brief by hand; add a note;
  hand the topic back to automation (release every pin).
- Plain `<form method="post">` with a redirect back to the topic (POST-redirect
  -GET), so a refresh does not re-submit and every result is a URL.
- **Admin**-gated, because that is what the API's own edit routes require
  (`server/edits.py`: `Admin`). A UI that accepted a writer here would be a
  second, weaker authorization for the same operation — which is the thing
  #180 refused, stated as a role instead of as a code path. A reader or writer
  sees the page and no forms.
- Input validation reuses the API's own pydantic models (`Rename`, `BriefText`,
  `NoteText`), so "a title may not be blank" is one rule, not two.
- CSRF: the session cookie is `SameSite=Strict` (#180), which is what keeps a
  cross-site POST from carrying it. State that in the module, because the next
  person to loosen the cookie needs to find out here.
- The page already SHOWS pins, brief and notes (#182); this adds the writes,
  and the result of a write must be visible on the page it returns to.

## Acceptance criteria
- [x] An admin renames a topic from the page and sees the new name.
- [x] A hand-written brief appears on the page AND in recall — the pin is what
      `override_brief` does, and a UI that wrote `nodes.title` directly would
      pass a page test and lose the edit on the next regeneration.
- [x] A note added from the page shows on the page.
- [x] "Hand back" releases the pins, and the page says the topic is unpinned.
- [x] A reader gets no forms; a reader's POST is refused, and so is a
      WRITER's — the API's floor for these is admin.
- [x] A blank title or note is refused by the same rule the API uses, and the
      page says so rather than 500ing.
- [x] Every write goes through the existing `edits`/`notes` functions — no
      second implementation.
- [x] A refresh after a write does not repeat it.
- [x] `ruff format`, `ruff check --fix`, `pytest` clean.

## Review log
- 2026-09-27 po: authored. T56 split into the edit half (this) and the migrate
  half (#189).
- 2026-09-27 dev: four POST routes on the topic page (rename, brief, note,
  release) plus the forms, behind a new `Admin` page dependency.
  - Admin, not writer: `server/edits.py` gates these at admin, and a page that
    took a writer would be a second, weaker authorization for the same
    operation. The forms are absent for a reader AND a writer, and the routes
    refuse a writer's POST with 403 — hiding is courtesy, the dependency is the
    permission.
  - Validation reuses the API's `Rename` / `BriefText` / `NoteText` models, so
    "may not be blank" is one rule. A `ValidationError` becomes an `?error=`
    on the redirect rather than a 500.
  - Redirect-after-POST with the outcome in the query, so the page a write
    lands on is a URL and a refresh repeats nothing.
  - Mutations, all killed: rename writing `nodes.title` directly (loses the
    pin); brief writing the `briefs` row directly (never reaches recall);
    `Admin` -> `Writer`; the template gate `can_edit` -> `can_write`;
    validation skipped; 303 -> 307 (the refresh test and the error test fail).
  - Driven live on :8794 as both an admin and a writer: admin renames, writes
    the brief, notes, hands back (pins go from `{'brief': ...}` to `{}`); the
    writer sees no forms and gets 403 on the POST.
  - Gate: 1339 passed, 2 skipped.
- 2026-09-27 qa: verified. Added three escaping tests, because this is the
  first page that reflects operator input: a title lands inside an ATTRIBUTE
  in the pre-filled rename form, and `?error=` / `?done=` are printed straight
  from the URL. Both are escaped, and a note renders as text.
  - Checked and not a finding: no CSRF token. The session cookie is
    `SameSite=Strict` (#180), so a cross-site POST does not carry it; the
    token would be a second mechanism for a threat the cookie already closes.
    The day the cookie loosens, this needs revisiting — which is why it is
    written down in `ui.py` beside the cookie and not only here.
- 2026-09-27 po: accepted. The role correction during authoring was the real
  content of this ticket: "writer" was in the first draft, and a dashboard that
  quietly lowers the bar for an operation is how an access rule stops being
  one. #189 carries the migrate half.
