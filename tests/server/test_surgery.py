"""Surgery on the tree by hand: #158's node operations and #160's section move.

Several of these already existed as pipeline primitives; what is new is the
operator's hand on them, the pin that keeps the result, and the refusals that
stop a hand-edit corrupting the tree. Each test checks the tree AFTER, not the
status code.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono import pins
from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.cluster.incubator import count as incubator_count
from hrono.cluster.incubator import park
from hrono.cluster.levels import migrate_children
from hrono.cluster.repair import migrate
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.embed.store import upsert_vector
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.recall.brief_passages import store_brief
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"
OTHER_TREE = "other"
MODEL = "emb"


class Harness:
    def __init__(self, client: TestClient, conn: object, token: str) -> None:
        self.client = client
        self.conn = conn
        self.headers = {"Authorization": f"Bearer {token}"}


def _section(conn: object, path: str, vector: list[float]) -> int:
    from hrono.cluster.blend import path_body, register_path_bodies

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


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[tuple[Harness, dict]]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    registry_store.insert(
        conn,
        "models",
        MODEL,
        '{"name": "emb", "kind": "embedding", "connection": null, '
        '"model": "m", "params": {"dims": 2}}',
        None,
        "t",
    )
    ids: dict[str, int] = {}
    with conn:
        alpha = _section(conn, "a.md", [1.0, 0.0])
        beta = _section(conn, "b.md", [0.9, 0.1])
        gamma = _section(conn, "c.md", [0.0, 1.0])
        ids["first"] = cluster_store.add_leaf_node(
            conn, TREE, [(alpha, False, None)]
        )
        ids["second"] = cluster_store.add_leaf_node(
            conn, TREE, [(beta, False, None)]
        )
        delta = _section(conn, "d.md", [0.0, 0.95])
        ids["third"] = cluster_store.add_leaf_node(
            conn, TREE, [(gamma, False, None)]
        )
        ids["fourth"] = cluster_store.add_leaf_node(
            conn, TREE, [(delta, False, None)]
        )
        ids["alpha"], ids["beta"] = alpha, beta
        ids["gamma"], ids["delta"] = gamma, delta
        # a node's brief vector is what the upper level sorts it by, so the
        # topics it belongs WITH is what these say: first/second are one
        # subject, third/fourth another.
        subject = {
            ids["first"]: [1.0, 0.0],
            ids["second"]: [1.0, 0.0],
            ids["third"]: [0.0, 1.0],
            ids["fourth"]: [0.0, 1.0],
        }
        for node in (
            ids["first"],
            ids["second"],
            ids["third"],
            ids["fourth"],
        ):
            text = f"A summary of topic {node}."
            briefs.upsert(
                conn,
                node,
                text,
                model_name="m",
                prompt_name="brief",
                prompt_hash="h",
                member_signature=briefs.member_signature(conn, node),
                input_tokens=1,
                output_tokens=1,
            )
            # the brief's vector is keyed by its own content hash, and the
            # vector table FKs content -- so the text has to be stored the
            # way `brief` stores it, not just embedded.
            istore.upsert_content(
                conn, content_hash(text.encode()), text.encode()
            )
            upsert_vector(
                conn, content_hash(text.encode()), MODEL, subject[node]
            )
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 0, 't')",
            (TREE,),
        )
        ids["parent"] = int(
            conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0]
        )
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 1, 't')",
            (TREE,),
        )
        ids["other_parent"] = int(
            conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0]
        )
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 2, 0, 't')",
            (TREE,),
        )
        ids["grandparent"] = int(
            conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0]
        )
        for child in (ids["first"], ids["second"]):
            cluster_store.add_child(
                conn, ids["parent"], child, attached=False, similarity=None
            )
        for child in (ids["third"], ids["fourth"]):
            cluster_store.add_child(
                conn,
                ids["other_parent"],
                child,
                attached=False,
                similarity=None,
            )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, conn, token), ids
    conn.close()


def _parent_of(h: Harness, child: int) -> int | None:
    row = h.conn.execute(
        "SELECT parent_id FROM node_children WHERE child_id = ?", (child,)
    ).fetchone()
    return None if row is None else int(row["parent_id"])


def _members(h: Harness, node: int) -> set[int]:
    return {
        int(r["section_id"])
        for r in h.conn.execute(
            "SELECT section_id FROM node_members WHERE node_id = ?", (node,)
        ).fetchall()
    }


def test_reparent_moves_the_node_and_pins_it(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/nodes/{ids['third']}/reparent",
        json={"to": ids["parent"]},
        headers=h.headers,
    )

    assert response.status_code == 200
    assert _parent_of(h, ids["third"]) == ids["parent"]
    assert pins.is_pinned(h.conn, pins.PARENTING, ids["third"]) is True
    assert pins.anchors(h.conn, pins.PARENTING)[ids["third"]] == ids["parent"]


def test_a_node_cannot_be_reparented_under_itself_or_its_own_child(
    harness: tuple[Harness, dict],
) -> None:
    # a cycle does not fail loudly: it detaches a subtree from the root and the
    # export simply stops mentioning it.
    h, ids = harness

    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/{ids['parent']}/reparent",
            json={"to": ids["parent"]},
            headers=h.headers,
        ).status_code
        == 422
    )
    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/{ids['parent']}/reparent",
            json={"to": ids["first"]},
            headers=h.headers,
        ).status_code
        == 422
    )
    assert _parent_of(h, ids["first"]) == ids["parent"]  # unchanged


def test_merge_folds_members_into_the_lowest_id(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness
    merged = sorted([ids["first"], ids["second"]])

    response = h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["second"], ids["first"]]},  # order must not matter
        headers=h.headers,
    )

    assert response.status_code == 200
    assert response.json()["node_id"] == merged[0]
    assert _members(h, merged[0]) == {ids["alpha"], ids["beta"]}
    assert (
        h.conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (merged[1],)
        ).fetchone()
        is None
    )


def test_merge_leaves_no_orphaned_brief_or_passage(
    harness: tuple[Harness, dict],
) -> None:
    # #125: a retired node's summary must not outlive it, and a merge retires
    # nodes the same way a rebuild does.
    h, ids = harness
    gone = max(ids["first"], ids["second"])

    h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["first"], ids["second"]]},
        headers=h.headers,
    )

    assert briefs.get(h.conn, gone) is None
    left = h.conn.execute(
        "SELECT COUNT(*) FROM sections WHERE source = ?", (f"node-{gone}",)
    ).fetchone()[0]
    assert int(left) == 0


def test_merge_pins_the_result_but_not_its_brief(
    harness: tuple[Harness, dict],
) -> None:
    # the operator decided these belong together, so membership holds; the
    # merged topic genuinely needs a NEW summary, so the brief does not.
    h, ids = harness
    survivor = min(ids["first"], ids["second"])

    h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["first"], ids["second"]]},
        headers=h.headers,
    )

    assert pins.pinned(h.conn, pins.MEMBERSHIP) == {ids["alpha"], ids["beta"]}
    assert pins.is_pinned(h.conn, pins.BRIEF, survivor) is False


def test_merge_needs_two_distinct_nodes(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness
    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/merge",
            json={"ids": [ids["first"], ids["first"]]},
            headers=h.headers,
        ).status_code
        == 422
    )


def _node_of(h: Harness, section: int) -> int | None:
    row = h.conn.execute(
        "SELECT m.node_id AS id FROM node_members m JOIN nodes n "
        "ON n.id = m.node_id WHERE m.section_id = ? AND n.tree = ?",
        (section, TREE),
    ).fetchone()
    return None if row is None else int(row["id"])


def test_dissolve_retires_the_topic_and_re_places_its_members(
    harness: tuple[Harness, dict],
) -> None:
    # every member gets a NEW HOME, which is the half of "dissolve" that the
    # node's death does not prove: a member left in no node at all is a chunk
    # recall can no longer reach, and the node is just as gone either way.
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/nodes/{ids['third']}/dissolve", headers=h.headers
    )

    assert response.status_code == 200
    assert (
        h.conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (ids["third"],)
        ).fetchone()
        is None
    )
    home = _node_of(h, ids["gamma"])
    assert home is not None and home != ids["third"]
    assert response.json()["members"] == {
        "joined": 1,
        "parked": 0,
        "skipped": 0,
    }
    # nothing is pinned: the operator asked for a re-placement, not a new home
    assert ids["gamma"] not in pins.pinned(h.conn, pins.MEMBERSHIP)


def test_dissolve_works_on_a_topic_of_any_size(
    harness: tuple[Harness, dict],
) -> None:
    # `repair.dissolve` carries the automatic repair's BELOW-TWO rule, and an
    # operator is not asking about size. Routed through it, this endpoint
    # reported success over a node it had left standing, having already
    # released the membership pins of every member on the way past.
    h, ids = harness
    h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["first"], ids["second"]]},
        headers=h.headers,
    )
    survivor = min(ids["first"], ids["second"])
    assert len(_members(h, survivor)) == 2

    response = h.client.post(
        f"/trees/{TREE}/nodes/{survivor}/dissolve", headers=h.headers
    )

    assert response.status_code == 200
    assert (
        h.conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (survivor,)
        ).fetchone()
        is None
    )
    for section in (ids["alpha"], ids["beta"]):
        assert _node_of(h, section) != survivor
    counts = response.json()["members"]
    assert counts["joined"] + counts["parked"] + counts["skipped"] == 2


def test_dissolve_reports_a_member_it_could_not_place(
    harness: tuple[Harness, dict],
) -> None:
    # a member whose best topic scores below TAU is PARKED, not placed, and
    # "2 members replaced" would have said it found them homes (#133).
    h, ids = harness

    # delta finds a home: `third` is the same subject, well above TAU
    first = h.client.post(
        f"/trees/{TREE}/nodes/{ids['fourth']}/dissolve", headers=h.headers
    )
    assert first.json()["members"] == {"joined": 1, "parked": 0, "skipped": 0}

    # now BOTH of them have nowhere to go: what is left of the tree is the
    # other subject entirely, and nothing there scores TAU.
    second = h.client.post(
        f"/trees/{TREE}/nodes/{ids['third']}/dissolve", headers=h.headers
    )

    assert second.json()["members"] == {"joined": 0, "parked": 2, "skipped": 0}
    for section in (ids["gamma"], ids["delta"]):
        assert _node_of(h, section) is None  # parked, not placed


def _children(h: Harness, node: int) -> set[int]:
    return {
        int(r["child_id"])
        for r in h.conn.execute(
            "SELECT child_id FROM node_children WHERE parent_id = ?", (node,)
        ).fetchall()
    }


def test_merging_upper_topics_carries_every_child_of_both(
    harness: tuple[Harness, dict],
) -> None:
    # an upper topic's content is its CHILDREN. #158 refused this rather than
    # guess; #163 is the rule: they come with it, or the loser's child edges
    # cascade away and a whole subtree leaves the root and the export.
    h, ids = harness
    survivor = min(ids["parent"], ids["other_parent"])
    gone = max(ids["parent"], ids["other_parent"])

    response = h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["parent"], ids["other_parent"]]},
        headers=h.headers,
    )

    assert response.status_code == 200
    assert response.json()["node_id"] == survivor
    assert _children(h, survivor) == {
        ids["first"],
        ids["second"],
        ids["third"],
        ids["fourth"],
    }
    assert (
        h.conn.execute("SELECT 1 FROM nodes WHERE id = ?", (gone,)).fetchone()
        is None
    )
    for node in ("first", "second", "third", "fourth"):
        assert _parent_of(h, ids[node]) == survivor
        # the operator put them together, so the pipeline may not take them
        # apart -- the upper twin of the membership pin a leaf merge sets
        assert pins.is_pinned(h.conn, pins.PARENTING, ids[node]) is True


def test_a_merge_folds_more_than_two(harness: tuple[Harness, dict]) -> None:
    # the AC says "retires the OTHERS", and every other merge test here folds
    # exactly one, so the loop over the losers was unguarded (#158 po review).
    h, ids = harness
    three = [ids["first"], ids["second"], ids["third"]]
    survivor = min(three)

    response = h.client.post(
        f"/trees/{TREE}/nodes/merge", json={"ids": three}, headers=h.headers
    )

    assert response.status_code == 200
    assert _members(h, survivor) == {ids["alpha"], ids["beta"], ids["gamma"]}
    for node in three:
        if node == survivor:
            continue
        assert (
            h.conn.execute(
                "SELECT 1 FROM nodes WHERE id = ?", (node,)
            ).fetchone()
            is None
        )


def test_merge_refuses_to_mix_levels(harness: tuple[Harness, dict]) -> None:
    # the survivor is the lowest id, which is deterministic and says nothing
    # about which node is the right KIND: a leaf would have survived and taken
    # a whole branch's place.
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["first"], ids["parent"]]},
        headers=h.headers,
    )

    assert response.status_code == 422
    assert _children(h, ids["parent"]) == {ids["first"], ids["second"]}
    assert _members(h, ids["first"]) == {ids["alpha"]}


def test_dissolving_an_upper_topic_re_places_its_children(
    harness: tuple[Harness, dict],
) -> None:
    # the upper twin of a leaf dissolve: the members that re-enter the rule are
    # CHILDREN, and they go to a SIBLING of the retired node -- never to its
    # grandparent, which would put them two levels under their parent.
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/nodes/{ids['other_parent']}/dissolve",
        headers=h.headers,
    )

    assert response.status_code == 200
    assert (
        h.conn.execute(
            "SELECT 1 FROM nodes WHERE id = ?", (ids["other_parent"],)
        ).fetchone()
        is None
    )
    for node in ("third", "fourth"):
        assert _parent_of(h, ids[node]) == ids["parent"]
    assert response.json()["members"]["joined"] == 2


def test_dissolving_the_only_topic_at_its_level_is_refused(
    harness: tuple[Harness, dict],
) -> None:
    # with no sibling left there is nowhere for the children to go, and doing
    # it anyway would detach them from the root -- which is the harm #163
    # exists to close, not a thing to do on request.
    h, ids = harness
    h.client.post(
        f"/trees/{TREE}/nodes/{ids['other_parent']}/dissolve",
        headers=h.headers,
    )

    response = h.client.post(
        f"/trees/{TREE}/nodes/{ids['parent']}/dissolve", headers=h.headers
    )

    assert response.status_code == 422
    assert "nowhere to go" in response.json()["error"]["message"]
    assert _children(h, ids["parent"])


def test_reparent_refuses_a_parent_that_is_not_one_level_up(
    harness: tuple[Harness, dict],
) -> None:
    # a leaf under a leaf broke 0012_node_children.sql's invariant in one
    # keystroke, and the pin made it permanent.
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/nodes/{ids['third']}/reparent",
        json={"to": ids["first"]},
        headers=h.headers,
    )

    assert response.status_code == 422
    assert "one level up" in response.json()["error"]["message"]
    assert _parent_of(h, ids["third"]) == ids["other_parent"]
    assert pins.is_pinned(h.conn, pins.PARENTING, ids["third"]) is False

    # and the other direction: a parent TOO FAR up skips a level, which leaves
    # the tree just as broken as a parent beside the node.
    skipped = h.client.post(
        f"/trees/{TREE}/nodes/{ids['third']}/reparent",
        json={"to": ids["grandparent"]},
        headers=h.headers,
    )

    assert skipped.status_code == 422
    assert _parent_of(h, ids["third"]) == ids["other_parent"]


def test_surgery_is_admin_only(harness: tuple[Harness, dict]) -> None:
    h, ids = harness
    conn = h.conn
    writer = create_user(conn, "writer", "writer")[1]
    headers = {"Authorization": f"Bearer {writer}"}

    for path, body in (
        (f"/trees/{TREE}/nodes/{ids['third']}/reparent", {"to": 1}),
        (f"/trees/{TREE}/nodes/merge", {"ids": [1, 2]}),
        (f"/trees/{TREE}/nodes/{ids['third']}/dissolve", None),
    ):
        response = h.client.post(path, json=body, headers=headers)
        assert response.status_code == 403


def test_an_id_this_tree_does_not_hold_is_not_found(
    harness: tuple[Harness, dict],
) -> None:
    # PO ruling 2026-09-24: 422 is for a conflict between ids that both live
    # in THIS tree; an id the tree does not hold is a 404, another tree's
    # included -- the API must not answer differently because of the contents
    # of a tree the caller did not ask about.
    h, ids = harness
    with h.conn:
        foreign = cluster_store.add_leaf_node(
            h.conn, OTHER_TREE, [(ids["alpha"], False, None)]
        )

    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/{ids['third']}/reparent",
            json={"to": foreign},
            headers=h.headers,
        ).status_code
        == 404
    )
    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/merge",
            json={"ids": [ids["first"], foreign]},
            headers=h.headers,
        ).status_code
        == 404
    )
    assert (
        h.client.post(
            f"/trees/{TREE}/nodes/99999/reparent",
            json={"to": ids["parent"]},
            headers=h.headers,
        ).status_code
        == 404
    )
    assert _parent_of(h, ids["third"]) == ids["other_parent"]  # unchanged


def test_dissolve_of_an_unknown_id_without_an_embedding_model(
    tmp_path: Path,
) -> None:
    # the endpoint resolved the embedding model before it confirmed the node,
    # so a server with no model answered an unknown id with a 500. Found by
    # driving a real `hrono serve`, which the test client cannot show: its
    # fixtures always have a model registered.
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    app = create_app(connection=conn, master_key=KEY, key_id=1)

    with TestClient(app) as client:
        response = client.post(
            f"/trees/{TREE}/nodes/99999/dissolve",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 404
    conn.close()


def test_merge_leaves_another_trees_membership_alone(
    harness: tuple[Harness, dict],
) -> None:
    # a section can be a member in more than one tree -- the primary key is
    # (node_id, section_id) -- so a merge that deletes membership by SECTION
    # alone reaches into a tree nobody asked it to touch.
    h, ids = harness
    with h.conn:
        elsewhere = cluster_store.add_leaf_node(
            h.conn, OTHER_TREE, [(ids["beta"], False, None)]
        )

    h.client.post(
        f"/trees/{TREE}/nodes/merge",
        json={"ids": [ids["first"], ids["second"]]},
        headers=h.headers,
    )

    assert _members(h, elsewhere) == {ids["beta"]}


def test_a_reparented_node_survives_the_pipeline(
    harness: tuple[Harness, dict],
) -> None:
    # the pin is not the point; what the pin BUYS is. `migrate_children` is
    # the upper-level rule that would take the node back by proximity, and
    # this corpus is built so that it wants to: `third`'s brief sits with
    # `fourth` under other_parent, so its own subject scores higher there.
    h, ids = harness
    h.client.post(
        f"/trees/{TREE}/nodes/{ids['third']}/reparent",
        json={"to": ids["parent"]},
        headers=h.headers,
    )

    with h.conn:
        assert migrate_children(h.conn, TREE, 1, MODEL) == 0
    assert _parent_of(h, ids["third"]) == ids["parent"]

    # and it is the pin doing it, not an absent better home
    with h.conn:
        pins.unpin(h.conn, pins.PARENTING, ids["third"])
        assert migrate_children(h.conn, TREE, 1, MODEL) == 1
    assert _parent_of(h, ids["third"]) == ids["other_parent"]


def test_a_section_moves_into_the_topic_a_human_chose(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/sections/{ids['gamma']}/move",
        json={"to_node": ids["first"]},
        headers=h.headers,
    )

    assert response.status_code == 200
    assert response.json()["from_node"] == ids["third"]
    assert _members(h, ids["first"]) == {ids["alpha"], ids["gamma"]}
    assert _members(h, ids["third"]) == set()
    assert pins.is_pinned(h.conn, pins.MEMBERSHIP, ids["gamma"]) is True
    assert pins.anchors(h.conn, pins.MEMBERSHIP)[ids["gamma"]] == ids["first"]


def test_a_moved_section_carries_no_invented_similarity(
    harness: tuple[Harness, dict],
) -> None:
    # it was placed by a human, not by proximity. A score here would be a
    # number nobody measured, and the misfit monitor acts on those numbers.
    h, ids = harness

    h.client.post(
        f"/trees/{TREE}/sections/{ids['gamma']}/move",
        json={"to_node": ids["first"]},
        headers=h.headers,
    )

    row = h.conn.execute(
        "SELECT attached, assignment_similarity AS sim, forced FROM "
        "node_members WHERE node_id = ? AND section_id = ?",
        (ids["first"], ids["gamma"]),
    ).fetchone()
    assert row["sim"] is None
    assert int(row["attached"]) == 0
    assert int(row["forced"]) == 0


def test_a_moved_section_is_not_migrated_back(
    harness: tuple[Harness, dict],
) -> None:
    # gamma sits with `first` only because a human put it there; by proximity
    # it belongs with `fourth`, which is exactly when the monitor moves a chunk
    # and the operator watches their own correction undone.
    #
    # ONE migrate run decides both members of the node, and the pin is the only
    # difference between them: gamma stays, alpha -- which nobody pinned and
    # which now fits `second` better -- leaves. A run that moved neither would
    # prove nothing about the pin.
    h, ids = harness
    h.client.post(
        f"/trees/{TREE}/sections/{ids['gamma']}/move",
        json={"to_node": ids["first"]},
        headers=h.headers,
    )

    with h.conn:
        migrate(h.conn, TREE, ids["first"], MODEL)

    assert ids["gamma"] in _members(h, ids["first"])
    assert ids["alpha"] not in _members(h, ids["first"])


def test_a_section_cannot_be_filed_under_an_upper_topic(
    harness: tuple[Harness, dict],
) -> None:
    # a topic above the leaves is made of topics, not chunks.
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/sections/{ids['gamma']}/move",
        json={"to_node": ids["parent"]},
        headers=h.headers,
    )

    assert response.status_code == 422
    assert "level 1" in response.json()["error"]["message"]
    assert _members(h, ids["third"]) == {ids["gamma"]}
    assert ids["gamma"] not in pins.pinned(h.conn, pins.MEMBERSHIP)


def test_a_parked_chunk_can_be_filed_under_a_topic(
    harness: tuple[Harness, dict],
) -> None:
    # the case an operator most needs this for: a chunk the placement rule
    # declined is in NO topic, so it is invisible in the map until the
    # incubator's own rules happen to reach it.
    h, ids = harness
    with h.conn:
        homeless = _section(h.conn, "homeless.md", [0.4, 0.4])
        park(h.conn, TREE, homeless, 1)

    response = h.client.post(
        f"/trees/{TREE}/sections/{homeless}/move",
        json={"to_node": ids["first"]},
        headers=h.headers,
    )

    assert response.status_code == 200
    assert response.json()["from_node"] is None
    assert homeless in _members(h, ids["first"])
    # joining unparks: clustered AND pending is the state that must not exist
    assert incubator_count(h.conn, TREE) == 0
    assert pins.anchors(h.conn, pins.MEMBERSHIP)[homeless] == ids["first"]


def test_a_section_move_refuses_what_this_tree_does_not_hold(
    harness: tuple[Harness, dict],
) -> None:
    h, ids = harness
    with h.conn:
        foreign = cluster_store.add_leaf_node(
            h.conn, OTHER_TREE, [(ids["alpha"], False, None)]
        )
        loose = _section(h.conn, "loose.md", [0.5, 0.5])
        # the pending pool is one table for every tree, and only its query
        # scopes it: without that scope an operator here could pull another
        # tree's homeless chunk into this map.
        parked_elsewhere = _section(h.conn, "theirs.md", [0.5, 0.5])
        park(h.conn, OTHER_TREE, parked_elsewhere, 1)

    for section, node, expected in (
        (ids["gamma"], foreign, 404),  # a real node, another tree's
        (ids["gamma"], 99999, 404),  # no such node
        (loose, ids["first"], 404),  # a real section, in no node OR pool here
        (99999, ids["first"], 404),  # no such section
        (parked_elsewhere, ids["first"], 404),  # parked, in ANOTHER tree
    ):
        response = h.client.post(
            f"/trees/{TREE}/sections/{section}/move",
            json={"to_node": node},
            headers=h.headers,
        )
        assert response.status_code == expected, (section, node)

    assert _members(h, ids["third"]) == {ids["gamma"]}
    assert pins.pinned(h.conn, pins.MEMBERSHIP) == frozenset()
    assert incubator_count(h.conn, OTHER_TREE) == 1  # still theirs
    assert parked_elsewhere not in _members(h, ids["first"])


def test_a_section_move_is_admin_only(harness: tuple[Harness, dict]) -> None:
    h, ids = harness
    writer = create_user(h.conn, "writer2", "writer")[1]

    response = h.client.post(
        f"/trees/{TREE}/sections/{ids['gamma']}/move",
        json={"to_node": ids["first"]},
        headers={"Authorization": f"Bearer {writer}"},
    )

    assert response.status_code == 403
    assert _members(h, ids["third"]) == {ids["gamma"]}


def test_a_move_that_empties_a_topic_says_so(
    harness: tuple[Harness, dict],
) -> None:
    # the pipeline retires an empty topic on its next repair and #125's trigger
    # takes the summary with it -- but the operator holding the context only
    # gets to act on it if anyone tells them (#165).
    h, ids = harness

    response = h.client.post(
        f"/trees/{TREE}/sections/{ids['gamma']}/move",
        json={"to_node": ids["first"]},
        headers=h.headers,
    )

    assert _members(h, ids["third"]) == set()
    note = response.json()["note"]
    assert f"topic {ids['third']} is now empty" in note
    assert "dissolve" in note


def test_a_chunk_from_the_pool_empties_nothing(
    harness: tuple[Harness, dict],
) -> None:
    # a parked chunk came from NO topic (#164), so there is none to empty. The
    # note is built from `from_node`, and without this the operator would be
    # told "topic None is now empty".
    h, ids = harness
    with h.conn:
        homeless = _section(h.conn, "pooled.md", [0.4, 0.4])
        park(h.conn, TREE, homeless, 1)

    response = h.client.post(
        f"/trees/{TREE}/sections/{homeless}/move",
        json={"to_node": ids["first"]},
        headers=h.headers,
    )

    assert response.json()["from_node"] is None
    assert "note" not in response.json()


def test_a_move_that_leaves_a_topic_standing_is_quiet(
    harness: tuple[Harness, dict],
) -> None:
    # a note every time is noise that teaches people to skip notes (#167)
    h, ids = harness
    h.client.post(
        f"/trees/{TREE}/sections/{ids['beta']}/move",
        json={"to_node": ids["third"]},
        headers=h.headers,
    )
    with h.conn:
        extra = _section(h.conn, "extra.md", [0.0, 0.9])
        cluster_store.add_member(
            h.conn, ids["third"], extra, forced=False, similarity=None
        )

    response = h.client.post(
        f"/trees/{TREE}/sections/{extra}/move",
        json={"to_node": ids["first"]},
        headers=h.headers,
    )

    assert _members(h, ids["third"])  # still holds gamma and beta
    assert "note" not in response.json()


def test_the_emptied_topic_stops_answering_once_dissolved(
    harness: tuple[Harness, dict],
) -> None:
    """The loop the note points at, closed end to end.

    The note tells the operator the topic still answers recall from its
    summary. Dissolving it is what stops that, and #125's trigger is what
    makes dissolving enough — the `node://` passages go with the node.
    """
    h, ids = harness
    emptied = ids["third"]
    with h.conn:
        store_brief(h.conn, emptied, "A summary of a topic about gamma.", "sig")
    assert _brief_passages(h, emptied)

    h.client.post(
        f"/trees/{TREE}/sections/{ids['gamma']}/move",
        json={"to_node": ids["first"]},
        headers=h.headers,
    )
    assert _brief_passages(h, emptied)  # still answering, as the note says

    h.client.post(f"/trees/{TREE}/nodes/{emptied}/dissolve", headers=h.headers)

    assert _brief_passages(h, emptied) == 0


def _brief_passages(h: Harness, node: int) -> int:
    return int(
        h.conn.execute(
            "SELECT COUNT(*) FROM passages WHERE source_type = 'node' "
            "AND source = ?",
            (f"node-{node}",),
        ).fetchone()[0]
    )
