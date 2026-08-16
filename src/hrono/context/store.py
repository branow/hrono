"""Named client contexts persisted in ``config.toml``.

A context tells a client subcommand which server to talk to and with what token.
The file holds a bearer token, so it is created owner-only (``0600``) under an
owner-only directory (``0700``). Access goes through an injectable path so tests
never touch the real ``~/.hrono``.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w


class DuplicateContext(Exception):
    """A context with this name already exists."""

    def __init__(self, name: str) -> None:
        super().__init__("context already exists")
        self.name = name


class UnknownContext(Exception):
    """No context with this name is registered."""

    def __init__(self, name: str) -> None:
        super().__init__("unknown context")
        self.name = name


class MalformedConfig(Exception):
    """The config file is not valid TOML or has the wrong shape."""

    def __init__(self, path: Path) -> None:
        super().__init__("malformed config")
        self.path = path


@dataclass(frozen=True)
class Context:
    name: str
    server_url: str
    token: str
    default_tree: str | None = None


@dataclass(frozen=True)
class State:
    contexts: tuple[Context, ...]
    current: str | None


def config_path() -> Path:
    """Resolve the config file location, honouring ``HRONO_HOME``."""
    home = os.environ.get("HRONO_HOME")
    base = Path(home) if home else Path.home() / ".hrono"
    return base / "config.toml"


class Store:
    """Load/save/CRUD of contexts over one injectable config path."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def contexts(self) -> tuple[Context, ...]:
        return _read(self._path).contexts

    def current(self) -> Context | None:
        state = _read(self._path)
        if state.current is None:
            return None
        return next(
            (c for c in state.contexts if c.name == state.current), None
        )

    def add(self, context: Context) -> None:
        _write(self._path, _add(_read(self._path), context))

    def use(self, name: str) -> None:
        _write(self._path, _use(_read(self._path), name))

    def remove(self, name: str) -> bool:
        state, cleared = _remove(_read(self._path), name)
        _write(self._path, state)
        return cleared


def _add(state: State, context: Context) -> State:
    if any(c.name == context.name for c in state.contexts):
        raise DuplicateContext(context.name)
    current = state.current if state.current is not None else context.name
    return State(state.contexts + (context,), current)


def _use(state: State, name: str) -> State:
    if not any(c.name == name for c in state.contexts):
        raise UnknownContext(name)
    return State(state.contexts, name)


def _remove(state: State, name: str) -> tuple[State, bool]:
    if not any(c.name == name for c in state.contexts):
        raise UnknownContext(name)
    remaining = tuple(c for c in state.contexts if c.name != name)
    cleared = state.current == name
    return State(remaining, None if cleared else state.current), cleared


def _read(path: Path) -> State:
    if not path.exists():
        return State((), None)
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
        return _parse(document)
    except (
        tomllib.TOMLDecodeError,
        KeyError,
        TypeError,
        AttributeError,
    ) as exc:
        raise MalformedConfig(path) from exc


def _parse(document: object) -> State:
    if not isinstance(document, dict):
        raise TypeError
    raw = document.get("contexts", {})
    if not isinstance(raw, dict):
        raise TypeError
    contexts = tuple(_context(name, table) for name, table in raw.items())
    current = document.get("current")
    if current is not None and not isinstance(current, str):
        raise TypeError
    return State(contexts, current)


def _context(name: str, table: object) -> Context:
    if not isinstance(table, dict):
        raise TypeError
    server_url = table["server_url"]
    token = table["token"]
    default_tree = table.get("default_tree")
    if not isinstance(server_url, str) or not isinstance(token, str):
        raise TypeError
    if default_tree is not None and not isinstance(default_tree, str):
        raise TypeError
    return Context(name, server_url, token, default_tree)


def _write(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        tomli_w.dump(_document(state), handle)
    os.chmod(path, 0o600)


def _document(state: State) -> dict[str, object]:
    document: dict[str, object] = {}
    if state.current is not None:
        document["current"] = state.current
    document["contexts"] = {c.name: _table(c) for c in state.contexts}
    return document


def _table(context: Context) -> dict[str, str]:
    table = {"server_url": context.server_url, "token": context.token}
    if context.default_tree is not None:
        table["default_tree"] = context.default_tree
    return table
