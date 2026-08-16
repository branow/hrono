"""Named client profiles persisted in ``config.toml``.

A profile tells a client subcommand which server to talk to and with what token.
The file holds a bearer token, so it is created owner-only (``0600``) under an
owner-only directory (``0700``). Access goes through an injectable path so tests
never touch the real ``~/.hrono``. (kubectl/gh call this a context.)
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

import tomli_w
from platformdirs import user_config_dir

from hrono.errors import BadRequest, Conflict, NotFound


class DuplicateProfile(Conflict):
    """A profile with this name already exists."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Profile '{name}' already exists.")
        self.name = name


class UnknownProfile(NotFound):
    """No profile with this name is registered."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown profile '{name}'.")
        self.name = name


class MalformedConfig(BadRequest):
    """The config file is not valid TOML or has the wrong shape."""

    def __init__(self, path: Path) -> None:
        super().__init__(f"Malformed config at {path}: fix or remove it.")
        self.path = path


@dataclass(frozen=True)
class Profile:
    name: str
    server_url: str
    token: str
    default_tree: str | None = None


@dataclass(frozen=True)
class State:
    profiles: tuple[Profile, ...]
    current: str | None


def config_path() -> Path:
    """Resolve the config file location per OS, honouring ``HRONO_HOME``.

    ``HRONO_HOME`` wins everywhere. Otherwise Windows uses the per-user config
    dir (``%APPDATA%\\hrono`` via platformdirs); macOS and Linux keep the Unix
    dotfolder ``~/.hrono`` (the CLI-tool convention). Only the default location
    differs, and only on Windows.
    """
    home = os.environ.get("HRONO_HOME")
    if home:
        base = Path(home)
    elif sys.platform == "win32":
        base = Path(user_config_dir("hrono", roaming=True))
    else:
        base = Path.home() / ".hrono"
    return base / "config.toml"


class Store:
    """Load/save/CRUD of profiles over one injectable config path."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def profiles(self) -> tuple[Profile, ...]:
        return _read(self._path).profiles

    def current(self) -> Profile | None:
        state = _read(self._path)
        if state.current is None:
            return None
        return next(
            (p for p in state.profiles if p.name == state.current), None
        )

    def add(self, profile: Profile) -> None:
        _write(self._path, _add(_read(self._path), profile))

    def use(self, name: str) -> None:
        _write(self._path, _use(_read(self._path), name))

    def remove(self, name: str) -> bool:
        state, cleared = _remove(_read(self._path), name)
        _write(self._path, state)
        return cleared


def _add(state: State, profile: Profile) -> State:
    if any(p.name == profile.name for p in state.profiles):
        raise DuplicateProfile(profile.name)
    current = state.current if state.current is not None else profile.name
    return State(state.profiles + (profile,), current)


def _use(state: State, name: str) -> State:
    if not any(p.name == name for p in state.profiles):
        raise UnknownProfile(name)
    return State(state.profiles, name)


def _remove(state: State, name: str) -> tuple[State, bool]:
    if not any(p.name == name for p in state.profiles):
        raise UnknownProfile(name)
    remaining = tuple(p for p in state.profiles if p.name != name)
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
    raw = document.get("profiles", {})
    if not isinstance(raw, dict):
        raise TypeError
    profiles = tuple(_profile(name, table) for name, table in raw.items())
    current = document.get("current")
    if current is not None and not isinstance(current, str):
        raise TypeError
    return State(profiles, current)


def _profile(name: str, table: object) -> Profile:
    if not isinstance(table, dict):
        raise TypeError
    server_url = table["server_url"]
    token = table["token"]
    default_tree = table.get("default_tree")
    if not isinstance(server_url, str) or not isinstance(token, str):
        raise TypeError
    if default_tree is not None and not isinstance(default_tree, str):
        raise TypeError
    return Profile(name, server_url, token, default_tree)


def _write(path: Path, state: State) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # POSIX owner-only perms; on Windows the file lands in the user-scoped
    # AppData dir and POSIX mode bits do not apply, so skip them cleanly.
    if os.name == "posix":
        os.chmod(path.parent, 0o700)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        tomli_w.dump(_document(state), handle)
    if os.name == "posix":
        os.chmod(path, 0o600)


def _document(state: State) -> dict[str, object]:
    document: dict[str, object] = {}
    if state.current is not None:
        document["current"] = state.current
    document["profiles"] = {p.name: _table(p) for p in state.profiles}
    return document


def _table(profile: Profile) -> dict[str, str]:
    table = {"server_url": profile.server_url, "token": profile.token}
    if profile.default_tree is not None:
        table["default_tree"] = profile.default_tree
    return table
