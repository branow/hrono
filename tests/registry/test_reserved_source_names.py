"""#076: `node-` is hrono's own source namespace, not a user's."""

import pytest
from pydantic import ValidationError

from hrono.registry.sources import RESERVED_PREFIX, GitSource


def _source(name: str) -> GitSource:
    return GitSource(
        name=name,
        type="git",
        url="https://example.com/repo.git",
        auth={"method": "none"},  # type: ignore[arg-type]
    )


@pytest.mark.parametrize("name", ["node-5", "node-anything", "NODE-5"])
def test_a_reserved_source_name_is_refused(name: str) -> None:
    # brief passages live under `node-<id>` in the same namespace a user
    # registers into, and `store_brief` CLEARS that key before re-writing — so
    # a user source called `node-5` loses its passages and FTS rows to node 5's
    # next re-brief. Silent cross-deletion, in a namespace the user has no
    # reason to know is shared. Upper-case too: the wipe matches on the stored
    # string, so refusing only the lower-case spelling would leave the hole.
    with pytest.raises(ValidationError, match="reserved"):
        _source(name)


@pytest.mark.parametrize(
    "name", ["node", "nodes", "node_five", "my-node-5", "nodejs-docs"]
)
def test_an_ordinary_name_that_mentions_node_is_fine(name: str) -> None:
    # the reservation is a PREFIX, not the word: `nodejs-docs` is an entirely
    # reasonable repo to ingest.
    assert _source(name).name == name


def test_the_reserved_prefix_is_the_one_brief_passages_use() -> None:
    # the two must not drift apart: if #071's key shape ever changes, this
    # fails rather than leaving a reservation that guards nothing.
    from hrono.recall.brief_passages import SOURCE_TYPE

    assert f"{SOURCE_TYPE}-" == RESERVED_PREFIX
