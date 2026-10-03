"""T30: render the collapsed tree to markdown files."""

import json
from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.export.collapse import StoredTree, collapse
from hrono.export.render import render
from hrono.export.store import load
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.summarize import briefs

TREE = "default"


def add_section(conn: object, path: str, body: bytes) -> int:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    section_id = istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=0,
    )
    half = len(body) // 2
    for ordinal, (start, end) in enumerate([(0, half), (half, len(body))]):
        chunk = body[start:end]
        istore.upsert_content(conn, content_hash(chunk), chunk)  # type: ignore[arg-type]
        istore.insert_passage(
            conn,  # type: ignore[arg-type]
            section_id=section_id,
            source="repo",
            address=Address("git", "ex/repo", path, "v1"),
            start=start,
            end=end,
            content_hash=content_hash(chunk),
            sp_paths=(),
            ordinal=ordinal,
        )
    return section_id


def brief(conn: object, node_id: int, text: str) -> None:
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node_id,
        text,
        model_name="m",
        prompt_name="brief",
        prompt_hash="h",
        member_signature="sig",
        input_tokens=1,
        output_tokens=1,
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[tuple[Database, dict[str, int]]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        s0 = add_section(conn, "a.py", b"alpha line one\nalpha line two\n")
        s1 = add_section(conn, "b.py", b"beta line one\nbeta line two\n")
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s0, False, None), (1, s1, False, None)],
            [(s0, [0.1]), (s1, [0.2])],
        )
        level0 = {
            int(r["label"]): int(r["id"])
            for r in conn.execute(
                "SELECT id, label FROM nodes WHERE level = 0"
            ).fetchall()
        }
        cluster_store.replace_level(
            conn,
            TREE,
            1,
            [(0, level0[0], False, None), (0, level0[1], False, None)],
        )
        root = int(
            conn.execute("SELECT id FROM nodes WHERE level = 1").fetchone()[
                "id"
            ]
        )
        brief(
            conn, level0[0], "# Alpha topic\n\nAlpha stuff.\n\nCaution: none."
        )
        brief(conn, level0[1], "# Beta topic\n\nBeta stuff.")
        brief(conn, root, "# Root overview\n\nEverything.")
        ids = {
            "s0": s0,
            "s1": s1,
            "root": root,
            **{f"n{k}": v for k, v in level0.items()},
        }
    yield database, ids
    database.close()


def _files(db: Database, notes=None) -> dict[str, str]:
    with db.connect() as conn:
        stored = load(conn, TREE)
        assert stored is not None
        return render(conn, collapse(stored, 3), notes=notes)


def test_root_renders_brief_and_mechanical_child_listing(
    db: tuple[Database, dict[str, int]],
) -> None:
    database, ids = db
    files = _files(database)
    assert "root.md" in files
    root = files["root.md"]
    assert "# Root overview" in root  # stored brief as-is
    assert "## Children" in root
    # mechanical links; node id suffixed so siblings never collide
    assert f"[Alpha topic](alpha-topic-{ids['n0']}/brief.md)" in root
    assert f"[Beta topic](beta-topic-{ids['n1']}/brief.md)" in root


def test_leaf_lists_sections_and_carries_caution(
    db: tuple[Database, dict[str, int]],
) -> None:
    database, ids = db
    files = _files(database)
    alpha = files[f"alpha-topic-{ids['n0']}/brief.md"]
    assert "Caution: none." in alpha  # the stored Caution rendered as-is
    assert "## Sections" in alpha


def test_section_reassembles_byte_identically(
    db: tuple[Database, dict[str, int]],
) -> None:
    database, ids = db
    files = _files(database)
    alpha_dir = f"alpha-topic-{ids['n0']}"
    section_files = [
        p
        for p in files
        if p.startswith(f"{alpha_dir}/") and p != f"{alpha_dir}/brief.md"
    ]
    assert section_files
    content = files[section_files[0]]
    assert "alpha line one\nalpha line two\n" in content  # reassembled body
    # the reassembled bytes equal the stored section bytes
    with database.connect() as conn:
        stored_body = istore.get_content(
            conn,
            conn.execute(
                "SELECT content_hash FROM sections WHERE id = ?", (ids["s0"],)
            ).fetchone()["content_hash"],
        )
        passages = b"".join(
            istore.get_content(conn, r["content_hash"])
            for r in conn.execute(
                "SELECT content_hash FROM passages WHERE section_id = ? "
                "ORDER BY ordinal",
                (ids["s0"],),
            ).fetchall()
        )
    assert passages == stored_body


def test_notes_render_only_when_present(
    db: tuple[Database, dict[str, int]],
) -> None:
    database, ids = db
    alpha = f"alpha-topic-{ids['n0']}/brief.md"
    without = _files(database)
    assert "## Notes" not in without[alpha]
    with_notes = _files(database, notes={ids["n0"]: "a human note"})
    assert "## Notes" in with_notes[alpha]
    assert "a human note" in with_notes[alpha]


def test_output_is_deterministic(db: tuple[Database, dict[str, int]]) -> None:
    assert _files(db[0]) == _files(db[0])


def test_same_heading_siblings_do_not_collide(tmp_path: object) -> None:
    # two children whose briefs both start "# Overview" must NOT overwrite each
    # other — every subtree survives and each child link is unique.
    database = Database.at(tmp_path / "c.db")
    with database.connect() as conn, conn:
        s0 = add_section(conn, "a.py", b"aaaa\n")
        s1 = add_section(conn, "b.py", b"bbbb\n")
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s0, False, None), (1, s1, False, None)],
            [(s0, [0.1]), (s1, [0.2])],
        )
        level0 = sorted(
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE level = 0"
            ).fetchall()
        )
        cluster_store.replace_level(
            conn,
            TREE,
            1,
            [(0, level0[0], False, None), (0, level0[1], False, None)],
        )
        root = int(
            conn.execute("SELECT id FROM nodes WHERE level = 1").fetchone()[
                "id"
            ]
        )
        brief(conn, level0[0], "# Overview\n\nFirst.")
        brief(conn, level0[1], "# Overview\n\nSecond.")  # same heading
        brief(conn, root, "# Root\n\nAll.")
    try:
        files = _files(database)
        briefs_written = [p for p in files if p.endswith("/brief.md")]
        assert len(briefs_written) == 2  # both subtrees survived, no overwrite
        assert len(set(briefs_written)) == 2  # distinct directories
        root_md = files["root.md"]
        links = [
            line for line in root_md.splitlines() if line.startswith("- [")
        ]
        assert len(links) == len(set(links)) == 2  # two unique child links
    finally:
        database.close()


def test_no_rendered_path_is_absolute(
    db: tuple[Database, dict[str, int]],
) -> None:
    files = _files(db[0])
    assert files
    assert not [p for p in files if p.startswith("/")]


def test_the_roots_own_sections_render_beside_root_md(
    tmp_path: object,
) -> None:
    # F19: a tree whose ROOT carries sections wrote "/<name>.md" for each of
    # them — pathlib rerooted the join and the CLI refused the whole export.
    database = Database.at(tmp_path / "flat.db")
    with database.connect() as conn, conn:
        s0 = add_section(conn, "a.py", b"alpha\n")
        s1 = add_section(conn, "b.py", b"beta\n")
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s0, False, None), (0, s1, False, None)],
            [(s0, [0.1]), (s1, [0.2])],
        )
        root = int(
            conn.execute("SELECT id FROM nodes WHERE level = 0").fetchone()[
                "id"
            ]
        )
        brief(conn, root, "# Only topic\n\nAll of it.")
    try:
        files = _files(database)
        assert not [p for p in files if p.startswith("/")]
        assert "root.md" in files
        sections = sorted(p for p in files if p != "root.md")
        assert sections == [f"a-py-{s0}.md", f"b-py-{s1}.md"]
    finally:
        database.close()


def test_a_parentless_node_keeps_its_own_brief_path(
    db: tuple[Database, dict[str, int]],
) -> None:
    # F20: the renderer must stay total — the loader refuses a forest, but if
    # one ever reaches render, two briefs may not collide onto one key.
    database, ids = db
    with database.connect() as conn:
        stored = load(conn, TREE)
        assert stored is not None
        forest = StoredTree(
            root=stored.root,
            node_level=stored.node_level,
            children={},  # every node parentless: nothing links them
            sections=stored.sections,
        )
        files = render(conn, collapse(forest, 3))
    assert not [p for p in files if p.startswith("/")]
    briefs_written = [p for p in files if p.endswith("brief.md")]
    assert len(briefs_written) == len(set(briefs_written)) == 2
    assert f"alpha-topic-{ids['n0']}/brief.md" in files
    assert f"beta-topic-{ids['n1']}/brief.md" in files


def test_a_brief_is_rendered_verbatim_including_its_own_headings(
    tmp_path: object,
) -> None:
    # the renderer DERIVES a title from the brief but never rewrites the brief:
    # a "## Summary" heading survives into the file as written. (The boilerplate
    # skip this test used to claim is exercised by
    # test_a_long_first_line_is_trimmed_to_a_usable_title — a single node IS the
    # root, so no directory name is derived from it here. #102.)
    database = Database.at(tmp_path / "b.db")
    with database.connect() as conn, conn:
        s0 = add_section(conn, "a.py", b"alpha\n")
        cluster_store.replace_tree(
            conn, TREE, 0, [(0, s0, False, None)], [(s0, [0.1])]
        )
        root = int(
            conn.execute("SELECT id FROM nodes WHERE level = 0").fetchone()[
                "id"
            ]
        )
        brief(
            conn,
            root,
            "## Summary\n\nThis is the signing library, key rotation and all."
            " It also covers timestamps.",
        )
    try:
        files = _files(database)
        assert "root.md" in files
        assert files["root.md"].startswith("## Summary")
        assert "key rotation and all." in files["root.md"]
    finally:
        database.close()


def test_a_long_first_line_is_trimmed_to_a_usable_title(
    tmp_path: object,
) -> None:
    database = Database.at(tmp_path / "t.db")
    with database.connect() as conn, conn:
        s0 = add_section(conn, "a.py", b"aaaa\n")
        s1 = add_section(conn, "b.py", b"bbbb\n")
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s0, False, None), (1, s1, False, None)],
            [(s0, [0.1]), (s1, [0.2])],
        )
        level0 = sorted(
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE level = 0"
            ).fetchall()
        )
        cluster_store.replace_level(
            conn,
            TREE,
            1,
            [(0, level0[0], False, None), (0, level0[1], False, None)],
        )
        root = int(
            conn.execute("SELECT id FROM nodes WHERE level = 1").fetchone()[
                "id"
            ]
        )
        brief(
            conn,
            level0[0],
            "## Summary\n\nThis is a **specification document** for the "
            "library, a signing and serialization toolkit with key rotation, "
            "timestamp validation and URL-safe encoding. More follows.",
        )
        brief(conn, level0[1], "# Beta topic\n\nBeta stuff.")
        brief(conn, root, "# Root\n\nAll of it.")
    try:
        files = _files(database)
        directories = {p.rsplit("/", 1)[0] for p in files if "/" in p}
        assert not [d for d in directories if d.startswith("summary-")]
        long_one = next(
            d for d in directories if d.startswith("specification-document-")
        )
        assert len(long_one.rsplit("-", 1)[0]) <= 60  # slug stays a directory
        links = [
            line
            for line in files["root.md"].splitlines()
            if line.startswith("- [")
        ]
        titles = [line.split("](", 1)[0] for line in links]
        assert all(len(title) < 90 for title in titles)  # not a paragraph
        # the sentence that became the title is not repeated as its summary
        assert any(line.endswith(" — More follows.") for line in links)
    finally:
        database.close()


def test_the_member_references_are_re_attached_from_metadata(
    db: tuple[Database, dict[str, int]],
) -> None:
    # #102 moved the member URIs out of briefs.text so #071's passages carry
    # prose only. The map must still show every reference: the renderer puts
    # them back from the stored metadata.
    database, ids = db
    uris = ("git://ex/repo/a.py@v1", "git://ex/repo/b.py@v1")
    with database.connect() as conn, conn:
        conn.execute(
            "UPDATE briefs SET members = ? WHERE node_id = ?",
            (json.dumps(list(uris)), ids["n0"]),
        )
    files = _files(database)
    rendered = files[f"alpha-topic-{ids['n0']}/brief.md"]
    assert "## References" in rendered
    for uri in uris:
        assert uri in rendered
    # ... and a node with no recorded members gets no empty section
    assert "## References" not in files[f"beta-topic-{ids['n1']}/brief.md"]


def test_an_upper_node_does_not_repeat_its_children_as_references(
    db: tuple[Database, dict[str, int]],
) -> None:
    # #102: an upper brief's member list is child NODE IDS. ## Children already
    # renders them as titled links, and an id is only meaningful while that node
    # exists — a brief written before a rebuild would have root.md cite topics
    # that have since been retired (three of them, on the live corpus).
    database, ids = db
    with database.connect() as conn, conn:
        conn.execute(
            "UPDATE briefs SET members = ? WHERE node_id = ?",
            (json.dumps(["node 3", "node 5", "node 6"]), ids["root"]),
        )
    files = _files(database)
    assert "## Children" in files["root.md"]  # the real, live listing
    assert "## References" not in files["root.md"]
    for retired in ("node 3", "node 5", "node 6"):
        assert retired not in files["root.md"]


def test_a_leaf_still_shows_its_source_references(
    db: tuple[Database, dict[str, int]],
) -> None:
    # the other side of the skip: a LEAF's member list is its members' source
    # URIs — provenance the export shows nowhere else, and never a node id, so
    # a retired id cannot reach the map through this path at all.
    database, ids = db
    uris = ("git://ex/repo/a.py@v1", "git://ex/repo/b.py@v1")
    with database.connect() as conn, conn:
        conn.execute(
            "UPDATE briefs SET members = ? WHERE node_id = ?",
            (json.dumps(list(uris)), ids["n0"]),
        )
    rendered = _files(database)[f"alpha-topic-{ids['n0']}/brief.md"]
    assert "## References" in rendered
    for uri in uris:
        assert uri in rendered


def test_a_childless_upper_node_still_skips_its_references(
    db: tuple[Database, dict[str, int]],
) -> None:
    # #114's transient state: a rebuild re-minted the leaf ids and cascaded the
    # root's edges away, so the root has no children to render. A guard on the
    # CHILD COUNT calls that a leaf and prints its stored node ids — three of
    # which were retired on the live corpus. The guard is on the LEVEL.
    database, ids = db
    with database.connect() as conn, conn:
        conn.execute("DELETE FROM node_children")
        conn.execute(
            "UPDATE briefs SET members = ? WHERE node_id = ?",
            (json.dumps(["node 3", "node 5", "node 6"]), ids["root"]),
        )
    files = _files(database)
    assert "## References" not in files["root.md"]
    assert not [path for path, body in files.items() if "- node " in body]


def test_an_index_entry_says_what_the_child_holds(
    db: tuple[Database, dict[str, int]],
) -> None:
    # #204: an agent picks a branch from the index page without opening it
    database, ids = db

    root = _files(database)["root.md"]

    assert (
        f"- [Alpha topic](alpha-topic-{ids['n0']}/brief.md) — Alpha stuff."
        in root.splitlines()
    )
    assert (
        f"- [Beta topic](beta-topic-{ids['n1']}/brief.md) — Beta stuff."
        in root.splitlines()
    )


def test_a_briefs_fact_links_the_section_page_that_states_it(
    tmp_path: object,
) -> None:
    # E018: the root cites a fact from a section two levels down, and the leaf
    # cites it from beside the page, so each link is relative to its own file.
    database = Database.at(tmp_path / "e.db")
    with database.connect() as conn, conn:
        s0 = add_section(conn, "a.py", b"TAU is 0.70 here\n")
        s1 = add_section(conn, "b.py", b"nothing\n")
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s0, False, None), (1, s1, False, None)],
            [(s0, [0.1]), (s1, [0.2])],
        )
        level0 = sorted(
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE level = 0"
            ).fetchall()
        )
        cluster_store.replace_level(
            conn,
            TREE,
            1,
            [(0, level0[0], False, None), (0, level0[1], False, None)],
        )
        root = int(
            conn.execute("SELECT id FROM nodes WHERE level = 1").fetchone()[
                "id"
            ]
        )
        brief(conn, level0[0], "# Alpha\n\nTAU is 0.70.")
        brief(conn, level0[1], "# Beta\n\nBeta stuff.")
        brief(conn, root, "# Root\n\nTAU is 0.70 everywhere.")
    try:
        files = _files(database)
        section = next(p for p in files if p.endswith(f"-{s0}.md"))
        directory = section.rsplit("/", 1)[0]
        assert f"[§]({section})" in files["root.md"]
        assert (
            f"[§]({section.rsplit('/', 1)[1]})"
            in files[f"{directory}/brief.md"]
        )
    finally:
        database.close()


def test_an_index_summary_skips_the_sentence_that_became_the_name(
    db: tuple[Database, dict[str, int]],
) -> None:
    database, ids = db
    with database.connect() as conn, conn:
        brief(
            conn,
            ids["n0"],
            "These condensations describe the signing library. It rotates"
            " keys.",
        )
    root = _files(database)["root.md"]
    assert "[Signing library.](signing-library-" in root
    assert "describe" not in root
    assert "— It rotates keys." in root


@pytest.mark.parametrize(
    ("brief_text", "kept", "dropped"),
    [
        ("# Root\n\nIntro.\n\n## Facts\n- TAU is 7.", "Intro.", "TAU is 7"),
        ("## Summary\nIntro.\n\n## Facts\n- TAU is 7.", "Intro.", "TAU is 7"),
        ("Just prose, no headings.", "Just prose", "\x00"),
        (
            "# Title\n## Summary\nIntro.\n## Facts\n- TAU is 7.",
            "Intro.",
            "TAU is 7",
        ),
    ],
    ids=["after-prose", "heading-first", "no-headings", "two-headings-first"],
)
def test_the_root_keeps_its_opening_and_leaves_the_facts_to_its_children(
    db: tuple[Database, dict[str, int]],
    brief_text: str,
    kept: str,
    dropped: str,
) -> None:
    # E018: the root is read first and carried on every later turn; its facts
    # are on the children's pages.
    database, ids = db
    with database.connect() as conn, conn:
        brief(conn, ids["root"], brief_text)
    root = _files(database)["root.md"]
    assert kept in root
    assert dropped not in root
    assert "## Children" in root


def test_a_brief_opening_with_a_heading_is_named_by_its_subject(
    db: tuple[Database, dict[str, int]],
) -> None:
    database, ids = db
    with database.connect() as conn, conn:
        brief(
            conn,
            ids["n0"],
            "# These condensations describe the signing library.\n\nKeys.",
        )
    root = _files(database)["root.md"]
    assert f"[Signing library.](signing-library-{ids['n0']}/brief.md)" in root
    assert "condensations" not in root


def test_only_a_page_with_children_is_trimmed_to_its_opening(
    tmp_path: object,
) -> None:
    # E018: the root, a middle index page and a leaf. The middle page has
    # children and keeps its opening; the leaf has none and keeps every fact.
    database = Database.at(tmp_path / "m.db")
    text = "# Topic\n\nIntro.\n\n## Facts\n- TAU is 7."
    with database.connect() as conn, conn:
        s = [
            add_section(conn, f"{n}.py", b"body one\nbody two\n") for n in "abc"
        ]
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(n, sid, False, None) for n, sid in enumerate(s)],
            [(sid, [0.1 * n]) for n, sid in enumerate(s)],
        )
        leaves = sorted(
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE level = 0"
            ).fetchall()
        )
        cluster_store.replace_level(
            conn,
            TREE,
            1,
            [
                (0, leaves[0], False, None),
                (0, leaves[1], False, None),
                (1, leaves[2], False, None),
            ],
        )
        middle = sorted(
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE level = 1"
            ).fetchall()
        )
        cluster_store.replace_level(
            conn,
            TREE,
            2,
            [(0, middle[0], False, None), (0, middle[1], False, None)],
        )
        for node in (*leaves, *middle):
            brief(conn, node, text)
        root = int(
            conn.execute("SELECT id FROM nodes WHERE level = 2").fetchone()[
                "id"
            ]
        )
        brief(conn, root, text)
    try:
        with database.connect() as conn:
            stored = load(conn, TREE)
            assert stored is not None
            files = render(conn, collapse(stored, 4))
        pages = {p: c for p, c in files.items() if p.endswith("brief.md")}
        indexes = [c for c in pages.values() if "## Children" in c]
        leaves_md = [c for c in pages.values() if "## Sections" in c]
        assert indexes
        assert leaves_md
        assert all("TAU is 7" not in c for c in indexes)
        assert all("TAU is 7" in c for c in leaves_md)
    finally:
        database.close()
