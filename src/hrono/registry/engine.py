"""The generic registry engine: one descriptor in, a CRUD router out.

Every collection shares this engine; behaviour differences live in the
``Descriptor`` (model, secret fields, write role, validation hook), never in a
per-collection branch here. Secrets are encrypted at rest via the request's
active key and masked on the way out, so plaintext is write-only.

``PUT`` CREATES OR REPLACES, idempotently (#138). The spec and ``CLAUDE.md``
both say "config is data you PUT", and this engine used to 404 a PUT to a name
that did not exist yet — so registering a source meant knowing whether it was
already there and choosing POST or PUT accordingly. A configuration write should
be declarative: say what the config IS, get that, whether or not it was there
before. POST keeps its create-only meaning (409 on conflict) for a caller that
wants to be told.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request, status
from pydantic import ValidationError

from hrono.crypto.cipher import Cipher
from hrono.errors import BadRequest, Conflict, Invalid, NotFound
from hrono.registry import impact, store
from hrono.registry.descriptor import Descriptor, ValidationContext
from hrono.registry.write import content_hash, decrypt, encrypt, mask
from hrono.server.auth import require_role


def build_router(descriptor: Descriptor) -> APIRouter:
    """Build the CRUD router for one collection from its descriptor."""
    router = APIRouter()
    collection = descriptor.collection
    reader = Depends(require_role("reader"))
    writer = Depends(require_role(descriptor.write_role))

    def list_route(request: Request) -> list[dict[str, object]]:
        return list_items(descriptor, request)

    def get_route(name: str, request: Request) -> dict[str, object]:
        return get_item(descriptor, name, request)

    def create_route(body: dict, request: Request) -> dict[str, object]:
        return create_item(descriptor, body, request)

    def replace_route(
        name: str, body: dict, request: Request, dry_run: bool = False
    ) -> dict[str, object]:
        return replace_item(descriptor, name, body, request, dry_run=dry_run)

    def delete_route(name: str, request: Request) -> dict[str, str]:
        return delete_item(descriptor, name, request)

    base = f"/{collection}"
    named = f"/{collection}/{{name}}"
    router.add_api_route(
        base, list_route, methods=["GET"], dependencies=[reader]
    )
    router.add_api_route(
        named, get_route, methods=["GET"], dependencies=[reader]
    )
    router.add_api_route(
        base,
        create_route,
        methods=["POST"],
        status_code=status.HTTP_201_CREATED,
        dependencies=[writer],
    )
    router.add_api_route(
        named, replace_route, methods=["PUT"], dependencies=[writer]
    )
    router.add_api_route(
        named, delete_route, methods=["DELETE"], dependencies=[writer]
    )
    return router


# The four operations are module-level rather than closures over the router so
# the dashboard can reach the SAME write path the API takes (#199). A settings
# page that re-validated a config in its own handler would be a second rule for
# what a valid config is, and the two would drift — the defect this codebase
# keeps writing tickets about. The routes above are now thin adapters.


def list_items(
    descriptor: Descriptor, request: Request
) -> list[dict[str, object]]:
    with request.app.state.db.connect() as conn:
        rows = store.list_all(conn, descriptor.collection)
    return [_masked(descriptor, row) for row in rows]


def get_item(
    descriptor: Descriptor, name: str, request: Request
) -> dict[str, object]:
    with request.app.state.db.connect() as conn:
        row = store.get(conn, descriptor.collection, name)
    if row is None:
        raise _not_found(descriptor.collection, name)
    return _masked(descriptor, row)


def create_item(
    descriptor: Descriptor, body: dict, request: Request
) -> dict[str, object]:
    collection = descriptor.collection
    config = _validated(descriptor, body)
    _run_hook(descriptor, config, context(request))
    stored, key_id = encrypt(config, descriptor, _cipher(request))
    payload = json.dumps(stored)
    try:
        with request.app.state.db.write() as conn:
            store.insert(
                conn,
                collection,
                config["name"],
                payload,
                key_id,
                _now(),
                content_hash=content_hash(payload),
            )
    except sqlite3.IntegrityError as exc:
        raise Conflict(
            f"{collection} already exists: {config['name']}"
        ) from exc
    return mask(stored, descriptor)


def replace_item(
    descriptor: Descriptor,
    name: str,
    body: dict,
    request: Request,
    dry_run: bool = False,
) -> dict[str, object]:
    collection = descriptor.collection
    config = _validated(descriptor, body)
    if config["name"] != name:
        raise BadRequest("name in body does not match name in path")
    _run_hook(descriptor, config, context(request))
    if dry_run:
        # validated and hooked, then NOTHING written: a preview of an edit
        # that would be rejected is a rejection, not an impact report
        # (T58). One implementation, in the engine, so every collection
        # has the safety rather than the ones someone remembered.
        with request.app.state.db.connect() as conn:
            return impact.as_json(
                impact.preview(conn, collection, name, config)
            )
    stored, key_id = encrypt(config, descriptor, _cipher(request))
    payload = json.dumps(stored)
    now = _now()
    with request.app.state.db.write() as conn:
        existed = store.replace(
            conn,
            collection,
            name,
            payload,
            key_id,
            now,
            content_hash(payload),
        )
        if not existed:  # PUT CREATES (#138 F2): config is data you PUT
            store.insert(
                conn,
                collection,
                name,
                payload,
                key_id,
                now,
                content_hash=content_hash(payload),
            )
    return mask(stored, descriptor)


def sync_items(
    descriptor: Descriptor, items: list[dict], request: Request
) -> dict[str, object]:
    """Make the collection BE ``items`` — writing what differs, dropping what
    is gone.

    A collection edited as a whole, which is how an operator thinks about one:
    "these are my models", rather than five separate edits plus a delete.
    Adding a model is a new entry in the list and dropping one is deleting its
    entry, in a single save.

    Three things this owes the operator. Every item is validated and hooked
    BEFORE anything is written, because a list that half-applies leaves a page
    that is neither what they had nor what they asked for. An item identical to
    what is stored is NOT rewritten — a save that restaled every brief in the
    tree because the page was opened and closed would make this view unusable.
    And the hooks see the state BEFORE the sync, so a batch introducing a
    source and a tree naming it together is refused; register the source first.
    That is the same limit the API's own PUTs have.
    """
    collection = descriptor.collection
    wanted: dict[str, dict[str, object]] = {}
    for body in items:
        config = _validated(descriptor, body)
        name = str(config["name"])
        if name in wanted:
            raise BadRequest(f"{collection} listed twice: {name}")
        _run_hook(descriptor, config, context(request))
        wanted[name] = config
    cipher = _cipher(request)
    with request.app.state.db.connect() as conn:
        held = {
            str(row["name"]): _plain(row, descriptor, cipher)
            for row in store.list_all(conn, collection)
        }
    written = [
        name
        for name, config in wanted.items()
        if _normal(descriptor, held.get(name)) != config
    ]
    for name in written:
        replace_item(descriptor, name, wanted[name], request)
    gone = sorted(set(held) - set(wanted))
    for name in gone:
        delete_item(descriptor, name, request)
    return {"written": written, "removed": gone}


def delete_item(
    descriptor: Descriptor, name: str, request: Request
) -> dict[str, str]:
    collection = descriptor.collection
    with request.app.state.db.connect() as conn:
        row = store.get(conn, collection, name)
    if row is None:
        raise _not_found(collection, name)
    default = _default_config(descriptor, name)
    if row["is_default"] and default is not None:
        stored, key_id = encrypt(default, descriptor, _cipher(request))
        payload = json.dumps(stored)
        with request.app.state.db.write() as conn:
            store.replace(
                conn,
                collection,
                name,
                payload,
                key_id,
                _now(),
                content_hash(payload),
            )
        return {"reset": name}
    note = None
    if descriptor.before_delete is not None:
        note = descriptor.before_delete(name, context(request))
    with request.app.state.db.write() as conn:
        store.delete(conn, collection, name)
    deleted: dict[str, str] = {"deleted": name}
    if note is not None:
        deleted["note"] = note
    return deleted


def _normal(
    descriptor: Descriptor, config: dict[str, object] | None
) -> dict[str, object] | None:
    """A stored config on the SAME terms as an incoming one.

    `wanted` holds validated configs — pydantic's dump, with every optional
    field present at its default. A stored row written before a field existed
    does not carry it, so comparing the two raw said "changed" about a config
    nobody had touched, and a save of an unmodified document rewrote the whole
    collection and restaled its briefs (#200).

    A row that no longer validates compares as different, which is correct: it
    is exactly a row the next save should replace.
    """
    if config is None:
        return None
    try:
        return _validated(descriptor, config)
    except Invalid:
        return None


def _plain(
    row: sqlite3.Row, descriptor: Descriptor, cipher: Cipher
) -> dict[str, object]:
    """One stored row as the config it holds, secrets decrypted.

    What `sync_items` compares against, so an item identical to what is stored
    is left alone — the comparison has to be made on the SAME terms as the
    incoming config, and an encrypted blob never equals a credential.
    """
    config = json.loads(row["config"])
    key_id = row["key_id"]
    if key_id is None or not descriptor.secret_paths:
        return config
    return decrypt(config, descriptor, cipher, int(key_id))


def _cipher(request: Request) -> Cipher:
    return Cipher.from_key(
        request.app.state.master_key, request.app.state.key_id
    )


def context(request: Request) -> ValidationContext:
    return ValidationContext(
        database=request.app.state.db,
        cipher=_cipher(request),
        cache_root=request.app.state.cache_root,
    )


def _validated(descriptor: Descriptor, body: dict) -> dict[str, object]:
    try:
        model = descriptor.model.model_validate(body)
    except ValidationError as exc:
        errors = [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]
        raise Invalid("invalid body", details={"errors": errors}) from exc
    return model.model_dump()


def _run_hook(
    descriptor: Descriptor,
    config: dict[str, object],
    context: ValidationContext,
) -> None:
    if descriptor.validate is None:
        return
    descriptor.validate(config, context)


def _masked(descriptor: Descriptor, row: sqlite3.Row) -> dict[str, object]:
    return mask(json.loads(row["config"]), descriptor)


def _default_config(
    descriptor: Descriptor, name: str
) -> dict[str, object] | None:
    for default in descriptor.defaults:
        if default["name"] == name:
            return dict(default)
    return None


def _not_found(collection: str, name: str) -> NotFound:
    return NotFound(f"{collection} not found: {name}")


def _now() -> str:
    return datetime.now(UTC).isoformat()
