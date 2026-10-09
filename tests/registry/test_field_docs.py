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

import pytest
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
    pytest.param(model, name, id=f"{d.collection}.{model.__name__}.{name}")
    for d in COLLECTIONS
    for model in _models(d.model)
    for name in model.model_fields
    if name != "root"
]


def test_the_walk_reaches_nested_and_union_models() -> None:
    """A walk that stopped at the RootModel would check nothing at all."""
    names = {param.values[0].__name__ for param in FIELDS}  # type: ignore[union-attr]

    assert {"GitSource", "GitAuth", "GitFilter", "Selector"} <= names
    assert {"ClaudeCodeConnection", "ModelPrice", "Prompt", "Tree"} <= names


@pytest.mark.parametrize(("model", "name"), FIELDS)
def test_every_field_has_a_label_and_help(
    model: type[BaseModel], name: str
) -> None:
    info = model.model_fields[name]

    assert info.title, f"{model.__name__}.{name} has no title"
    assert info.description, f"{model.__name__}.{name} has no description"
    assert info.title != name, "a label that is the key says nothing new"
