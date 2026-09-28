"""#185 (T52): the triage view.

Each row is a state some earlier ticket learned to detect. The fixture builds
every one of them at once, because a triage page that is right about four
kinds and silent about the fifth is the failure this view exists to prevent.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.cluster.incubator import park
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs import store as job_store
from hrono.server import triage
from hrono.server.app import create_app
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"


def _section(conn: object, path: str) -> int:
    body = f"{path} body\n".encode()
    digest = content_hash(body)
    istore.upsert_content(conn, digest, body)  # type: ignore[arg-type]
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
    def __init__(self, client: TestClient, token: str, conn: object) -> None:
        self.client = client
        self.token = token
        self.conn = conn

    def sign_in(self) -> None:
        self.client.post("/ui/login", data={"token": self.token})

    def triage(self, tree: str = TREE) -> str:
        return self.client.get(f"/ui/trees/{tree}/triage").text

    def survey(self, tree: str = TREE) -> dict[str, int]:
        return {
            item.kind: item.count
            for item in triage.survey(self.conn, tree)  # type: ignore[arg-type]
        }


@pytest.fixture
def clean_tree(tmp_path: Path) -> Iterator[Browser]:
    """A tree with nothing wrong, THREE levels deep.

    Three and not two on purpose: with a two-level tree, "every level below the
    top" and "level 0 only" are the same set, and the orphan check would look
    right while only ever looking at the leaves (#163).
    """
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    with conn:
        leaf = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "a.md"), False, None)]
        )

        def upper(level: int) -> int:
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, ?, 0, 't')",
                (TREE, level),
            )
            return int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])

        mid, root = upper(1), upper(2)
        cluster_store.add_child(
            conn, mid, leaf, attached=False, similarity=None
        )
        cluster_store.add_child(
            conn, root, mid, attached=False, similarity=None
        )
        for node in (leaf, mid, root):
            briefs.upsert(
                conn,
                node,
                f"A summary of {node}.",
                model_name="m",
                prompt_name="brief",
                prompt_hash="h",
                member_signature="sig",
                input_tokens=1,
                output_tokens=1,
            )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, token, conn)
    conn.close()


@pytest.fixture
def messy(clean_tree: Browser) -> Browser:
    """Every kind of trouble at once."""
    conn = clean_tree.conn
    with conn:  # type: ignore[union-attr]
        # an UPPER topic nothing points at — the #163 shape, and the one a
        # leaf-level check cannot see because its own child IS parented
        conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 9, 't')",
            (TREE,),
        )

        # a forced placement nobody scored
        leaf = int(
            conn.execute(  # type: ignore[attr-defined]
                "SELECT MIN(id) FROM nodes WHERE tree = ? AND level = 0",
                (TREE,),
            ).fetchone()[0]
        )
        cluster_store.add_member(
            conn,
            leaf,
            _section(conn, "forced.md"),
            forced=True,
            similarity=None,
        )
        park(conn, TREE, _section(conn, "parked.md"), 1)  # type: ignore[arg-type]
        job_store.insert(conn, "job_x", None, TREE, "sync", "{}", "t")  # type: ignore[arg-type]
        job_store.set_status(conn, "job_x", "failed", "boom", "t")  # type: ignore[arg-type]
    return clean_tree


def test_a_clean_tree_says_it_is_clean(clean_tree: Browser) -> None:
    # the answer an operator most wants, and one a blank page cannot give
    clean_tree.sign_in()

    page = clean_tree.triage()

    assert "nothing needs attention in default." in page


def test_every_kind_is_counted(messy: Browser) -> None:
    counts = messy.survey()

    assert counts["topics nothing points at"] == 1
    assert counts["topics with no brief, or a stale one"] == 1  # the orphan
    assert counts["chunks in no topic"] == 1
    assert counts["chunks placed without a score"] == 1
    assert counts["runs that failed"] == 1


def test_a_messy_tree_does_not_claim_to_be_clean(messy: Browser) -> None:
    messy.sign_in()

    assert "nothing needs attention" not in messy.triage()


def test_an_unreachable_topic_links_to_the_topic_itself(
    messy: Browser,
) -> None:
    # the defect that shipped twice is the one this view exists for, so the
    # link lands on the thing rather than on a page you then have to search
    messy.sign_in()

    page = messy.triage()

    orphan = [
        item
        for item in triage.survey(messy.conn, TREE)  # type: ignore[arg-type]
        if item.kind == "topics nothing points at"
    ][0]
    assert f"/ui/trees/{TREE}/nodes/" in orphan.link
    assert orphan.link in page


def test_a_zero_is_shown_rather_than_hidden(clean_tree: Browser) -> None:
    clean_tree.sign_in()

    page = clean_tree.triage()

    assert page.count('class="ok"') == 5  # every kind, all at zero
    assert "runs that failed" in page


def test_counts_are_per_tree(messy: Browser) -> None:
    # #054: a count that silently spans trees is worse than no count
    assert messy.survey("other") == {
        "topics nothing points at": 0,
        "topics with no brief, or a stale one": 0,
        "chunks in no topic": 0,
        "chunks placed without a score": 0,
        "runs that failed": 0,
    }


def test_the_top_level_is_not_counted_as_unreachable(
    clean_tree: Browser,
) -> None:
    """The root is MEANT to have no parent.

    Counting it would put every healthy tree permanently at "1 topic nothing
    points at", which is how a triage page teaches people to ignore it.
    """
    assert clean_tree.survey()["topics nothing points at"] == 0


def test_no_internal_ticket_numbers_reach_the_page(
    clean_tree: Browser,
) -> None:
    """#197: the most demo-able screen printed "(#124, #163)" and "(#113)".

    Our issue numbers mean nothing to the person looking at the page, and
    invite a question nobody wants to answer in a demo.
    """
    clean_tree.sign_in()

    page = clean_tree.triage()

    assert "#1" not in page
    assert not re.search(r"\(#\d+", page)
