"""Settings: every registry collection, and the writes that change one.

The page and its writes live together (#195), because a form and what it posts
to are one subject.

Every write goes through `registry.engine`'s OWN operations — the same
functions the API routes call — so what a valid config is, how a secret is
encrypted, what `before_delete` warns about and what `?dry_run=true` reports
each have exactly one implementation. A settings page that validated a config
itself would be a second rule, and the two would drift.

What this module adds is only what a browser needs and an API client does not:
the submitted values kept when a write is refused, the server's per-field
errors rendered against the field they name, the blast radius shown before the
edit is applied, and a mask that means UNTOUCHED rather than "write ``***``
over the credential".

**Two views over the same collections (#200).** The page was five textareas of
JSON, which is the API's surface wearing a browser: adding a model meant
knowing the schema by heart, and the collection could only be edited one item
at a time — there was no way to say "these are my models". So:

- `view=form` (the default) renders the collection as a TABLE of named
  columns (`config_view.COLUMNS`), and each item's add or edit as FIELDS
  derived from the collection's own pydantic model by `server/forms.py`.
- `view=json` renders the collection as ONE array, written back through
  `engine.sync_items`, which writes what differs and removes what is gone —
  the advanced alternative.

**One collection at a time (#210).** All five on one page was a 3000px wall
with an edit form opened in the middle of it. `section` picks the collection
from a sub-navigation, and an add, an edit or a delete is its own view, so
none of them reorders or pushes down the list it came from.

**Trees come first.** A tree is the thing every other collection is in service
of, and it was the last card on the page, behind a `<details>` — an operator
looking for "how do I make a tree" found four screens of model JSON instead.
It is the first section and the one the page lands on.
"""

from __future__ import annotations

import json
import os
import sqlite3
from importlib.metadata import version
from urllib.parse import parse_qs, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.auth.users import User
from hrono.errors import AppError, NotFound
from hrono.registry import completeness, engine, impact, store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.descriptor import Descriptor
from hrono.registry.write import decrypt, unmask
from hrono.server import config_view, forms
from hrono.server.auth import allows, require_role
from hrono.server.ui import Reader, _trees, router, templates
from hrono.summarize import pool

FROZEN = (
    "a shipped default cannot be edited — reset it, or add your own beside it"
)
VIEWS = ("form", "json")
# Trees first: a tree is what every other collection is in service of, and the
# page's job is to answer "how do I make one" before it answers anything else.
ORDER = ("trees", "sources", "connections", "models", "prompts")
# Which fields name a row in ANOTHER collection. The pydantic model types them
# as plain strings — they are foreign keys the registry resolves by hand — so
# the page has to be told, once, to offer the registered names rather than a
# free-text box whose typo is only caught by a refusal after the save.
REFERS: dict[str, dict[str, str]] = {
    "trees": {"sources": "sources"},
    "models": {"connection": "connections"},
}


@router.get("/ui/config", response_class=HTMLResponse)
def config_page(
    request: Request,
    user: Reader,
    tree: str = "",
    section: str = "",
    view: str = "",
    edit: str = "",
    add: str = "",
    delete: str = "",
    variant: str = "",
    done: str = "",
    error: str = "",
) -> Response:
    """One registry collection at a time, with secrets masked.

    Masked through the registry's OWN `mask()`, not a second redaction here: it
    reads each collection's declared `secret_paths` (#142), so a source type
    whose credential moves is masked by declaring the new path — and there is
    no second place that can forget to.

    `section` picks the collection (#210): five collections on one page was a
    3000px wall, and an edit form opened in the middle of it. `edit`, `add`,
    `delete` and `variant` ride in the URL rather than in the page, so the
    form an operator has open is a link like any other, a refused write can
    redirect back to exactly it, and the list it came from is untouched — it
    is one Cancel away rather than pushed down the page.

    `done` and `error` are read back off the redirect every write ends with.
    They were being SENT and never read — the route took neither, so a save
    redirected to a page that said nothing about the save (#200).
    """
    return _render(
        request,
        user,
        tree,
        section=section,
        view=view,
        edit=edit,
        add=add,
        delete=delete,
        variant=variant,
        done=done,
        error=error,
    )


@router.post("/ui/config/{collection}/item")
async def item_from_the_page(
    collection: str, request: Request, user: Reader
) -> Response:
    """Save one item from its form — creating it, or replacing what is there.

    One route for both, because `engine.replace_item` is already create-or-
    replace (#138): "config is data you PUT". A page that chose between POST
    and PUT by first asking whether the name existed would be re-deriving that
    decision in a second place.
    """
    descriptor = _descriptor(collection)
    _may_write(descriptor, request)
    form = await _form(request)
    tree, name = _one(form, "tree"), _one(form, "name").strip()
    picked = _one(form, "variant")
    preview = bool(_one(form, "preview"))
    options = _options(request, collection)
    body = forms.config_from(descriptor, form, options)
    row = _existing(descriptor, name, request)
    spot = _spot(collection, name, picked, body)
    if row is not None and row["is_default"]:
        return _render(
            request,
            user,
            tree,
            **spot,
            draft=_refused(collection, [_problem(FROZEN)]),
        )
    sent = _kept_secrets(descriptor, row, body, request)
    try:
        result = engine.replace_item(
            descriptor,
            str(sent.get("name", name)),
            sent,
            request,
            dry_run=preview,
        )
    except AppError as exc:
        return _render(
            request,
            user,
            tree,
            **spot,
            draft=_refused(collection, _errors(exc)),
        )
    if preview:
        return _render(
            request,
            user,
            tree,
            **spot,
            draft=_refused(
                collection,
                impact=result.get("affected_trees", []),
                previewed=True,
            ),
        )
    return _settled(
        tree, collection, done=f"{collection}: saved {sent.get('name', name)}"
    )


def _spot(
    collection: str, name: str, variant: str, body: dict[str, object]
) -> dict[str, object]:
    """Where to re-open the form a write came from, and with what in it.

    A refused save re-renders rather than redirecting, because the operator's
    typed values are the thing worth keeping — a redirect would hand back the
    stored config and ask them to type it again.
    """
    return {
        "edit": f"{collection}:{name}" if name else "",
        "add": "" if name else collection,
        "variant": variant,
        "typed": body,
        "where": collection,
    }


@router.post("/ui/config/{collection}/replace")
async def replace_the_collection(
    collection: str, request: Request, user: Reader
) -> Response:
    """Make the collection be the list that was typed (the JSON view).

    The whole point of this view: adding a model is a new entry, dropping one
    is deleting its entry, and both land in one save.
    """
    descriptor = _descriptor(collection)
    _may_write(descriptor, request)
    form = await _form(request)
    tree, text = _one(form, "tree"), _one(form, "config")
    items, problems = _parsed_list(text)
    if items is None:
        return _render(
            request,
            user,
            tree,
            section=collection,
            view="json",
            draft=_draft(collection, text, problems),
        )
    held = {row.name: row for row in _table(request, collection).rows}
    try:
        kept = [
            _kept_secrets(
                descriptor,
                _existing(descriptor, str(item.get("name", "")), request),
                item,
                request,
            )
            for item in items
        ]
        result = engine.sync_items(descriptor, kept, request)
    except AppError as exc:
        return _render(
            request,
            user,
            tree,
            section=collection,
            view="json",
            draft=_draft(collection, text, _errors(exc)),
        )
    return _settled(
        tree, collection, view="json", done=_said(collection, result, held)
    )


@router.post("/ui/config/{collection}/{name}/delete")
async def delete_from_the_page(
    collection: str, name: str, request: Request, user: Reader
) -> Response:
    """Remove an item — or, for a seeded default, reset it to what shipped."""
    descriptor = _descriptor(collection)
    _may_write(descriptor, request)
    form = await _form(request)
    tree = _one(form, "tree")
    doomed = f"{collection}:{name}"
    if not _one(form, "confirm"):
        return _render(
            request,
            user,
            tree,
            delete=doomed,
            error=f"confirm to delete: {name}",
        )
    try:
        result = engine.delete_item(descriptor, name, request)
    except AppError as exc:
        return _render(request, user, tree, delete=doomed, error=exc.message)
    if "reset" in result:
        return _settled(
            tree, collection, done=f"{collection}: {name} reset to default"
        )
    note = result.get("note", "")
    return _settled(
        tree,
        collection,
        done=f"{collection}: deleted {name}" + (f" — {note}" if note else ""),
    )


def _said(
    collection: str, result: dict[str, object], held: dict[str, object]
) -> str:
    """What a whole-collection save actually did, counted rather than claimed.

    "saved" over a list that changed nothing is a lie an operator acts on.
    """
    written = list(result.get("written", []))  # type: ignore[call-overload]
    removed = list(result.get("removed", []))  # type: ignore[call-overload]
    if not written and not removed:
        return f"{collection}: nothing to change"
    parts = []
    if written:
        added = [name for name in written if name not in held]
        if added:
            parts.append(f"added {', '.join(added)}")
        changed = [name for name in written if name in held]
        if changed:
            parts.append(f"changed {', '.join(changed)}")
    if removed:
        parts.append(f"removed {', '.join(removed)}")
    return f"{collection}: " + ", ".join(parts)


def _render(
    request: Request,
    user: User,
    tree: str,
    *,
    section: str = "",
    view: str = "",
    edit: str = "",
    add: str = "",
    delete: str = "",
    variant: str = "",
    typed: dict[str, object] | None = None,
    where: str = "",
    done: str = "",
    error: str = "",
    draft: dict[str, object] | None = None,
) -> Response:
    """The page, in whatever state the write that just ran left it."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        tables = {table.name: table for table in config_view.tables(conn)}
        offers = {
            descriptor.collection: [
                str(row["name"])
                for row in store.list_all(conn, descriptor.collection)
            ]
            for descriptor in COLLECTIONS
        }
        gaps = completeness.gaps(conn)
        environment = _environment(conn)
    showing = _showing(section, edit, add, delete)
    opened, open_name = _split(edit)
    doomed_in, doomed = _split(delete)
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree if tree in trees else trees[0],
            "view": view if view in VIEWS else VIEWS[0],
            "sections": [
                {
                    "name": descriptor.collection,
                    "count": len(tables[descriptor.collection].rows),
                }
                for descriptor in _ordered()
            ],
            "collection": _collection(
                _descriptor(showing),
                tables[showing],
                user,
                request,
                offers,
                editing=open_name if opened == showing else "",
                adding=add == showing,
                deleting=doomed if doomed_in == showing else "",
                variant=variant,
                typed=typed if where == showing else None,
                draft=draft,
            ),
            "can_write": user.role in {"writer", "admin"},
            "gaps": gaps,
            "environment": environment,
            "done": done,
            "error": error,
            "draft": draft,
        },
    )


def _environment(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """What the server's environment sets, which no registry write changes.

    The database path is asked of the connection itself rather than of the
    app's arguments, so an app built over an injected connection reports the
    file it is really on.
    """
    files = {
        str(row["name"]): str(row["file"])
        for row in conn.execute("PRAGMA database_list").fetchall()
    }
    return [
        ("Version", version("hrono")),
        ("Database", files.get("main") or "in memory"),
        ("LLM calls at once", _width()),
    ]


def _width() -> str:
    """The LLM pool width, and whether the environment or the default set it."""
    if os.environ.get(pool.ENV_WIDTH) is None:
        return f"{pool.width()} (the default; {pool.ENV_WIDTH} changes it)"
    return f"{pool.width()} (from {pool.ENV_WIDTH})"


def _showing(section: str, edit: str, add: str, delete: str) -> str:
    """Which collection the page is on: the one an open form belongs to, else
    the one asked for, else trees."""
    for asked in (_split(edit)[0], add, _split(delete)[0], section):
        if asked in ORDER:
            return asked
    return ORDER[0]


def _ordered() -> list[Descriptor]:
    """The collections in the order an operator meets them, trees first."""
    place = {name: index for index, name in enumerate(ORDER)}
    return sorted(
        COLLECTIONS,
        key=lambda d: (place.get(d.collection, len(ORDER)), d.collection),
    )


def _collection(
    descriptor: Descriptor,
    table: config_view.Table,
    user: User,
    request: Request,
    offers: dict[str, list[str]],
    *,
    editing: str,
    adding: bool,
    deleting: str,
    variant: str,
    typed: dict[str, object] | None,
    draft: dict[str, object] | None,
) -> dict[str, object]:
    """One collection, with the role its writes actually take.

    `can_write` is the collection's OWN `write_role` run through the check the
    post would be refused by — not a page-local opinion about who may write
    what, which is how a control gets drawn for someone the API then refuses.

    `mode` is what the page is showing for it: the `list`, a `form` (an add
    or an edit), the variant `choosing` step of a union's add, a `frozen`
    shipped default, or the `delete` confirmation. Exactly one, so an open
    form never shares the page with the list it came from.
    """
    writable = allows(user.role, descriptor.write_role)
    held = {row.name: row for row in table.rows}
    options = {
        field: offers.get(target, [])
        for field, target in REFERS.get(descriptor.collection, {}).items()
    }
    refused = (
        draft
        if draft and draft.get("collection") == descriptor.collection
        else None
    )
    form = None
    mode = "list"
    if writable and (editing or adding):
        # what the operator TYPED beats what is stored: a refused save must
        # hand back their words, not the config they were trying to replace
        config = typed if typed is not None else _held_config(held, editing)
        form = forms.form_for(descriptor, config, variant, options)
        mode = "form"
        # a union's add starts by naming the shape: five near-identical forms
        # stacked on a page, four of them wrong, is not a choice anyone makes
        if adding and form.picks and not variant:
            mode = "choosing"
        if editing in held and held[editing].is_default:
            mode = "frozen"
    doomed = held.get(deleting) if writable else None
    if doomed is not None:
        mode = "delete"
    return {
        "name": descriptor.collection,
        "write_role": descriptor.write_role,
        "can_write": writable,
        "document": table.document,
        "headings": [
            column.heading
            for column in config_view.COLUMNS.get(descriptor.collection, ())
        ],
        "rows": [
            {
                "name": row.name,
                "is_default": row.is_default,
                "config": row.config,
                "cells": row.cells(descriptor.collection),
            }
            for row in table.rows
        ],
        "mode": mode,
        "form": form,
        "editing": editing,
        "doomed": None
        if doomed is None
        else {
            "name": doomed.name,
            "is_default": doomed.is_default,
            "config": doomed.config,
            "note": ""
            if doomed.is_default
            else _delete_note(descriptor, doomed.name, request),
            "impact": _removal(descriptor, doomed, request),
        },
        "draft": refused,
    }


def _removal(
    descriptor: Descriptor, row: config_view.Row, request: Request
) -> list[object]:
    """What removing this row would strand, asked BEFORE the button is.

    A shipped default resets rather than deletes, so its impact is the edit
    back to what shipped — the same preview a save would show.
    """
    shipped = next(
        (d for d in descriptor.defaults if d.get("name") == row.name), None
    )
    with request.app.state.db.connect() as conn:
        found = (
            impact.preview(conn, descriptor.collection, row.name, shipped)
            if row.is_default and shipped is not None
            else impact.of_delete(conn, descriptor.collection, row.name)
        )
    return list(impact.as_json(found)["affected_trees"])  # type: ignore[call-overload]


def _held_config(
    held: dict[str, config_view.Row], editing: str
) -> dict[str, object] | None:
    row = held.get(editing)
    return row.data if row is not None else None


def _refused(
    collection: str,
    errors: object = (),
    *,
    impact: object = (),
    previewed: bool = False,
) -> dict[str, object]:
    """One item's rejection or dry run, rendered against its own form.

    Carries no text: the form is rebuilt from the posted CONFIG, so there is
    nothing to keep a second copy of.
    """
    return {
        "collection": collection,
        "text": "",
        "errors": list(errors),  # type: ignore[call-overload]
        "impact": list(impact),  # type: ignore[call-overload]
        "previewed": previewed,
        "on_form": True,
    }


def _options(request: Request, collection: str) -> dict[str, list[str]]:
    """What the referring fields of ``collection`` may name, as registered."""
    refers = REFERS.get(collection, {})
    if not refers:
        return {}
    with request.app.state.db.connect() as conn:
        return {
            field: [str(row["name"]) for row in store.list_all(conn, target)]
            for field, target in refers.items()
        }


def _table(request: Request, collection: str) -> config_view.Table:
    with request.app.state.db.connect() as conn:
        for table in config_view.tables(conn):
            if table.name == collection:
                return table
    raise NotFound(f"no such collection: {collection}")


def _delete_note(descriptor: Descriptor, name: str, request: Request) -> str:
    """What deleting this row would arm, asked BEFORE it is offered (#167).

    The same hook the DELETE runs, called here for its warning — so what the
    operator reads beside the button is what the operation itself would say,
    rather than a copy of it kept in a template.
    """
    if descriptor.before_delete is None:
        return ""
    try:
        return descriptor.before_delete(name, engine.context(request)) or ""
    except AppError as exc:
        return exc.message


def _kept_secrets(
    descriptor: Descriptor,
    row: object,
    body: dict[str, object],
    request: Request,
) -> dict[str, object]:
    """A secret still at the mask keeps the credential already stored.

    The page can only ever show `***`, so a form that posted back what it
    displayed would overwrite the credential with the mask and leave a config
    that looks exactly right and no longer authenticates.
    """
    if row is None or not descriptor.secret_paths:
        return body
    key_id = row["key_id"]  # type: ignore[index]
    if key_id is None:
        return body
    previous = decrypt(
        json.loads(row["config"]),  # type: ignore[index]
        descriptor,
        engine.context(request).cipher,
        int(key_id),
    )
    return unmask(body, previous, descriptor)


def _descriptor(collection: str) -> Descriptor:
    for descriptor in COLLECTIONS:
        if descriptor.collection == collection:
            return descriptor
    raise NotFound(f"no such collection: {collection}")


def _may_write(descriptor: Descriptor, request: Request) -> None:
    """Refuse what the API would refuse, through the API's own check.

    The collection's declared `write_role`, resolved by `require_role` — so a
    page write can never be a softer door than the PUT it stands for, and a
    forged post from a reader is refused here rather than merely undrawn.
    """
    require_role(descriptor.write_role)(request)


def _existing(
    descriptor: Descriptor, name: str, request: Request
) -> object | None:
    """The stored row, or None — an add names something that is not there."""
    if not name:
        return None
    with request.app.state.db.connect() as conn:
        return store.get(conn, descriptor.collection, name)


async def _form(request: Request) -> dict[str, list[str]]:
    """An HTML form's fields, keeping EVERY value of a repeated name.

    `ui._fields` collapses each name to one value, which is right for a text
    input and wrong for a set of checkboxes: the tree picker posts `sources`
    once per ticked source, and taking the first would silently register a
    tree over one source out of five.
    """
    body = (await request.body()).decode("utf-8", "replace")
    return parse_qs(body, keep_blank_values=True)


def _one(form: dict[str, list[str]], key: str) -> str:
    return form.get(key, [""])[0]


def _split(edit: str) -> tuple[str, str]:
    """``collection:name`` as its two halves, blank when there is no edit."""
    collection, _, name = edit.partition(":")
    return collection, name


def _parsed_list(
    text: str,
) -> tuple[list[dict] | None, list[dict[str, str]]]:
    """The typed JSON as a list of configs, or why it is not one."""
    try:
        body = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [
            _problem(
                f"not valid JSON: {exc.msg} "
                f"(line {exc.lineno}, column {exc.colno})",
                field="config",
            )
        ]
    if not isinstance(body, list):
        return None, [_problem("a collection is a JSON array", field="config")]
    bad = [item for item in body if not isinstance(item, dict)]
    if bad:
        return None, [
            _problem("every entry must be a JSON object", field="config")
        ]
    return body, []


VALUE_ERROR = "Value error, "  # pydantic's own prefix on a validator's text


def _errors(error: AppError) -> list[dict[str, str]]:
    """The server's rejection, per field.

    `Invalid` already carries `details.errors` with a `loc` and a `msg` per
    field (`engine._validated`), so the page renders THOSE rather than
    "invalid body" — an operator editing one field of a discriminated union
    needs to be told which field, in its own words.
    """
    details = error.details or {}
    reported = details.get("errors")
    if not isinstance(reported, list):
        return [_problem(error.message)]
    return [
        _problem(
            str(item.get("msg", "")).removeprefix(VALUE_ERROR),
            field=".".join(str(part) for part in item.get("loc", ())),
        )
        for item in reported
        if isinstance(item, dict)
    ]


def _problem(message: str, field: str = "") -> dict[str, str]:
    return {"field": field, "msg": message}


def _draft(
    collection: str,
    text: str,
    errors: object,
    *,
    impact: object = (),
    previewed: bool = False,
) -> dict[str, object]:
    """What the operator typed, kept so a rejection loses no work.

    ``previewed`` is not ``impact`` being empty: a dry run that finds no
    affected tree is an answer — "this edit restales nothing" — and an edit
    nobody previewed has not been asked the question.
    """
    return {
        "collection": collection,
        "text": text,
        "errors": list(errors),  # type: ignore[call-overload]
        "impact": list(impact),  # type: ignore[call-overload]
        "previewed": previewed,
    }


def _settled(
    tree: str, section: str, view: str = "", **outcome: str
) -> Response:
    """Redirect-after-POST, back to the collection it changed."""
    query = {"tree": tree, "section": section}
    if view:
        query["view"] = view
    query.update({k: v for k, v in outcome.items() if v})
    return RedirectResponse(f"/ui/config?{urlencode(query)}", status_code=303)
