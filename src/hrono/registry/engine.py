"""The generic registry engine: one descriptor in, a CRUD router out.

Every collection shares this engine; behaviour differences live in the
``Descriptor`` (model, secret fields, write role, validation hook), never in a
per-collection branch here. Secrets are encrypted at rest via the request's
active key and masked on the way out, so plaintext is write-only.
"""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import ValidationError

from hrono.crypto.cipher import Cipher
from hrono.registry import store
from hrono.registry.descriptor import (
    Descriptor,
    ValidationContext,
    ValidationFailed,
)
from hrono.server.auth import require_role

_MASK = "***"


def build_router(descriptor: Descriptor) -> APIRouter:
    """Build the CRUD router for one collection from its descriptor."""
    router = APIRouter()
    collection = descriptor.collection
    reader = Depends(require_role("reader"))
    writer = Depends(require_role(descriptor.write_role))

    def list_items(request: Request) -> list[dict[str, object]]:
        with request.app.state.db.connect() as conn:
            rows = store.list_all(conn, collection)
        return [_masked(descriptor, row) for row in rows]

    def get_item(name: str, request: Request) -> dict[str, object]:
        with request.app.state.db.connect() as conn:
            row = store.get(conn, collection, name)
        if row is None:
            raise _not_found(collection, name)
        return _masked(descriptor, row)

    def create_item(body: dict, request: Request) -> dict[str, object]:
        config = _validated(descriptor, body)
        _run_hook(descriptor, config, _context(request))
        stored, key_id = _encrypt(config, descriptor, _cipher(request))
        try:
            with request.app.state.db.connect() as conn:
                store.insert(
                    conn,
                    collection,
                    config["name"],
                    json.dumps(stored),
                    key_id,
                    _now(),
                )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{collection} already exists: {config['name']}",
            ) from exc
        return _mask(stored, descriptor)

    def replace_item(
        name: str, body: dict, request: Request
    ) -> dict[str, object]:
        config = _validated(descriptor, body)
        if config["name"] != name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="name in body does not match name in path",
            )
        _run_hook(descriptor, config, _context(request))
        stored, key_id = _encrypt(config, descriptor, _cipher(request))
        with request.app.state.db.connect() as conn:
            existed = store.replace(
                conn, collection, name, json.dumps(stored), key_id, _now()
            )
        if not existed:
            raise _not_found(collection, name)
        return _mask(stored, descriptor)

    def delete_item(name: str, request: Request) -> dict[str, str]:
        with request.app.state.db.connect() as conn:
            removed = store.delete(conn, collection, name)
        if not removed:
            raise _not_found(collection, name)
        return {"deleted": name}

    base = f"/{collection}"
    named = f"/{collection}/{{name}}"
    router.add_api_route(
        base, list_items, methods=["GET"], dependencies=[reader]
    )
    router.add_api_route(
        named, get_item, methods=["GET"], dependencies=[reader]
    )
    router.add_api_route(
        base,
        create_item,
        methods=["POST"],
        status_code=status.HTTP_201_CREATED,
        dependencies=[writer],
    )
    router.add_api_route(
        named, replace_item, methods=["PUT"], dependencies=[writer]
    )
    router.add_api_route(
        named, delete_item, methods=["DELETE"], dependencies=[writer]
    )
    return router


def _cipher(request: Request) -> Cipher:
    return Cipher.from_key(
        request.app.state.master_key, request.app.state.key_id
    )


def _context(request: Request) -> ValidationContext:
    return ValidationContext(
        database=request.app.state.db, cipher=_cipher(request)
    )


def _validated(descriptor: Descriptor, body: dict) -> dict[str, object]:
    try:
        model = descriptor.model.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=[{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()],
        ) from exc
    return model.model_dump()


def _run_hook(
    descriptor: Descriptor,
    config: dict[str, object],
    context: ValidationContext,
) -> None:
    if descriptor.validate is None:
        return
    try:
        descriptor.validate(config, context)
    except ValidationFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=exc.reason
        ) from exc


def _encrypt(
    config: dict[str, object], descriptor: Descriptor, cipher: Cipher
) -> tuple[dict[str, object], int | None]:
    stored = deepcopy(config)
    key_id: int | None = None
    for path in descriptor.secret_paths:
        holder = _holder(stored, path)
        if holder is None:
            continue
        parent, key = holder
        if parent[key] is None:
            continue
        secret = cipher.encrypt(str(parent[key]))
        parent[key] = secret.ciphertext
        key_id = secret.key_id
    return stored, key_id


def _mask(
    config: dict[str, object], descriptor: Descriptor
) -> dict[str, object]:
    masked = deepcopy(config)
    for path in descriptor.secret_paths:
        holder = _holder(masked, path)
        if holder is None:
            continue
        parent, key = holder
        if parent[key] is not None:
            parent[key] = _MASK
    return masked


def _masked(descriptor: Descriptor, row: sqlite3.Row) -> dict[str, object]:
    return _mask(json.loads(row["config"]), descriptor)


def _holder(
    data: dict[str, object], path: tuple[str, ...]
) -> tuple[dict[str, object], str] | None:
    node: object = data
    for key in path[:-1]:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    if not isinstance(node, dict) or path[-1] not in node:
        return None
    return node, path[-1]


def _not_found(collection: str, name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{collection} not found: {name}",
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
