"""#197: every collection took `name: str`, so an EMPTY name was valid.

Found by creating a tree from the new settings page with the field blank: it
was accepted, and the switcher grew an entry nobody could select, address or
delete. The hole was never the UI's — the API had it too, in all five
collections, because each one declared its own unconstrained `name`.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hrono.registry.collections.connections import Connection
from hrono.registry.collections.models import Model
from hrono.registry.collections.prompts import Prompt
from hrono.registry.collections.sources import Source
from hrono.registry.collections.trees import Tree


def _tree(name: str) -> dict:
    return {"name": name, "sources": ["docs"]}


def _prompt(name: str) -> dict:
    return {"name": name, "role": "brief", "template": "x {content}"}


def _model(name: str) -> dict:
    return {"name": name, "kind": "text", "model": "m", "connection": None}


def _source(name: str) -> dict:
    return {
        "name": name,
        "type": "git",
        "url": "https://example.com/x.git",
        "auth": {"method": "none"},
    }


def _connection(name: str) -> dict:
    return {
        "name": name,
        "provider": "anthropic",
        "auth": {"method": "api-key", "key": "not-a-key-" + "x" * 8},
    }


BUILDERS = [
    pytest.param(Tree, _tree, id="trees"),
    pytest.param(Prompt, _prompt, id="prompts"),
    pytest.param(Model, _model, id="models"),
    pytest.param(Source, _source, id="sources"),
    pytest.param(Connection, _connection, id="connections"),
]


@pytest.mark.parametrize(("model", "build"), BUILDERS)
def test_an_empty_name_is_refused(model, build) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        model(**build(""))


@pytest.mark.parametrize(("model", "build"), BUILDERS)
def test_whitespace_is_not_a_name(model, build) -> None:  # type: ignore[no-untyped-def]
    # it renders as an empty row exactly like "" does
    with pytest.raises(ValidationError):
        model(**build("   "))


@pytest.mark.parametrize(("model", "build"), BUILDERS)
def test_a_separator_is_refused(model, build) -> None:  # type: ignore[no-untyped-def]
    """A name is a path segment: `/sources/{name}`.

    One containing a slash addresses a route that does not exist, so the row
    can be created and never read back.
    """
    with pytest.raises(ValidationError):
        model(**build("one/two"))


@pytest.mark.parametrize(("model", "build"), BUILDERS)
def test_an_ordinary_name_is_untouched(model, build) -> None:  # type: ignore[no-untyped-def]
    # the constraint must not narrow what already works
    for name in ("default", "brief-upper", "openai-main", "local_embed.v2"):
        assert model(**build(name)) is not None


@pytest.mark.parametrize(("model", "build"), BUILDERS)
def test_surrounding_whitespace_is_trimmed(model, build) -> None:  # type: ignore[no-untyped-def]
    """ "docs" and " docs" must not be two different rows."""
    made = model(**build("  docs  "))
    dumped = made.model_dump()
    inner = dumped.get("root", dumped)

    assert inner["name"] == "docs"


@pytest.mark.parametrize(("model", "build"), BUILDERS)
def test_a_name_has_an_upper_bound(model, build) -> None:  # type: ignore[no-untyped-def]
    """It is a primary key and a path segment, not a place to put a document."""
    with pytest.raises(ValidationError):
        model(**build("x" * 201))

    assert model(**build("x" * 200)) is not None
