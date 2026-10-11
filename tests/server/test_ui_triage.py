"""The triage view.

Each row is a state hrono can detect. The fixture builds
every one of them at once, because a triage page that is right about four
kinds and silent about the fifth is the failure this view exists to prevent.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.cluster.incubator import park
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.health import report, triage
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs import store as job_store
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.summarize import briefs
from tests.summarize.test_shape import ECHOED, _default

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
        """The page after the report is refreshed, as a sync would leave it."""
        report.refresh(Database.adopt(self.conn), tree)  # type: ignore[arg-type]
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
    right while only ever looking at the leaves.
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
                f"A summary of node {node}: what its members hold, in brief.",
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
        # an UPPER topic nothing points at — an orphan above level 0, the one a
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
    # a zero is shown rather than hidden
    assert page.count('class="ok"') == 5  # every kind, all at zero
    assert "No run has failed" in page
    assert "Every topic can be reached from the root" in page
    # a zero carries no non-zero sentence beneath it
    for item in triage.survey(clean_tree.conn, TREE):  # type: ignore[arg-type]
        assert item.detail not in page


def test_every_kind_is_counted(messy: Browser) -> None:
    counts = messy.survey()

    assert counts["topics cut off from the root"] == 1
    assert (
        counts["topics with no usable brief, or a stale one"] == 1
    )  # the orphan
    assert counts["sections waiting for a topic"] == 1
    assert counts["sections placed without a score"] == 1
    assert counts["runs that failed"] == 1


def test_a_messy_tree_does_not_claim_to_be_clean(messy: Browser) -> None:
    messy.sign_in()

    page = messy.triage()
    assert "nothing needs attention" not in page
    for item in triage.survey(messy.conn, TREE):  # type: ignore[arg-type]
        assert item.detail in page


def test_a_non_zero_check_reads_as_a_task_in_the_singular(
    messy: Browser,
) -> None:
    messy.sign_in()
    page = messy.triage()

    assert "1 topic is cut off from the root" in page
    assert "1 section is waiting for a topic" in page
    assert "1 run has failed" in page
    assert "1 topics" not in page


def test_a_non_zero_check_is_plural_over_one() -> None:
    item = triage.Item(
        kind="k",
        count=3,
        detail="d",
        link="l",
        clear="none",
        one="1 thing",
        many="{n} things",
    )

    assert item.said == "3 things"


def test_an_unreachable_topic_links_to_the_topic_itself(
    messy: Browser,
) -> None:
    # an unreachable topic is what this view exists for, so the
    # link lands on the thing rather than on a page you then have to search
    messy.sign_in()

    page = messy.triage()

    orphan = [
        item
        for item in triage.survey(messy.conn, TREE)  # type: ignore[arg-type]
        if item.kind == "topics cut off from the root"
    ][0]
    assert f"/ui/trees/{TREE}/nodes/" in orphan.link
    assert orphan.link in page


def test_counts_are_per_tree(messy: Browser) -> None:
    # a count that silently spans trees is worse than no count
    assert messy.survey("other") == {
        "topics cut off from the root": 0,
        "topics with no usable brief, or a stale one": 0,
        "sections waiting for a topic": 0,
        "sections placed without a score": 0,
        "runs that failed": 0,
    }


def test_the_top_level_is_not_counted_as_unreachable(
    clean_tree: Browser,
) -> None:
    """The root is MEANT to have no parent.

    Counting it would put every healthy tree permanently at "1 topic nothing
    points at", which is how a triage page teaches people to ignore it.
    """
    assert clean_tree.survey()["topics cut off from the root"] == 0


def _echo(browser: Browser, nth: int = 0) -> None:
    """Settle an echo on the tree's `nth` leaf (the prompt is filed once)."""
    conn = browser.conn
    leaf = int(
        conn.execute(  # type: ignore[attr-defined]
            "SELECT id FROM nodes WHERE tree = ? AND level = 0"
            " ORDER BY id LIMIT 1 OFFSET ?",
            (TREE, nth),
        ).fetchone()[0]
    )
    with conn:  # type: ignore[attr-defined]
        if nth == 0:
            registry_store.insert(
                conn,  # type: ignore[arg-type]
                "prompts",
                "brief",
                json.dumps({"name": "brief", "template": _default("brief")}),
                None,
                "t",
            )
        briefs.upsert(
            conn,  # type: ignore[arg-type]
            leaf,
            ECHOED["brief"],
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(conn, leaf),  # type: ignore[arg-type]
            input_tokens=1,
            output_tokens=1,
            flagged="echoes-the-prompt",
        )


def _briefless_detail(browser: Browser) -> str:
    return next(
        item.detail
        for item in triage.survey(browser.conn, TREE)  # type: ignore[arg-type]
        if item.kind.startswith("topics with no usable brief")
    )


def test_a_stale_brief_says_a_sync_rewrites_it(clean_tree: Browser) -> None:
    with clean_tree.conn:  # type: ignore[attr-defined]
        clean_tree.conn.execute("UPDATE briefs SET stale = 1")  # type: ignore[attr-defined]

    assert _briefless_detail(clean_tree) == (
        "Recall cannot answer from them until a sync rewrites them."
    )


def test_a_settled_echo_does_not_promise_a_sync(clean_tree: Browser) -> None:
    _echo(clean_tree)

    detail = _briefless_detail(clean_tree)

    assert "sync" not in detail
    assert "1 needs a person" in detail

    # and several of them say "need", still with no sync promised
    with clean_tree.conn:  # type: ignore[attr-defined]
        cluster_store.add_leaf_node(
            clean_tree.conn,  # type: ignore[arg-type]
            TREE,
            [(_section(clean_tree.conn, "b.md"), False, None)],  # type: ignore[arg-type]
        )
    _echo(clean_tree, 1)

    detail = _briefless_detail(clean_tree)

    assert "sync" not in detail
    assert "2 need a person" in detail


def test_opening_the_page_works_nothing_out(clean_tree: Browser) -> None:
    # the checks run when the tree changes and on Recheck, never on opening
    clean_tree.sign_in()

    page = clean_tree.client.get(f"/ui/trees/{TREE}/triage").text

    assert "Not checked yet" in page
    assert "nothing needs attention" not in page  # unchecked is not clean
    stored = clean_tree.conn.execute(  # type: ignore[attr-defined]
        "SELECT count(*) FROM tree_health"
    ).fetchone()[0]
    assert stored == 0


def test_recheck_starts_a_health_run(clean_tree: Browser) -> None:
    clean_tree.sign_in()

    answer = clean_tree.client.post(
        f"/ui/trees/{TREE}/triage/recheck", follow_redirects=False
    )
    job = clean_tree.conn.execute(  # type: ignore[attr-defined]
        "SELECT op, tree FROM jobs WHERE op = 'health'"
    ).fetchone()

    assert answer.status_code == 303
    assert (job["op"], job["tree"]) == ("health", TREE)
    assert "Checked " in clean_tree.triage()  # a refreshed report is dated
