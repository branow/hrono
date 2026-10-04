"""Setup: from an empty install to a built tree, in the browser (#219).

Four steps — a connection, models, a source, an estimate and the build — each
a real form over the registry the Settings page edits. Nothing here keeps its
own record of how far a person got: a step is DONE when the registry says it
is (a connection exists, `completeness.gaps` finds no model missing, a source
exists, the tree has topics), so leaving halfway and coming back resumes at the
first step still open, and a person who configured things in Settings or with
the CLI is not asked to do them again.

Every write goes through `registry.engine.replace_item`, the function the API's
PUT and the Settings form call: a connection is tested against its provider
before it is stored, a model is called once before it is stored, and a refusal
is shown in the provider's words with nothing saved. A model row is only
written when it differs from what is stored, so resuming a step that half
finished does not pay for the calls that already succeeded.

What a source's filter keeps, and what a build would cost, are READS: the files
are fetched the way a sync fetches them, the filter is `ingest.filter.survey`
(the function ingest reads its files through), and no model is called.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.auth.users import User
from hrono.embed import runner
from hrono.errors import AppError
from hrono.ingest import SyncError
from hrono.ingest.sync import fetch_source as fill_cache
from hrono.jobs.ops import JobContext
from hrono.jobs.worker import enqueue
from hrono.onboarding import defaults
from hrono.onboarding.estimate import Estimate, cut, estimate
from hrono.onboarding.preview import Preview, preview
from hrono.registry import completeness, engine, store
from hrono.registry.collections.connections import CONNECTIONS
from hrono.registry.collections.models import MODELS
from hrono.registry.collections.sources import SOURCES
from hrono.registry.collections.trees import is_known, scoped_sources
from hrono.server import forms
from hrono.server.auth import allows
from hrono.server.ui import Reader, Writer, _shape, _trees, router, templates
from hrono.server.ui.settings import (
    existing,
    field_errors,
    first,
    kept_secrets,
    posted,
    problem,
)
from hrono.summarize import pool
from hrono.usage.present import duration

STEPS = (
    ("connection", "Connection"),
    ("models", "Models"),
    ("source", "Source"),
    ("build", "Estimate and build"),
)
_KEYS = tuple(key for key, _ in STEPS)
_LIVE = ("pending", "running")


@dataclass(frozen=True)
class Progress:
    """Which steps the registry says are done."""

    connections: tuple[dict[str, object], ...]
    sources: tuple[dict[str, object], ...]
    model_gaps: tuple[completeness.Gap, ...]
    models: int
    built: bool

    @property
    def done(self) -> dict[str, bool]:
        return {
            "connection": bool(self.connections),
            "models": not self.model_gaps,
            "source": bool(self.sources),
            "build": self.built,
        }

    @property
    def open(self) -> str:
        """The first step still to do, or the last when all are done."""
        done = self.done
        return next((key for key in _KEYS if not done[key]), _KEYS[-1])


def progress(conn: sqlite3.Connection, tree: str) -> Progress:
    topics, _ = _shape(conn, tree)
    return Progress(
        connections=tuple(_configs(conn, "connections")),
        sources=tuple(_configs(conn, "sources")),
        model_gaps=tuple(
            gap
            for gap in completeness.gaps(conn)
            if gap.section in ("models", "prompts")
        ),
        models=len(store.list_all(conn, "models")),
        built=topics > 0,
    )


def _configs(conn: sqlite3.Connection, collection: str) -> list[dict]:
    return [
        json.loads(row["config"]) for row in store.list_all(conn, collection)
    ]


@router.get("/ui/setup", response_class=HTMLResponse)
def setup_page(
    request: Request,
    user: Reader,
    tree: str = "",
    step: str = "",
    provider: str = "",
    source: str = "",
    new: str = "",
    change: str = "",
) -> Response:
    """The setup path, at the step asked for or the first one still open."""
    return _render(
        request,
        user,
        tree,
        step=step,
        provider=provider,
        source=source,
        adding=bool(new),
        changing=bool(change),
    )


@router.post("/ui/setup/connection")
async def save_connection(request: Request, user: Writer) -> Response:
    """Test a connection against its provider; store it only if it passes."""
    form = await posted(request)
    tree, chosen = first(form, "tree"), first(form, "variant")
    body = forms.config_from(CONNECTIONS, form)
    name = str(body.get("name", "")).strip()
    try:
        await run_in_threadpool(
            engine.replace_item, CONNECTIONS, name, body, request
        )
    except AppError as exc:
        return _render(
            request,
            user,
            tree,
            step="connection",
            provider=chosen,
            changing=True,
            typed=body,
            problems=field_errors(exc),
        )
    return _next(tree, "models", f"Connected: {name} answered.")


@router.post("/ui/setup/models")
async def save_models(request: Request, user: Writer) -> Response:
    """Register the embedding model and one text model per writing role."""
    form = await posted(request)
    tree = first(form, "tree")
    connection = first(form, "connection")
    wanted = _wanted(request, connection, form)
    refused = await run_in_threadpool(_write_models, request, wanted)
    if refused is not None:
        name, exc = refused
        return _render(
            request,
            user,
            tree,
            step="models",
            typed={"connection": connection, **_upstreams(wanted)},
            problems=[
                problem(f"{name}: {message['msg']}", field=message["field"])
                for message in field_errors(exc)
            ],
        )
    return _next(tree, "source", "Models registered and each one answered.")


@router.post("/ui/setup/source")
async def save_source(request: Request, user: Writer) -> Response:
    """Store a git source, fetch it, and come back to say what it holds."""
    form = await posted(request)
    tree, chosen = first(form, "tree"), first(form, "variant")
    descriptor = SOURCES
    body = forms.config_from(descriptor, form)
    name = str(body.get("name", "")).strip()
    row = existing(descriptor, name, request)
    sent = kept_secrets(descriptor, row, body, request)
    try:
        await run_in_threadpool(
            engine.replace_item, descriptor, name, sent, request
        )
    except AppError as exc:
        return _render(
            request,
            user,
            tree,
            step="source",
            adding=True,
            source=name,
            typed=body,
            problems=field_errors(exc),
            variant=chosen,
        )
    return await _fetched(request, user, tree, name)


@router.post("/ui/setup/source/fetch")
async def fetch_source(request: Request, user: Writer) -> Response:
    """Fetch a stored source again, so its preview reads current files."""
    form = await posted(request)
    return await _fetched(
        request, user, first(form, "tree"), first(form, "name")
    )


@router.post("/ui/setup/build")
async def start_build(request: Request, user: Writer) -> Response:
    """Start the first build and land on its run."""
    form = await posted(request)
    tree = first(form, "tree")
    with request.app.state.db.connect() as conn:
        if not is_known(conn, tree):
            return _render(
                request,
                user,
                tree,
                step="build",
                problems=[problem(f"tree not registered: {tree}")],
            )
        state = progress(conn, tree)
        busy = conn.execute(
            "SELECT id FROM jobs WHERE tree = ? AND parent_id IS NULL "
            "AND status IN ('pending', 'running') LIMIT 1",
            (tree,),
        ).fetchone()
    if busy is not None:
        return RedirectResponse(
            f"/ui/jobs/{busy['id']}?tree={tree}", status_code=303
        )
    if state.model_gaps or not state.sources:
        return _next(tree, state.open, "")
    job = enqueue(
        request.app.state.db,
        "maintain",
        {},
        tree=tree,
        started_by=user.name,
    )
    return RedirectResponse(f"/ui/jobs/{job}?tree={tree}", status_code=303)


def _render(
    request: Request,
    user: User,
    tree: str,
    *,
    step: str = "",
    provider: str = "",
    source: str = "",
    adding: bool = False,
    changing: bool = False,
    typed: dict[str, object] | None = None,
    problems: list[dict[str, str]] | None = None,
    variant: str = "",
) -> Response:
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        chosen_tree = tree if tree in trees else trees[0]
        state = progress(conn, chosen_tree)
        current = _current(step, state)
        context: dict[str, object] = {
            "user": user,
            "trees": trees,
            "tree": chosen_tree,
            "can_write": allows(user.role, "writer"),
            "steps": [
                {"key": key, "label": label, "done": state.done[key]}
                for key, label in STEPS
            ],
            "step": current,
            "state": state,
            "refusals": problems or [],
            "providers": defaults.PROVIDERS,
        }
        if current == "connection":
            context |= _connection(state, provider, changing, typed)
        elif current == "models":
            context |= _models(conn, state, typed)
        elif current == "source":
            context |= _source(
                request, conn, state, source, adding, typed, variant
            )
        else:
            context |= _build(request, conn, chosen_tree, state)
    return templates.TemplateResponse(request, "setup.html", context)


def _current(step: str, state: Progress) -> str:
    """The step asked for if every step before it is done, else the open one."""
    if step not in _KEYS:
        return state.open
    done = state.done
    earlier = _KEYS[: _KEYS.index(step)]
    return step if all(done[key] for key in earlier) else state.open


def _connection(
    state: Progress,
    provider: str,
    changing: bool,
    typed: dict[str, object] | None,
) -> dict[str, object]:
    chosen = defaults.provider(provider) or defaults.PROVIDERS[0]
    config = {
        "name": chosen.name,
        "provider": chosen.name,
        **(typed or {}),
    }
    form = forms.form_for(CONNECTIONS, config, chosen.name)
    return {
        "provider": chosen,
        "form": form,
        "showing_form": changing or not state.connections,
    }


def _models(
    conn: sqlite3.Connection,
    state: Progress,
    typed: dict[str, object] | None,
) -> dict[str, object]:
    names = [str(one["name"]) for one in state.connections]
    chosen = str((typed or {}).get("connection") or (names[0] if names else ""))
    kind = next(
        (
            str(one["provider"])
            for one in state.connections
            if one["name"] == chosen
        ),
        "",
    )
    shipped = {
        str(one["name"]): one for one in defaults.models_for(kind, chosen)
    }
    roles = [
        {
            "role": role,
            "model": str(
                (typed or {}).get(role)
                or shipped.get(role, {}).get("model", "")
            ),
        }
        for role in defaults.ROLES
    ]
    return {
        "connection_names": names,
        "chosen_connection": chosen,
        "roles": roles,
        "embedding": str(
            (typed or {}).get("embedding") or defaults.EMBEDDING_MODEL
        ),
        "foreign": _foreign(conn),
        "embed_missing": not runner.backend_installed(),
        "embed_install": runner.INSTALL,
    }


def _foreign(conn: sqlite3.Connection) -> bool:
    """Is there a model this path did not register?

    Models it registered are resumable: a step that stopped after three of five
    is finished by the same form. A model someone else added is theirs to fix,
    and adding the shipped rows beside it would claim a role twice.
    """
    ours = {defaults.EMBEDDING_NAME, *defaults.ROLES}
    return any(
        row["name"] not in ours for row in store.list_all(conn, "models")
    )


def _source(
    request: Request,
    conn: sqlite3.Connection,
    state: Progress,
    source: str,
    adding: bool,
    typed: dict[str, object] | None,
    variant: str,
) -> dict[str, object]:
    held = {str(one["name"]): one for one in state.sources}
    name = source if source in held else ""
    showing = adding or name != "" and typed is not None
    config = typed if typed is not None else dict(held.get(name, {}))
    config.setdefault("type", "git")
    config.setdefault("name", "repo" if not held else "")
    form = forms.form_for(SOURCES, config, "git")
    chosen = name or (next(iter(held), "") if not adding else "")
    seen = None
    if chosen and chosen in held and not adding:
        seen = _preview(request, chosen, held[chosen])
    return {
        "source_names": list(held),
        "source": chosen,
        "form": form,
        "showing_form": showing or not held,
        "preview": seen,
        "fetched": seen is not None,
    }


def _preview(
    request: Request, name: str, config: dict[str, object]
) -> Preview | None:
    """What the source's filter keeps, from its cache; None until fetched."""
    if str(config.get("type")) != "git":
        return None
    cache = _cache(request, name)
    if cache is None:
        return None
    filtered = config.get("filter")
    return preview(cache, filtered if isinstance(filtered, dict) else None)


def _cache(request: Request, name: str) -> Path | None:
    """Where a source was fetched to, or None when it has not been."""
    root = request.app.state.cache_root
    cache = None if root is None else root / name
    return cache if cache is not None and cache.exists() else None


def _build(
    request: Request, conn: sqlite3.Connection, tree: str, state: Progress
) -> dict[str, object]:
    if state.built:
        return {"estimate": None, "unread": [], "elsewhere": []}
    if state.model_gaps or not state.sources:
        return {"estimate": None, "unread": [], "elsewhere": []}
    caches, unread, elsewhere = [], [], []
    for name in scoped_sources(conn, tree):
        config = next(one for one in state.sources if one["name"] == name)
        cache = _cache(request, name)
        if str(config["type"]) != "git":
            elsewhere.append(name)
        elif cache is None:
            unread.append(name)
        else:
            filtered = config.get("filter")
            caches.append(
                (cache, filtered if isinstance(filtered, dict) else None)
            )
    found: Estimate | None = (
        estimate(conn, cut(caches), pool.width()) if caches else None
    )
    return {"estimate": found, "unread": unread, "elsewhere": elsewhere}


def _wanted(
    request: Request, connection: str, form: dict[str, list[str]]
) -> list[dict[str, object]]:
    """The model rows the form asks for, upstream ids as typed."""
    with request.app.state.db.connect() as conn:
        row = store.get(conn, "connections", connection)
    kind = "" if row is None else str(json.loads(row["config"])["provider"])
    rows = defaults.models_for(kind, connection)
    for one in rows:
        one["model"] = first(form, _field(one)).strip()
    return rows


def _field(row: dict[str, object]) -> str:
    """The form field a model row's upstream id is typed into."""
    return "embedding" if row["kind"] == "embedding" else str(row["name"])


def _upstreams(rows: list[dict[str, object]]) -> dict[str, object]:
    return {_field(one): one["model"] for one in rows}


def _write_models(
    request: Request, rows: list[dict[str, object]]
) -> tuple[str, AppError] | None:
    """Register each model that is not already registered exactly so.

    A row already stored with the same config is left alone: it passed its
    probe once, and a person resuming after the third of five failed should not
    wait on, or pay for, the first two again. Returns the first refusal.
    """
    for one in rows:
        name = str(one["name"])
        with request.app.state.db.connect() as conn:
            held = store.get(conn, "models", name)
        if held is not None and _same(json.loads(held["config"]), one):
            continue
        try:
            engine.replace_item(MODELS, name, one, request)
        except AppError as exc:
            return name, exc
    return None


def _same(stored: dict[str, object], wanted: dict[str, object]) -> bool:
    return all(stored.get(key) == value for key, value in wanted.items())


async def _fetched(
    request: Request, user: User, tree: str, name: str
) -> Response:
    context = JobContext(
        request.app.state.db,
        request.app.state.cipher,
        cache_root=request.app.state.cache_root,
    )
    try:
        await run_in_threadpool(fill_cache, context, name)
    except SyncError as exc:
        return _render(
            request,
            user,
            tree,
            step="source",
            source=name,
            problems=[problem(f"saved, but it could not be read: {exc}")],
        )
    query = urlencode({"tree": tree, "step": "source", "source": name})
    return RedirectResponse(f"/ui/setup?{query}", status_code=303)


def _next(tree: str, step: str, said: str) -> Response:
    query = {"tree": tree, "step": step}
    if said:
        query["done"] = said
    return RedirectResponse(f"/ui/setup?{urlencode(query)}", status_code=303)


def dollars(amount: float | None) -> str:
    """A cost as a person reads it; unknown stays unknown, never zero."""
    if amount is None:
        return "unknown"
    return f"${amount:,.2f}" if amount >= 1 else f"${amount:.4f}"


templates.env.filters["dollars"] = dollars
templates.env.filters["taken"] = duration
