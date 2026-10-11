"""Structure surgery from the topic page.

Everything here moves structure, so every assertion reads the STORE after the
click, not the page that reports it. The page is how an operator asks; whether
it happened is a question for `node_members`, `node_children` and `pins`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono import pins
from hrono.auth.users import create_user
from hrono.cluster import incubator
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.embed.store import upsert_vector
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.registry import store as registry_store
from hrono.server.app import create_app

KEY = Fernet.generate_key()
TREE = "default"
MODEL = "emb"
MODEL_ROW = (
    '{"name": "emb", "kind": "embedding", "connection": null, '
    '"model": "m", "params": {"dims": 2}}'
)


def _section(conn: object, path: str, vector: list[float]) -> int:
    body = f"{path} body\n".encode()
    digest = content_hash(body)
    istore.upsert_content(conn, digest, body)  # type: ignore[arg-type]
    register_path_bodies(conn, [path])  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, vector)  # type: ignore[arg-type]
    upsert_vector(  # type: ignore[arg-type]
        conn, content_hash(path_body(path)), MODEL, vector
    )
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="docs",
        address=Address("git", "ex/docs", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


class Browser:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn
        self.leaves: tuple[int, ...] = ()
        self.uppers: tuple[int, ...] = ()

    def sign_in(self, role: str = "admin") -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def page(self, node_id: int) -> str:
        return self.client.get(f"/ui/trees/{TREE}/nodes/{node_id}").text

    def post(self, path: str, **fields: str):  # type: ignore[no-untyped-def]
        return self.client.post(f"/ui/trees/{TREE}/{path}", data=fields)

    def parent_of(self, node_id: int) -> int | None:
        row = self.conn.execute(  # type: ignore[attr-defined]
            "SELECT parent_id FROM node_children WHERE child_id = ?",
            (node_id,),
        ).fetchone()
        return None if row is None else int(row["parent_id"])

    def members_of(self, node_id: int) -> set[int]:
        return {
            int(row["section_id"])
            for row in self.conn.execute(  # type: ignore[attr-defined]
                "SELECT section_id FROM node_members WHERE node_id = ?",
                (node_id,),
            ).fetchall()
        }

    def exists(self, node_id: int) -> bool:
        return (
            self.conn.execute(  # type: ignore[attr-defined]
                "SELECT 1 FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
            is not None
        )


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    """Three leaves under two upper topics, each leaf with real vectors."""
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    registry_store.insert(conn, "models", MODEL, MODEL_ROW, None, "t")
    with conn:
        a = cluster_store.add_leaf_node(
            conn,
            TREE,
            [
                (_section(conn, "a0.md", [1.0, 0.0]), False, None),
                (_section(conn, "a1.md", [1.0, 0.05]), False, None),
            ],
        )
        b = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "b0.md", [0.0, 1.0]), False, None)]
        )
        c = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "c0.md", [-1.0, 0.0]), False, None)]
        )

        def upper() -> int:
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, 1, 0, 't')",
                (TREE,),
            )
            return int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])

        left, right = upper(), upper()
        for leaf, parent in ((a, left), (b, left), (c, right)):
            cluster_store.add_child(
                conn, parent, leaf, attached=False, similarity=None
            )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        # The worker polls the SAME adopted connection this fixture writes
        # through. Two threads on one sqlite connection interleave
        # transactions, which is an intermittent failure in whichever test
        # happens to be writing when a poll lands.
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        browser = Browser(client, tokens, conn)
        browser.leaves, browser.uppers = (a, b, c), (left, right)
        yield browser
    conn.close()


def _form(page: str, action: str) -> str:
    """The one form that posts to `action`, markup and all."""
    assert f'{action}"' in page, f"no form posts to {action}"
    return page.split(f'{action}"', 1)[1].split("</form>", 1)[0]


def _offered(page: str, action: str, field: str) -> set[int]:
    """Every topic that form offers to pick, by id."""
    return {
        int(value)
        for value in re.findall(
            rf'name="{field}" value="(\d+)"', _form(page, action)
        )
    }


def test_the_parent_choices_are_exactly_one_level_up(
    browser: Browser,
) -> None:
    """Offer the right options and the rule never has to be explained.

    `reparent` refuses a parent that is not exactly one level up. An operator
    typing an id learns that from a refusal; a picker cannot offer it.
    """
    a, _, _ = browser.leaves
    left, right = browser.uppers
    browser.sign_in()

    # exactly the level above: never a leaf, never the topic itself
    assert _offered(browser.page(a), f"/nodes/{a}/reparent", "to") == {
        left,
        right,
    }


def test_the_merge_choices_are_exactly_the_same_level(
    browser: Browser,
) -> None:
    a, b, c = browser.leaves
    left, _ = browser.uppers
    browser.sign_in()

    offered = _offered(browser.page(a), f"/nodes/{a}/merge", "with")

    assert offered == {b, c}  # its own level, and not itself
    assert left not in offered


def test_a_candidate_topic_says_what_it_holds_and_links_to_it(
    browser: Browser,
) -> None:
    """Listing "topic 2, topic 3" is listing row ids; nobody merges into one.

    A picker has to answer "what IS that topic" where it is asked, and let
    an operator go and look before they fold two topics together.
    """
    a, b, c = browser.leaves
    browser.sign_in()

    offered = _form(browser.page(a), f"/nodes/{a}/merge")

    for candidate in (b, c):
        # a way to go and see it, and what it holds, beside its number
        assert f'href="/ui/trees/{TREE}/nodes/{candidate}?tree={TREE}"' in (
            offered
        )
    assert ">1 section</span>" in offered


def test_a_reparent_moves_the_topic_and_pins_it(browser: Browser) -> None:
    a, _, _ = browser.leaves
    _, right = browser.uppers
    browser.sign_in()

    browser.post(f"nodes/{a}/reparent", to=str(right))

    assert browser.parent_of(a) == right
    assert pins.reasons(browser.conn, a).get("parenting") == (  # type: ignore[arg-type]
        "reparented by hand"
    )


def test_a_reparent_the_domain_refuses_says_why(browser: Browser) -> None:
    """The domain's own words, not a reworded version that could drift.

    A leaf under a leaf: the level rule, which is the one an operator would
    otherwise have had to learn by typing an id and being told off.
    """
    a, b, _ = browser.leaves
    left, _ = browser.uppers
    browser.sign_in()

    answer = browser.post(f"nodes/{a}/reparent", to=str(b))

    assert "a parent sits exactly one level up" in answer.text
    assert browser.parent_of(a) == left


def test_a_reparent_that_would_detach_a_subtree_is_refused(
    browser: Browser,
) -> None:
    """A cycle does not fail loudly: it takes a subtree out of the export."""
    a, _, _ = browser.leaves
    left, _ = browser.uppers
    browser.sign_in()

    answer = browser.post(f"nodes/{left}/reparent", to=str(a))

    assert "below this topic" in answer.text
    assert browser.parent_of(left) is None


def test_a_merge_folds_the_topics_and_lands_on_the_survivor(
    browser: Browser,
) -> None:
    """The topic the operator was on may be the one that goes."""
    a, b, _ = browser.leaves
    browser.sign_in()
    before = browser.members_of(a) | browser.members_of(b)

    answer = browser.post(f"nodes/{b}/merge", **{"with": str(a)}, confirm="yes")

    survivor = min(a, b)
    assert not browser.exists(max(a, b))
    assert browser.members_of(survivor) == before
    assert answer.url.path.endswith(f"/nodes/{survivor}")


def test_a_merge_dissolve_or_split_without_the_tick_changes_nothing(
    browser: Browser,
) -> None:
    # the tick is checked before a split's recipe runs, so any topic will do
    a, b, _ = browser.leaves
    browser.sign_in()

    wrong = []
    for op, fields in (
        ("merge", {"with": str(a)}),
        ("dissolve", {}),
        ("split", {}),
    ):
        answer = browser.post(f"nodes/{b}/{op}", **fields)
        if not (browser.exists(a) and browser.exists(b)):
            wrong.append(f"{op}: a topic went")
        if "tick the box" not in answer.text:
            wrong.append(f"{op}: no word about the tick")

    assert wrong == []


def test_a_dissolve_retires_the_topic_and_loses_no_chunk(
    browser: Browser,
) -> None:
    """Re-placed or parked, never dropped: the no-lost-chunk invariant.

    `repair.retire` offers each member to the placement rule and parks the
    ones it declines. Asserting they land in a sibling would assert the
    RULE's verdict, which is not what dissolving promises — that nothing
    falls off the map is.
    """
    a, b, c = browser.leaves
    browser.sign_in()
    held = browser.members_of(b)

    browser.post(f"nodes/{b}/dissolve", confirm="yes")

    assert not browser.exists(b)
    assert held <= (
        browser.members_of(a) | browser.members_of(c) | _parked(browser)
    )


def _parked(browser: Browser) -> set[int]:
    return {
        section_id
        for section_id, _, _, _ in incubator.pending(browser.conn, TREE)  # type: ignore[arg-type]
    }


def test_dissolving_the_only_topic_at_its_level_is_refused(
    browser: Browser,
) -> None:
    """It would detach its children from the root, silently."""
    left, right = browser.uppers
    browser.sign_in()
    browser.post(f"nodes/{right}/dissolve", confirm="yes")  # now left is alone

    answer = browser.post(f"nodes/{left}/dissolve", confirm="yes")

    assert browser.exists(left)
    assert "only topic at its level" in answer.text


def test_a_chunk_moves_to_another_topic_and_is_pinned(
    browser: Browser,
) -> None:
    a, b, _ = browser.leaves
    browser.sign_in()
    chunk = min(browser.members_of(a))

    browser.post(f"sections/{chunk}/move", to_node=str(b), from_node=str(a))

    assert chunk in browser.members_of(b)
    assert chunk not in browser.members_of(a)
    assert pins.reasons(browser.conn, chunk).get("membership") == (  # type: ignore[arg-type]
        "moved by hand"
    )


def test_a_move_that_empties_a_topic_says_so(browser: Browser) -> None:
    """The operator holding the context is the one who can act on it."""
    _, b, c = browser.leaves
    browser.sign_in()
    chunk = min(browser.members_of(b))

    answer = browser.post(
        f"sections/{chunk}/move", to_node=str(c), from_node=str(b)
    )

    assert "now empty" in answer.text


def test_a_writer_sees_no_surgery(browser: Browser) -> None:
    """A form ACTION is what a control is; a label is what it is called.

    This asked about two labels that had already been reworded, so it passed
    on a page that offered every one of these forms.
    """
    a, b, _ = browser.leaves
    chunk = min(browser.members_of(a))
    browser.sign_in("writer")

    page = browser.page(a)

    for action in (
        f"/nodes/{a}/merge",
        f"/nodes/{a}/reparent",
        f"/nodes/{a}/dissolve",
        f"/nodes/{a}/split",
        f"/sections/{chunk}/move",
    ):
        assert action not in page
    # nor the ids it would have posted, in a picker or a menu
    assert f'value="{b}"' not in page


def test_every_surgery_route_refuses_a_writer(browser: Browser) -> None:
    """One table, every route: a door left ajar is one nobody listed.

    The floor is admin because the API's is. Hiding the control is
    courtesy; each route's own dependency is the permission, and "each" has to
    mean each.
    """
    a, b, _ = browser.leaves
    left, right = browser.uppers
    chunk = min(browser.members_of(a))
    browser.sign_in("writer")
    attempts = {
        f"nodes/{a}/reparent": {"to": str(right)},
        f"nodes/{a}/merge": {"with": str(b), "confirm": "yes"},
        f"nodes/{a}/dissolve": {"confirm": "yes"},
        f"nodes/{a}/split": {"confirm": "yes"},
        f"sections/{chunk}/move": {"to_node": str(b), "from_node": str(a)},
    }

    refused = {
        path: browser.post(path, **fields).status_code
        for path, fields in attempts.items()
    }

    assert refused == dict.fromkeys(attempts, 403)
    assert browser.parent_of(a) == left
    assert chunk in browser.members_of(a)
    assert browser.exists(a) and browser.exists(b)


def test_without_an_embedding_model_a_dissolve_says_so(
    browser: Browser,
) -> None:
    _, b, _ = browser.leaves
    with browser.conn:  # type: ignore[union-attr]
        registry_store.delete(browser.conn, "models", MODEL)  # type: ignore[arg-type]
    browser.sign_in()

    answer = browser.post(f"nodes/{b}/dissolve", confirm="yes")

    assert browser.exists(b)
    assert "no embedding model available" in answer.text


@pytest.fixture
def divisible(tmp_path: Path) -> Iterator[tuple[Browser, int]]:
    """One topic that is really two, with enough points for the real recipe.

    The clustering ladder floors at 12 points and a manual split runs
    that same recipe, so a divisible topic has at least that many members.
    """
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1] for role in ("writer", "admin")
    }
    registry_store.insert(conn, "models", MODEL, MODEL_ROW, None, "t")
    with conn:
        left = [_section(conn, f"l{i}.md", [1.0, 0.01 * i]) for i in range(8)]
        right = [_section(conn, f"r{i}.md", [0.01 * i, 1.0]) for i in range(8)]
        node = cluster_store.add_leaf_node(
            conn, TREE, [(sid, False, None) for sid in left + right]
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        # The worker polls the SAME adopted connection this fixture writes
        # through. Two threads on one sqlite connection interleave
        # transactions, which is an intermittent failure in whichever test
        # happens to be writing when a poll lands.
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, tokens, conn), node
    conn.close()


def test_a_split_divides_a_topic_and_lands_somewhere_that_exists(
    divisible: tuple[Browser, int],
) -> None:
    """The topic they were on retires, so the redirect cannot go back to it."""
    browser, node = divisible
    browser.sign_in()
    held = browser.members_of(node)

    answer = browser.post(f"nodes/{node}/split", confirm="yes")

    assert not browser.exists(node)
    landed = int(answer.url.path.rsplit("/", 1)[1])
    assert browser.exists(landed)
    assert browser.members_of(landed) < held  # a part of it, not all of it


def test_a_split_too_small_to_divide_says_so(browser: Browser) -> None:
    """The ladder's floor is not a budget: below it there is nothing to
    divide BY, and the domain says that in its own words."""
    a, _, _ = browser.leaves
    browser.sign_in()

    answer = browser.post(f"nodes/{a}/split", confirm="yes")

    assert browser.exists(a)
    assert "too few members" in answer.text
