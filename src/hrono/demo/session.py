"""A demo conversation, and the turn that runs one question through it.

A turn is what the plugin does around a real session: recall the question,
attach what came back, hand the prompt to the agent. Each part is a step, so
the page can show it as it happens. A conversation lives in the server's
memory only; a restart forgets it, which costs nothing but the scroll-back.
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.demo import prompts
from hrono.demo.agents import Agent
from hrono.demo.agents.anthropic import AnthropicChat
from hrono.demo.agents.claude_code import ClaudeCode
from hrono.demo.agents.loop import Chat, Looped
from hrono.demo.agents.openai import OpenAIChat
from hrono.demo.steps import Steps
from hrono.demo.tools import Library
from hrono.embed.runner import EmbedError
from hrono.errors import Conflict, Invalid, Unavailable
from hrono.export import saved
from hrono.llm import client as anthropic_client
from hrono.llm import openai
from hrono.llm.client import LLMError
from hrono.llm.ledger import Call, record
from hrono.recall.ask import ask
from hrono.registry import store

log = logging.getLogger(__name__)

KEPT = 20  # conversations kept in memory; the oldest goes first


@dataclass(frozen=True)
class Place:
    """Where the server runs the agent from and serves it the tools."""

    database: Database
    cipher: Cipher | None
    workdir: Path  # the CLI's empty working directory
    root: str  # how the CLI reaches this server, e.g. http://127.0.0.1:8000


@dataclass
class Conversation:
    """One conversation: its tree, its model, its steps and its agent."""

    id: str
    tree: str
    model: str
    steps: Steps
    library: Library
    agent: Agent | None = None
    busy: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class Conversations:
    """The conversations this server holds, by id."""

    def __init__(self) -> None:
        self._held: OrderedDict[str, Conversation] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, ident: str) -> Conversation | None:
        with self._lock:
            return self._held.get(ident)

    def start(self, place: Place, tree: str, model: str) -> Conversation:
        """A new conversation with ``model`` over ``tree``'s kept export."""
        with place.database.connect() as conn:
            export = saved.load(conn, tree)
            config = _model(conn, model)
            provider = _provider(conn, config)
        if export is None:
            raise Conflict(
                f"tree has no export: {tree}", details={"tree": tree}
            )
        steps = Steps()
        talk = Conversation(
            id=secrets.token_urlsafe(16),
            tree=tree,
            model=model,
            steps=steps,
            library=Library(place.database, tree, export, steps),
        )
        talk.agent = _agent(place, talk, config, provider)
        with self._lock:
            self._held[talk.id] = talk
            while len(self._held) > KEPT:
                self._held.popitem(last=False)
        return talk


def begin(talk: Conversation, question: str) -> bool:
    """Claim the conversation for a turn; False while one is running."""
    with talk.lock:
        if talk.busy:
            return False
        talk.busy = True
        return True


def turn(talk: Conversation, database: Database, question: str) -> None:
    """Run one question through recall and the agent, adding its steps.

    Runs on its own thread after ``begin``; every failure ends the turn as a
    ``failed`` step, so the page never waits on a turn that is gone.
    """
    steps = talk.steps
    try:
        steps.add("asked", text=question)
        attached = _recall(talk, database, question)
        prompt = prompts.prompt(question, attached)
        steps.add("prompt", text=prompt, system=prompts.system(talk.tree))
        assert talk.agent is not None
        talk.agent.turn(prompt)
        steps.add("done")
    except LLMError as exc:
        steps.add("failed", message=str(exc))
    except Exception:
        log.exception("demo turn failed")
        steps.add("failed", message="the turn failed on the server")
    finally:
        with talk.lock:
            talk.busy = False


def _recall(
    talk: Conversation, database: Database, question: str
) -> str | None:
    """What the plugin's hook would attach, shown as a step either way."""
    try:
        found = ask(database, talk.tree, question, prompts.LIMIT)
    except (Unavailable, EmbedError) as exc:
        talk.steps.add("recall", hits=[], problem=str(exc))
        return None
    attached = prompts.attachment(talk.tree, found.hits)
    talk.steps.add(
        "recall",
        hits=[
            {
                "title": prompts.title(hit),
                "kind": "brief" if hit.kind == "summary" else "source",
                "score": round(hit.score, 3),
                "topic": hit.topic,
            }
            for hit in found.hits
        ],
        refused=found.message,
    )
    return attached


def _model(conn: object, name: str) -> dict[str, object]:
    row = store.get(conn, "models", name)  # type: ignore[arg-type]
    config = json.loads(row["config"]) if row is not None else None
    if not isinstance(config, dict) or config.get("kind") != "text":
        raise Invalid(f"no text model: {name}", details={"model": name})
    if not config.get("connection"):
        raise Invalid(
            f"model has no connection: {name}", details={"model": name}
        )
    return config


def _provider(conn: object, config: dict[str, object]) -> str:
    row = store.get(conn, "connections", str(config["connection"]))  # type: ignore[arg-type]
    if row is None:
        raise Invalid(
            f"unknown connection: {config['connection']}",
            details={"connection": config["connection"]},
        )
    return str(json.loads(row["config"]).get("provider") or "anthropic")


def _agent(
    place: Place, talk: Conversation, config: dict[str, object], provider: str
) -> Agent:
    """The agent loop this model's connection calls for."""
    model = str(config["model"])
    system = prompts.system(talk.tree)

    def write(call: Call) -> None:
        record(place.database, None, call)

    if provider == "claude-code":
        return ClaudeCode(
            model=model,
            system=system,
            url=f"{place.root}/demo/{talk.id}/mcp",
            workdir=place.workdir,
            steps=talk.steps,
            record=write,
        )
    return Looped(
        chat=_chat(place, config, provider, system),
        library=talk.library,
        steps=talk.steps,
        record=write,
        model=str(config.get("name") or model),
        provider=provider,
    )


def _chat(
    place: Place, config: dict[str, object], provider: str, system: str
) -> Chat:
    model = str(config["model"])
    if provider == "anthropic":
        if place.cipher is None:
            raise Invalid("no cipher to read the connection's key")
        key, endpoint = anthropic_client.credential(
            place.database, place.cipher, config["connection"]
        )
        return AnthropicChat(
            key=key, endpoint=endpoint, model=model, system=system
        )
    if provider in ("openai", "openai-compatible"):
        key, base = openai.credential(
            place.database, place.cipher, config["connection"]
        )
        return OpenAIChat(key=key, base=base, model=model, system=system)
    raise Invalid(
        f"the demo cannot run a {provider} connection",
        details={"provider": provider},
    )
