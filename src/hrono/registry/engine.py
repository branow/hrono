"""The generic registry engine: one descriptor in, a CRUD router out.

Every collection shares this engine; behaviour differences live in the
``Descriptor`` (model, secret fields, write role, validation hook), never in a
per-collection branch here. Secrets are encrypted at rest via the request's
active key and masked on the way out, so plaintext is write-only.
"""

from __future__ import annotations

import json
import sqlite3
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
from hrono.registry.write import content_hash, encrypt, mask
from hrono.server.auth import require_role


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
        stored, key_id = encrypt(config, descriptor, _cipher(request))
        payload = json.dumps(stored)
        try:
            with request.app.state.db.connect() as conn:
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
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{collection} already exists: {config['name']}",
            ) from exc
        return mask(stored, descriptor)

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
        stored, key_id = encrypt(config, descriptor, _cipher(request))
        payload = json.dumps(stored)
        with request.app.state.db.connect() as conn:
            existed = store.replace(
                conn,
                collection,
                name,
                payload,
                key_id,
                _now(),
                content_hash(payload),
            )
        if not existed:
            raise _not_found(collection, name)
        return mask(stored, descriptor)

    def delete_item(name: str, request: Request) -> dict[str, str]:
        with request.app.state.db.connect() as conn:
            row = store.get(conn, collection, name)
        if row is None:
            raise _not_found(collection, name)
        default = _default_config(descriptor, name)
        if row["is_default"] and default is not None:
            stored, key_id = encrypt(default, descriptor, _cipher(request))
            payload = json.dumps(stored)
            with request.app.state.db.connect() as conn:
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
        with request.app.state.db.connect() as conn:
            store.delete(conn, collection, name)
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


def _masked(descriptor: Descriptor, row: sqlite3.Row) -> dict[str, object]:
    return mask(json.loads(row["config"]), descriptor)


def _default_config(
    descriptor: Descriptor, name: str
) -> dict[str, object] | None:
    for default in descriptor.defaults:
        if default["name"] == name:
            return dict(default)
    return None


def _not_found(collection: str, name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{collection} not found: {name}",
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
