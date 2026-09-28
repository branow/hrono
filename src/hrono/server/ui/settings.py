"""Settings: every registry collection, and the writes that change one.

The page and its writes live together (#195), because a form and what it posts
to are one subject.

Every write goes through `registry.engine`'s OWN operations — the same
functions the API routes call — so what a valid config is, how a secret is
encrypted, what `before_delete` warns about and what `?dry_run=true` reports
each have exactly one implementation. A settings page that validated a config
itself would be a second rule, and the two would drift.

What this module adds is only what a browser needs and an API client does not:
the submitted text kept when a write is refused, the server's per-field errors
rendered against the field they name, the blast radius shown before the edit is
applied, and a mask that means UNTOUCHED rather than "write ``***`` over the
credential".
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.auth.users import User
from hrono.errors import AppError, NotFound
from hrono.registry import engine, store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.descriptor import Descriptor
from hrono.registry.write import decrypt, unmask
from hrono.server import config_view
from hrono.server.auth import allows, require_role
from hrono.server.ui import Reader, _trees, router, templates

FROZEN = (
    "a shipped default cannot be edited — reset it, or add your own beside it"
)


@router.get("/ui/config", response_class=HTMLResponse)
def config_page(request: Request, user: Reader, tree: str = "") -> Response:
    """Every registry collection, with secrets masked.

    Masked through the registry's OWN `mask()`, not a second redaction here: it
    reads each collection's declared `secret_paths` (#142), so a source type
    whose credential moves is masked by declaring the new path — and there is
    no second place that can forget to.
    """
    return _render(request, user, tree)


@router.post("/ui/config/trees/new")
async def new_tree_from_the_page(request: Request, user: Reader) -> Response:
    """Create a tree: a name, and the sources it is the map over (#054).

    A picker rather than a JSON field, because the sources a tree may name are
    exactly the ones registered — and the validation hook that refuses an
    unregistered name teaches that through a refusal, which is the worse way to
    learn it.
    """
    descriptor = _descriptor("trees")
    _may_write(descriptor, request)
    form = await _form(request)
    tree = _one(form, "tree")
    name = _one(form, "name").strip()
    sources = [source for source in form.get("sources", []) if source]
    try:
        engine.create_item(
            descriptor, {"name": name, "sources": sources}, request
        )
    except AppError as exc:
        return _render(
            request,
            user,
            tree,
            new_tree={
                "name": name,
                "sources": sources,
                "errors": _errors(exc),
            },
        )
    return _settled(tree, done=f"tree {name} created")


@router.post("/ui/config/{collection}/create")
async def create_from_the_page(
    collection: str, request: Request, user: Reader
) -> Response:
    """Add an item to a collection from the JSON an operator typed."""
    descriptor = _descriptor(collection)
    _may_write(descriptor, request)
    form = await _form(request)
    tree, text = _one(form, "tree"), _one(form, "config")
    body, problems = _parsed(text)
    if body is None:
        return _render(
            request, user, tree, adding=_draft(collection, text, problems)
        )
    try:
        engine.create_item(descriptor, body, request)
    except AppError as exc:
        return _render(
            request,
            user,
            tree,
            adding=_draft(collection, text, _errors(exc)),
        )
    return _settled(tree, done=f"{collection}: added {body.get('name', '')}")


@router.post("/ui/config/{collection}/{name}/save")
async def save_from_the_page(
    collection: str, name: str, request: Request, user: Reader
) -> Response:
    """Replace one item's config, or preview what replacing it would cost.

    The preview is `?dry_run=true`'s own path (#190): validated, hooked, and
    then NOTHING written. An edit that would restale a tree's briefs says so
    here, before it is applied.
    """
    descriptor = _descriptor(collection)
    _may_write(descriptor, request)
    row = _row(descriptor, name, request)
    form = await _form(request)
    tree, text = _one(form, "tree"), _one(form, "config")
    preview = bool(_one(form, "preview"))
    if row["is_default"]:
        return _render(
            request,
            user,
            tree,
            draft=_draft(collection, text, [_problem(FROZEN)], name=name),
        )
    body, problems = _parsed(text)
    if body is None:
        return _render(
            request,
            user,
            tree,
            draft=_draft(collection, text, problems, name=name),
        )
    try:
        result = engine.replace_item(
            descriptor,
            name,
            _kept_secrets(descriptor, row, body, request),
            request,
            dry_run=preview,
        )
    except AppError as exc:
        return _render(
            request,
            user,
            tree,
            draft=_draft(collection, text, _errors(exc), name=name),
        )
    if preview:
        return _render(
            request,
            user,
            tree,
            draft=_draft(
                collection,
                text,
                (),
                name=name,
                impact=result.get("affected_trees", []),
                previewed=True,
            ),
        )
    return _settled(tree, done=f"{collection}: saved {name}")


@router.post("/ui/config/{collection}/{name}/delete")
async def delete_from_the_page(
    collection: str, name: str, request: Request, user: Reader
) -> Response:
    """Remove an item — or, for a seeded default, reset it to what shipped."""
    descriptor = _descriptor(collection)
    _may_write(descriptor, request)
    form = await _form(request)
    tree = _one(form, "tree")
    if not _one(form, "confirm"):
        return _render(
            request, user, tree, error=f"tick the box to confirm: {name}"
        )
    try:
        result = engine.delete_item(descriptor, name, request)
    except AppError as exc:
        return _render(request, user, tree, error=exc.message)
    if "reset" in result:
        return _settled(tree, done=f"{collection}: {name} reset to default")
    note = result.get("note", "")
    return _settled(
        tree,
        done=f"{collection}: deleted {name}" + (f" — {note}" if note else ""),
    )


def _render(
    request: Request,
    user: User,
    tree: str,
    *,
    done: str = "",
    error: str = "",
    draft: dict[str, object] | None = None,
    adding: dict[str, object] | None = None,
    new_tree: dict[str, object] | None = None,
) -> Response:
    """The page, in whatever state the write that just ran left it."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        tables = {table.name: table for table in config_view.tables(conn)}
        sources = [str(row["name"]) for row in store.list_all(conn, "sources")]
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree if tree in trees else trees[0],
            "collections": [
                _collection(
                    descriptor, tables[descriptor.collection], user, request
                )
                for descriptor in COLLECTIONS
            ],
            "sources": sources,
            "can_write": user.role in {"writer", "admin"},
            "done": done,
            "error": error,
            "draft": draft,
            "adding": adding,
            "new_tree": new_tree,
        },
    )


def _collection(
    descriptor: Descriptor,
    table: config_view.Table,
    user: User,
    request: Request,
) -> dict[str, object]:
    """One collection, with the role its writes actually take.

    `can_write` is the collection's OWN `write_role` run through the check the
    post would be refused by — not a page-local opinion about who may write
    what, which is how a control gets drawn for someone the API then refuses.
    """
    writable = allows(user.role, descriptor.write_role)
    return {
        "name": descriptor.collection,
        "write_role": descriptor.write_role,
        "can_write": writable,
        "rows": [
            {
                "name": row.name,
                "is_default": row.is_default,
                "config": row.config,
                "delete_note": ""
                if row.is_default or not writable
                else _delete_note(descriptor, row.name, request),
            }
            for row in table.rows
        ],
    }


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
    if not descriptor.secret_paths:
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


def _row(descriptor: Descriptor, name: str, request: Request) -> object:
    with request.app.state.db.connect() as conn:
        row = store.get(conn, descriptor.collection, name)
    if row is None:
        raise NotFound(f"{descriptor.collection} not found: {name}")
    return row


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


def _parsed(
    text: str,
) -> tuple[dict[str, object] | None, list[dict[str, str]]]:
    """The typed JSON as a config object, or why it is not one."""
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
    if not isinstance(body, dict):
        return None, [_problem("a config is a JSON object", field="config")]
    return body, []


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
            str(item.get("msg", "")),
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
    name: str = "",
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
        "name": name,
        "text": text,
        "errors": list(errors),  # type: ignore[call-overload]
        "impact": list(impact),  # type: ignore[call-overload]
        "previewed": previewed,
    }


def _settled(tree: str, **outcome: str) -> Response:
    """Redirect-after-POST, carrying what happened."""
    query = urlencode({"tree": tree, **{k: v for k, v in outcome.items() if v}})
    return RedirectResponse(f"/ui/config?{query}", status_code=303)
