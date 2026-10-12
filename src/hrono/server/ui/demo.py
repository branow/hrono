"""The Demo page: an agent answering from the tree, every step on screen.

With the plugin, recall and the walk of the map happen inside someone's
Claude Code session, where nobody watching can see them. This page runs the
same steps on the server (``hrono.demo``) and shows each as it happens: the
passages the hook attached, the prompt the model received, every page and
file the agent opened, lit on the map beside it, and the answer.

The model is one already set up in Settings, chosen by its connection. The
agent reads the tree's kept export, so the page asks for one first.

A turn runs on its own thread and its steps stream to the page as
Server-Sent Events, read from memory: nothing here holds a database
connection between steps.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import tempfile
import threading
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    Response,
    StreamingResponse,
)

from hrono.demo import session
from hrono.demo.agents import mcp
from hrono.demo.steps import FINAL, Step
from hrono.errors import AppError
from hrono.export import saved
from hrono.registry import store
from hrono.server import graph, prose
from hrono.server.ui import Reader, Writer, _fields, _trees, router, templates

POLL_SECONDS = 0.25


@router.get("/ui/trees/{tree}/demo", response_class=HTMLResponse)
def demo_page(request: Request, user: Reader, tree: str) -> Response:
    """The page: the model picker, the conversation and the map."""
    with request.app.state.db.connect() as conn:
        export = saved.load(conn, tree)
        connections, models = _choices(conn)
        trees = _trees(conn)
    return templates.TemplateResponse(
        request,
        "demo.html",
        {
            "user": user,
            "tree": tree,
            "trees": trees,
            "exported": None if export is None else export.built_at[:10],
            "connections": connections,
            "models": models,
            "can_write": user.role in {"writer", "admin"},
        },
    )


@router.post("/ui/trees/{tree}/demo/ask")
async def demo_ask(request: Request, user: Writer, tree: str) -> Response:
    """Start a turn; answer with where its steps will stream from."""
    fields = await _fields(request)
    question = fields.get("question", "").strip()
    if not question:
        return _problem("Type a question first.")
    talks: session.Conversations = _conversations(request)
    talk = talks.get(fields.get("conversation", ""))
    if talk is None or talk.tree != tree or talk.model != fields.get("model"):
        try:
            talk = talks.start(_place(request), tree, fields.get("model", ""))
        except AppError as exc:
            return _problem(exc.message)
    if not session.begin(talk, question):
        return _problem("The last question is still being answered.")
    after = len(talk.steps)
    threading.Thread(
        target=session.turn,
        args=(talk, request.app.state.db, question),
        name=f"demo-{talk.id[:6]}",
        daemon=True,
    ).start()
    return JSONResponse({"conversation": talk.id, "after": after})


@router.get("/ui/trees/{tree}/demo/{conversation}/steps")
async def demo_steps(
    request: Request, user: Reader, tree: str, conversation: str, after: int = 0
) -> Response:
    """The turn's steps from ``after`` on, until it is done or has failed."""
    talk = _conversations(request).get(conversation)
    if talk is None or talk.tree != tree:
        return Response(status_code=404)

    async def stream() -> AsyncIterator[str]:
        seen = after
        while not await request.is_disconnected():
            fresh = talk.steps.since(seen)
            seen += len(fresh)
            for step in fresh:
                yield f"event: step\ndata: {json.dumps(_shown(step))}\n\n"
                if step.kind in FINAL:
                    return
            await asyncio.sleep(POLL_SECONDS)

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/ui/trees/{tree}/demo/map", response_class=HTMLResponse)
def demo_map(
    request: Request, user: Reader, tree: str, visited: str = ""
) -> Response:
    """The map opened down to every topic visited, those topics lit."""
    seen = [int(part) for part in visited.split(",") if part.isdigit()]
    with request.app.state.db.connect() as conn:
        opened = _opened(conn, tree, seen)
        drawn = graph.build(conn, tree, sorted(opened))
    return templates.TemplateResponse(
        request,
        "_demo_map.html",
        {
            "graph": drawn,
            "visited": set(seen),
            "current": seen[-1] if seen else None,
        },
    )


@router.post("/demo/{conversation}/mcp")
async def demo_tools(request: Request, conversation: str) -> Response:
    """The conversation's tools over MCP, for the Claude Code CLI.

    No login: the CLI has no cookie. The conversation id is the secret, a
    random token the server made and passed only to the CLI and the page
    that started it.
    """
    talk = _conversations(request).get(conversation)
    if talk is None:
        return Response(status_code=404)
    try:
        message = json.loads(await request.body())
    except ValueError:
        return Response(status_code=400)
    if not isinstance(message, dict):
        return Response(status_code=400)
    reply = await asyncio.to_thread(mcp.answer, message, talk.library)
    if reply is None:
        return Response(status_code=202)
    return JSONResponse(reply)


def _conversations(request: Request) -> session.Conversations:
    state = request.app.state
    if not hasattr(state, "demos"):
        state.demos = session.Conversations()
    return state.demos


def _place(request: Request) -> session.Place:
    """Where the agent runs: the server's own CLI directory and address.

    The CLI runs on this machine, so it reaches the server at the local
    address the request came in on.
    """
    state = request.app.state
    root = getattr(state, "cache_root", None)
    workdir = (
        Path(root).parent / "cli"
        if root is not None
        else Path(tempfile.gettempdir()) / "hrono-cli"
    )
    host, port = request.scope.get("server") or ("127.0.0.1", 80)
    host = f"[{host}]" if ":" in str(host) else host
    return session.Place(
        database=state.db,
        cipher=getattr(state, "cipher", None),
        workdir=workdir,
        root=f"http://{host}:{port}",
    )


def _choices(
    conn: sqlite3.Connection,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Every connection, and every text model with the connection it uses."""
    connections = [
        {
            "name": str(row["name"]),
            "provider": str(json.loads(row["config"]).get("provider") or ""),
        }
        for row in store.list_all(conn, "connections")
    ]
    models = []
    for row in store.list_all(conn, "models"):
        config = json.loads(row["config"])
        if config.get("kind") == "text" and config.get("connection"):
            models.append(
                {
                    "name": str(row["name"]),
                    "model": str(config.get("model") or ""),
                    "connection": str(config["connection"]),
                }
            )
    return connections, models


def _opened(conn: sqlite3.Connection, tree: str, seen: list[int]) -> set[int]:
    """The visited topics and every topic above them; the root at least."""
    parent = {
        int(row["child"]): int(row["parent"])
        for row in conn.execute(
            "SELECT c.parent_id AS parent, c.child_id AS child "
            "FROM node_children c JOIN nodes n ON n.id = c.parent_id "
            "WHERE n.tree = ?",
            (tree,),
        ).fetchall()
    }
    root = conn.execute(
        "SELECT id FROM nodes WHERE tree = ? ORDER BY level DESC, id LIMIT 1",
        (tree,),
    ).fetchone()
    opened = {int(root["id"])} if root else set()
    for node in seen:
        while node not in opened:
            opened.add(node)
            if node not in parent:
                break
            node = parent[node]
    return opened


def _shown(step: Step) -> dict[str, object]:
    """A step as the page receives it; model text also comes as HTML."""
    data = dict(step.data)
    if step.kind in ("answer", "say"):
        data["html"] = prose.markdown(str(data.get("text") or ""))
    return {"kind": step.kind, **data}


def _problem(message: str) -> Response:
    return JSONResponse({"problem": message}, status_code=409)
