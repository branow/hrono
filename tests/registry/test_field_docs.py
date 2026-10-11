"""Every registry field carries a human label and one line of help.

The settings form reads both off the collection's own pydantic model, so the
API's validation and the page cannot drift. A field added without them would
render as its raw config path with nothing saying what it does — the state the
page was rebuilt to leave — and this is what stops that at review time rather
than on the screen.
"""

from __future__ import annotations

import types
import typing
from collections.abc import Iterator

from pydantic import BaseModel

from hrono.registry.collections import COLLECTIONS


def _models(model: type[BaseModel]) -> Iterator[type[BaseModel]]:
    """A model and every model reachable from its fields, unions included."""
    seen: set[type[BaseModel]] = set()
    queue = [model]
    while queue:
        current = queue.pop()
        if current in seen:
            continue
        seen.add(current)
        yield current
        for info in current.model_fields.values():
            queue.extend(_nested(info.annotation))


def _nested(annotation: object) -> list[type[BaseModel]]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return [annotation]
    origin = typing.get_origin(annotation)
    if origin is None and not isinstance(annotation, types.UnionType):
        return []
    found: list[type[BaseModel]] = []
    for arg in typing.get_args(annotation):
        found.extend(_nested(arg))
    return found


FIELDS = [
    (f"{d.collection}.{model.__name__}.{name}", model, name)
    for d in COLLECTIONS
    for model in _models(d.model)
    for name in model.model_fields
    if name != "root"
]


def test_the_walk_reaches_nested_and_union_models() -> None:
    """A walk that stopped at the RootModel would check nothing at all."""
    names = {model.__name__ for _, model, _ in FIELDS}

    assert {"GitSource", "GitAuth", "GitFilter", "Selector"} <= names
    assert {"ClaudeCodeConnection", "ModelPrice", "Prompt", "Tree"} <= names


def test_every_field_has_a_label_and_help() -> None:
    # one pass over every field, naming each one that falls short
    failures = []
    for where, model, name in FIELDS:
        info = model.model_fields[name]
        if not info.title:
            failures.append(f"{where} has no title")
        elif info.title == name:
            failures.append(f"{where}: a label that is the key says nothing")
        if not info.description:
            failures.append(f"{where} has no description")

    assert not failures, "\n".join(failures)
