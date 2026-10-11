"""Every collection refuses an EMPTY name.

A tree created from the settings page with the field blank would otherwise be
accepted, and the switcher would grow an entry nobody could select, address or
delete. The rule belongs to the API, not the UI: all five collections share
one constrained `name` rather than each declaring an unconstrained one.
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


# the empty name runs over all five, which proves each one uses the shared
# constrained type; the other rules then need only one of them
@pytest.mark.parametrize(("model", "build"), BUILDERS)
def test_an_empty_name_is_refused(model, build) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValidationError):
        model(**build(""))


def test_whitespace_is_not_a_name() -> None:
    # it renders as an empty row exactly like "" does
    with pytest.raises(ValidationError):
        Tree(**_tree("   "))


def test_a_separator_is_refused() -> None:
    """A name is a path segment: `/sources/{name}`.

    One containing a slash addresses a route that does not exist, so the row
    can be created and never read back.
    """
    with pytest.raises(ValidationError):
        Tree(**_tree("one/two"))


def test_an_ordinary_name_is_untouched() -> None:
    # the constraint must not narrow what already works
    for name in ("default", "brief-upper", "openai-main", "local_embed.v2"):
        assert Tree(**_tree(name)) is not None


def test_surrounding_whitespace_is_trimmed() -> None:
    """ "docs" and " docs" must not be two different rows."""
    made = Tree(**_tree("  docs  "))
    dumped = made.model_dump()
    inner = dumped.get("root", dumped)

    assert inner["name"] == "docs"


def test_a_name_has_an_upper_bound() -> None:
    """It is a primary key and a path segment, not a place to put a document."""
    with pytest.raises(ValidationError):
        Tree(**_tree("x" * 201))

    assert Tree(**_tree("x" * 200)) is not None
