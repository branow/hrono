"""E011: search, the outline and the file lookup, for a reader (#208).

The searched tree is built the way production builds one — a git source
through `maintain` — so a section's text, its passages, its FTS rows and its
topic arrive by the writer rather than by a fixture that happens to agree
with the reader.
"""

import json
import re
import sqlite3
from collections.abc import Iterator
from urllib.parse import quote

import pytest
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import incubator
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.registry import store as registry_store
from hrono.server import find
from hrono.server.app import create_app
from tests.server import test_map_at_scale as at_scale
from tests.server.test_ui_ask import KEY, TREE, Panel
from tests.server.test_ui_ask import panel as panel  # noqa: PLC0414


def page(p: Panel, route: str, **query: str) -> str:
    p.client.post("/ui/login", data={"token": p.token})
    args = "&".join(f"{k}={quote(v)}" for k, v in query.items())
    return p.client.get(f"/ui/trees/{TREE}/{route}?tree={TREE}&{args}").text


def topic_of(p: Panel, path: str) -> int:
    return int(
        p.conn.execute(
            "SELECT m.node_id FROM node_members m JOIN sections s "
            "ON s.id = m.section_id WHERE s.path = ?",
            (path,),
        ).fetchone()[0]
    )


def test_a_word_only_in_a_sections_text_finds_the_section_and_its_topic(
    panel: Panel,
) -> None:
    html = page(panel, "find", q="module 7")

    sections = html[html.index('aria-label="section matches"') :]
    assert "f7.txt" in sections
    assert "f3.txt" not in sections
    home = topic_of(panel, "f7.txt")
    assert f"/nodes/{home}?tree={TREE}#section-" in sections
    assert "<mark>module</mark>" in sections


def test_a_word_in_a_brief_finds_its_topic(panel: Panel) -> None:
    html = page(panel, "find", q="related things")

    assert 'aria-label="topic matches"' in html
    assert "brief</span>" in html
    assert 'aria-label="section matches"' not in html


def test_a_name_a_person_gave_is_found_though_no_passage_holds_it(
    panel: Panel,
) -> None:
    admin = create_user(panel.conn, "ada", "admin")[1]
    panel.conn.commit()
    node = topic_of(panel, "f2.txt")
    panel.client.patch(
        f"/trees/{TREE}/nodes/{node}",
        json={"title": "Zanzibar ledger"},
        headers={"Authorization": f"Bearer {admin}"},
    )

    html = page(panel, "find", q="zanzibar")

    assert "Zanzibar ledger" in html
    assert "named by hand" in html


def test_another_trees_text_is_not_found(panel: Panel) -> None:
    panel.client.post("/ui/login", data={"token": panel.token})

    html = panel.client.get("/ui/trees/elsewhere/find?q=module").text

    assert "Nothing contains all of those words" in html


@pytest.mark.parametrize(
    "query",
    ['"', "module OR", "module*", "NEAR(", "a:b", "^x", "module -"],
)
def test_fts_syntax_in_a_query_is_only_words(panel: Panel, query: str) -> None:
    p = panel
    p.client.post("/ui/login", data={"token": p.token})

    answer = p.client.get(f"/ui/trees/{TREE}/find", params={"q": query})

    assert answer.status_code == 200


def test_a_snippet_cannot_carry_markup() -> None:
    shown = find._marked("<img src=x onerror=1>\x02hit\x03")

    assert shown == "&lt;img src=x onerror=1&gt;<mark>hit</mark>"


def test_the_outline_lists_every_topic_and_each_row_opens_its_page(
    panel: Panel,
) -> None:
    html = page(panel, "outline", open="all")

    total = panel.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0]
    ids = {int(i) for i in re.findall(rf"/nodes/(\d+)\?tree={TREE}", html)}
    assert ids == {
        int(r[0]) for r in panel.conn.execute("SELECT id FROM nodes")
    }
    assert f"{total} topics" in html
    assert 'class="chip ok"' in html


def test_the_outline_collapses_below_the_top_and_expands_on_request(
    panel: Panel,
) -> None:
    depth = panel.conn.execute("SELECT MAX(level) FROM nodes").fetchone()[0]
    assert depth >= 2, "the fixture tree must be deep enough to collapse"

    closed = page(panel, "outline")
    every = page(panel, "outline", open="all")

    assert closed.count("<details open>") == 1
    assert closed.count("<details>") >= 1
    assert every.count("<details>") == 0
    assert every.count("<details open>") == 1 + closed.count("<details>")


def test_a_stale_brief_shows_as_needing_one(panel: Panel) -> None:
    node = topic_of(panel, "f4.txt")
    panel.conn.execute("UPDATE briefs SET stale = 1 WHERE node_id = ?", (node,))
    panel.conn.commit()

    html = page(panel, "outline", open="all")

    assert html.count("needs a brief</span>") >= 1


def test_a_file_lists_its_sections_with_their_topics(panel: Panel) -> None:
    html = page(panel, "files", path="f5.txt")

    home = topic_of(panel, "f5.txt")
    assert "section 1, bytes 0–" in html
    assert f"/nodes/{home}?tree={TREE}#section-" in html
    assert "f6.txt" not in html


def test_a_prefix_lists_every_file_under_it(panel: Panel) -> None:
    html = page(panel, "files", path="./f1")

    assert "f1.txt" in html
    assert "f10.txt" in html
    assert "f11.txt" in html
    assert "f2.txt" not in html


def test_an_unknown_path_says_it_is_not_ingested(panel: Panel) -> None:
    html = page(panel, "files", path="nowhere/at/all.py")

    assert "Not ingested" in html


def test_a_parked_section_says_it_is_parked(panel: Panel) -> None:
    section = int(
        panel.conn.execute(
            "SELECT id FROM sections WHERE path = 'f8.txt'"
        ).fetchone()[0]
    )
    panel.conn.execute(
        "DELETE FROM node_members WHERE section_id = ?", (section,)
    )
    incubator.park(panel.conn, TREE, section, 1)
    panel.conn.commit()

    html = page(panel, "files", path="f8.txt")
    found = page(panel, "find", q="module 8")

    assert ">parked</span>" in html
    assert "not in any topic yet" in html
    assert ">parked</span>" in found


def test_the_search_box_is_on_every_page_and_the_tab_is_marked(
    panel: Panel,
) -> None:
    for route in ("find", "outline", "files"):
        html = page(panel, route)
        assert 'role="search"' in html.split("<main")[0]
        assert re.search(
            r'class="tab" href="[^"]*/find[^"]*" aria-current', html
        )
    node = topic_of(panel, "f1.txt")
    for url in (
        "/ui",
        f"/ui/trees/{TREE}/graph",
        f"/ui/trees/{TREE}/ask",
        f"/ui/trees/{TREE}/nodes/{node}",
        "/ui/jobs",
        "/ui/guide",
    ):
        html = panel.client.get(url).text
        assert 'role="search"' in html.split("<main")[0], url


# -- the outline at the size people build ----------------------------------


@pytest.fixture(scope="module")
def big(tmp_path_factory: pytest.TempPathFactory) -> Iterator[TestClient]:
    path = tmp_path_factory.mktemp("big") / "hrono.db"
    conn = open_database(path)
    reconcile(conn, KEY)
    token = create_user(conn, "rita", "reader")[1]
    groups, leaves = 25, 20
    with conn:
        uppers = []
        for group in range(groups):
            family = []
            for index in range(leaves):
                leaf = at_scale.cluster_store.add_leaf_node(
                    conn,
                    TREE,
                    [
                        (
                            at_scale._section(
                                conn, f"src/g{group}/m{index}.py"
                            ),
                            False,
                            None,
                        )
                    ],
                )
                at_scale._brief(conn, leaf, f"Handles part {group}.{index}.")
                family.append(leaf)
            upper = at_scale._parent(conn, 1, family)
            at_scale._brief(conn, upper, f"Handles group {group}.")
            uppers.append(upper)
        root = at_scale._parent(conn, 2, uppers)
        at_scale._brief(conn, root, "Everything.")
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        client.post("/ui/login", data={"token": token})
        yield client
    conn.close()


def test_the_outline_holds_five_hundred_topics(big: TestClient) -> None:
    html = big.get(f"/ui/trees/{TREE}/outline?tree={TREE}").text

    assert "526 topics" in html
    assert html.count("/nodes/") >= 526
    assert "src/g0" in html


def test_a_five_hundred_topic_outline_rolls_sections_up(
    big: TestClient,
) -> None:
    html = big.get(f"/ui/trees/{TREE}/outline?tree={TREE}").text

    assert "500 sections beneath this topic" in html
    assert "20 sections beneath this topic" in html


def test_find_sections_never_returns_a_brief_as_a_file(
    panel: Panel,
) -> None:
    rows: list[sqlite3.Row] = panel.conn.execute(
        "SELECT path FROM sections WHERE source_type = 'node' LIMIT 1"
    ).fetchall()
    assert rows, "the fixture tree must hold briefs as node sections"

    located = find.lookup(panel.conn, TREE, "nodes/")

    assert located.files == ()


def test_a_section_parked_in_another_tree_is_not_this_trees(
    panel: Panel,
) -> None:
    section = int(
        panel.conn.execute(
            "SELECT id FROM sections WHERE path = 'f9.txt'"
        ).fetchone()[0]
    )
    panel.conn.execute(
        "DELETE FROM node_members WHERE section_id = ?", (section,)
    )
    incubator.park(panel.conn, "elsewhere", section, 1)
    panel.conn.commit()
    panel.client.post("/ui/login", data={"token": panel.token})

    here = panel.client.get(f"/ui/trees/{TREE}/find?q=module+9").text
    there = panel.client.get("/ui/trees/elsewhere/find?q=module+9").text

    assert "f9.txt" not in here
    assert "f9.txt" in there


def test_a_word_in_many_sections_does_not_crowd_out_a_brief(
    panel: Panel, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(find, "CANDIDATES", 2)

    html = page(panel, "find", q="module")

    assert 'aria-label="topic matches"' in html
    assert 'aria-label="section matches"' in html


def file_in_other_tree(p: Panel, path: str) -> int:
    """Move a section out of this tree's topics into a topic of another."""
    section = int(
        p.conn.execute(
            "SELECT id FROM sections WHERE path = ?", (path,)
        ).fetchone()[0]
    )
    p.conn.execute("DELETE FROM node_members WHERE section_id = ?", (section,))
    node = p.conn.execute(
        "INSERT INTO nodes(tree, level, label, created_at) "
        "VALUES ('elsewhere', 0, -1, 't')"
    ).lastrowid
    p.conn.execute(
        "INSERT INTO node_members(node_id, section_id, attached, created_at) "
        "VALUES (?, ?, 0, 't')",
        (node, section),
    )
    incubator.park(p.conn, TREE, section, 1)
    p.conn.commit()
    return int(node or 0)


def test_a_topic_of_another_tree_is_not_linked_from_this_one(
    panel: Panel,
) -> None:
    other = file_in_other_tree(panel, "f9.txt")

    found = page(panel, "find", q="module 9")
    files = page(panel, "files", path="f9.txt")

    for html in (found, files):
        assert "f9.txt" in html
        assert f"/nodes/{other}" not in html
        assert ">parked</span>" in html


def test_another_trees_source_sharing_a_path_is_not_this_trees(
    panel: Panel,
) -> None:
    mine = str(
        panel.conn.execute(
            "SELECT source FROM sections WHERE path = 'f1.txt'"
        ).fetchone()[0]
    )
    registry_store.insert(
        panel.conn,
        "trees",
        TREE,
        json.dumps({"name": TREE, "sources": [mine]}),
        None,
        "t",
    )
    body = b"another source\n"
    istore.upsert_content(panel.conn, content_hash(body), body)
    for path in ("f1.txt", "only/theirs.txt"):
        istore.insert_section(
            panel.conn,
            source="crypto",
            address=Address("git", "ex/crypto", path, "v1"),
            start=0,
            end=len(body),
            content_hash=content_hash(body),
            ordinal=0,
        )
    panel.conn.commit()

    shared = find.lookup(panel.conn, TREE, "f1.txt")
    theirs = page(panel, "files", path="only/theirs.txt")

    assert {file.source for file in shared.files} == {mine}
    assert "Not ingested" in theirs


def leave_every_source_out(p: Panel) -> None:
    """The tree's entry now names no source its sections come from."""
    registry_store.insert(
        p.conn,
        "trees",
        TREE,
        json.dumps({"name": TREE, "sources": ["dropped-source"]}),
        None,
        "t",
    )
    p.conn.commit()


def test_a_section_still_filed_here_outlives_its_source_leaving_the_tree(
    panel: Panel,
) -> None:
    leave_every_source_out(panel)

    html = page(panel, "files", path="f5.txt")

    assert "Not ingested" not in html
    assert f"/nodes/{topic_of(panel, 'f5.txt')}?tree={TREE}#section-" in html


def test_a_section_still_parked_here_outlives_its_source_leaving_the_tree(
    panel: Panel,
) -> None:
    section = int(
        panel.conn.execute(
            "SELECT id FROM sections WHERE path = 'f8.txt'"
        ).fetchone()[0]
    )
    panel.conn.execute(
        "DELETE FROM node_members WHERE section_id = ?", (section,)
    )
    incubator.park(panel.conn, TREE, section, 1)
    panel.conn.commit()
    leave_every_source_out(panel)

    html = page(panel, "files", path="f8.txt")

    assert "Not ingested" not in html
    assert ">parked</span>" in html


def test_a_section_parked_only_in_another_tree_is_not_ingested_here(
    panel: Panel,
) -> None:
    section = int(
        panel.conn.execute(
            "SELECT id FROM sections WHERE path = 'f7.txt'"
        ).fetchone()[0]
    )
    panel.conn.execute(
        "DELETE FROM node_members WHERE section_id = ?", (section,)
    )
    incubator.park(panel.conn, "elsewhere", section, 1)
    panel.conn.commit()
    leave_every_source_out(panel)

    html = page(panel, "files", path="f7.txt")

    assert "Not ingested" in html
    assert ">parked</span>" not in html


def test_a_section_filed_only_in_another_tree_is_not_ingested_here(
    panel: Panel,
) -> None:
    file_in_other_tree(panel, "f7.txt")
    panel.conn.execute("DELETE FROM pending WHERE tree = ?", (TREE,))
    panel.conn.commit()
    leave_every_source_out(panel)

    html = page(panel, "files", path="f7.txt")

    assert "Not ingested" in html
    assert "#section-" not in html
