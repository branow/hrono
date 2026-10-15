"""Render the collapsed tree to markdown files."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.export.collapse import StoredTree, collapse
from hrono.export.render import render
from hrono.export.store import load
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.split.constants import section_budget
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


def _files(db: Database, notes=None, hops: int = 3) -> dict[str, str]:
    with db.connect() as conn:
        stored = load(conn, TREE)
        assert stored is not None
        return render(conn, collapse(stored, hops), notes=notes)


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


def test_leaf_lists_its_sources_and_carries_caution(
    db: tuple[Database, dict[str, int]],
) -> None:
    database, ids = db
    files = _files(database)
    alpha = files[f"alpha-topic-{ids['n0']}/brief.md"]
    assert "Caution: none." in alpha  # the stored Caution rendered as-is
    sources = alpha.split("## Sources\n", 1)[1].split()
    assert " ".join(sources) == "repo @ v1: - `a.py`"


def test_no_section_copy_is_written(
    db: tuple[Database, dict[str, int]],
) -> None:
    # the export is briefs only: the reader has the repository, so a leaf
    # points at its files and copies none of them
    database, ids = db
    files = _files(database)
    assert all(p == "root.md" or p.endswith("/brief.md") for p in files)
    alpha = files[f"alpha-topic-{ids['n0']}/brief.md"]
    assert "- `a.py`" in alpha
    assert "alpha line one" not in alpha


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


def test_a_parentless_node_keeps_its_own_brief_path(
    db: tuple[Database, dict[str, int]],
) -> None:
    # the renderer must stay total — the loader refuses a forest, but if
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
    # skip is exercised by test_a_long_first_line_is_trimmed_to_a_usable_title
    # — a single node IS the root, so no directory name is derived from it
    # here.)
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


def test_an_upper_node_does_not_repeat_its_children_as_references(
    db: tuple[Database, dict[str, int]],
) -> None:
    # an upper brief's member list is child NODE IDS. ## Children already
    # renders them as titled links, and an id is only meaningful while that node
    # exists — a brief written before a rebuild would have root.md cite topics
    # that have since been retired.
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


def test_a_leaf_lists_each_source_file_once(tmp_path: object) -> None:
    # a long file is split into several sections; the reader opens it once
    database, ids = _grove(
        tmp_path,
        [[["big/x.py", "big/x.py", "big/y.py"]]],
        {"root": "# Root\n\nAll.", "m0": "# Mid\n\nA.", "l0.0": "# L\n\nB."},
    )
    try:
        files = _files(database)
    finally:
        database.close()
    leaf = next(c for c in files.values() if "## Sources" in c)
    sources = [
        line for line in leaf.split("## Sources\n", 1)[1].splitlines() if line
    ]
    assert sources == ["repo @ v1:", "- `big/x.py`", "- `big/y.py`"]


def test_a_childless_upper_node_still_skips_its_references(
    db: tuple[Database, dict[str, int]],
) -> None:
    # a transient state: a rebuild re-minted the leaf ids and cascaded the
    # root's edges away, so the root has no children to render. A guard on the
    # CHILD COUNT would call that a leaf and print its stored node ids, which
    # may name retired nodes. The guard is on the LEVEL.
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
    # an agent picks a branch from the index page without opening it
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
    # the root is read first and carried on every later turn; its facts
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


def test_only_the_root_is_trimmed_to_its_opening(
    tmp_path: object,
) -> None:
    # the root, a middle index page and a leaf. The root is read on every
    # turn and keeps its opening; a middle page keeps its flows, and a leaf
    # keeps every fact.
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
        leaves_md = [c for c in pages.values() if "## Sources" in c]
        assert indexes
        assert leaves_md
        assert all("TAU is 7" in c for c in indexes)
        assert all("TAU is 7" in c for c in leaves_md)
        assert "TAU is 7" not in files["root.md"]
    finally:
        database.close()


def _grove(
    tmp_path: object,
    shape: list[list[list[str]]],
    texts: dict[str, str],
    apex: bool = False,
) -> tuple[Database, dict[str, int]]:
    """A tree from nested names: root -> middles -> leaves -> sections.

    ``shape`` is a list of middle nodes, each a list of leaves, each a list of
    section paths. ``texts`` maps "root", "m<i>" and "l<i>.<j>" to a brief.
    ``apex`` puts one more node above "root", so that "root" is an ordinary
    index page below the export's root.md (which names no sources);
    export it with ``hops=4``. Its page is ``_page(ids["root"])``.
    """
    database = Database.at(tmp_path / "grove.db")
    ids: dict[str, int] = {}
    with database.connect() as conn, conn:
        rows = []
        vectors = []
        leaf_of: list[tuple[int, int]] = []
        label = 0
        for m, leaves in enumerate(shape):
            for paths in leaves:
                for path in paths:
                    sid = add_section(conn, path, b"body one\nbody two\n")
                    ids[path] = sid
                    rows.append((label, sid, False, None))
                    vectors.append((sid, [0.01 * len(rows)]))
                leaf_of.append((m, label))
                label += 1
        cluster_store.replace_tree(conn, TREE, 0, rows, vectors)
        leaf_ids = {
            int(r["label"]): int(r["id"])
            for r in conn.execute(
                "SELECT id, label FROM nodes WHERE level = 0"
            ).fetchall()
        }
        cluster_store.replace_level(
            conn,
            TREE,
            1,
            [(m, leaf_ids[lab], False, None) for m, lab in leaf_of],
        )
        middles = {
            int(r["label"]): int(r["id"])
            for r in conn.execute(
                "SELECT id, label FROM nodes WHERE level = 1"
            ).fetchall()
        }
        cluster_store.replace_level(
            conn,
            TREE,
            2,
            [(0, middles[m], False, None) for m in sorted(middles)],
        )
        ids["root"] = int(
            conn.execute("SELECT id FROM nodes WHERE level = 2").fetchone()[
                "id"
            ]
        )
        if apex:
            cluster_store.replace_level(
                conn, TREE, 3, [(0, ids["root"], False, None)]
            )
            ids["apex"] = int(
                conn.execute("SELECT id FROM nodes WHERE level = 3").fetchone()[
                    "id"
                ]
            )
            brief(conn, ids["apex"], "# Apex\n\nEverything.")
        flat = iter(leaf_of)
        for m, leaves in enumerate(shape):
            ids[f"m{m}"] = middles[m]
            for j, _ in enumerate(leaves):
                _, lab = next(flat)
                ids[f"l{m}.{j}"] = leaf_ids[lab]
        for key, text in texts.items():
            brief(conn, ids[key], text)
    return database, ids


def _page(node_id: int) -> str:
    """Where the export puts the page of the node titled "Root" (``_grove``)."""
    return f"root-{node_id}/brief.md"


def test_index_pages_name_no_sources(tmp_path: object) -> None:
    # a source file is named once, on its leaf, not sampled again above it
    database, ids = _grove(
        tmp_path,
        [[["src/deep/a/x1.py", "src/deep/a/x2.py"]], [["b/y1.py"]]],
        {
            "root": "# Root\n\nAll.",
            "m0": "# Mid A\n\nAlpha things.",
            "m1": "# Mid B\n\nBeta things.",
            "l0.0": "# Leaf A\n\nLeaf alpha.",
            "l1.0": "# Leaf B\n\nLeaf beta.",
        },
        apex=True,
    )
    try:
        files = _files(database, hops=4)
    finally:
        database.close()
    index = [page for page in files.values() if "## Children" in page]
    leaves = [page for page in files.values() if "## Sources" in page]
    assert index and leaves
    assert not any("Sources" in page or "`" in page for page in index)
    named = "".join(leaves)
    for path in ("src/deep/a/x1.py", "src/deep/a/x2.py", "b/y1.py"):
        assert named.count(f"`{path}`") == 1


def test_a_page_links_its_children_from_its_own_directory(
    tmp_path: object,
) -> None:
    # a middle page sits one directory down, so its links drop that prefix
    database, ids = _grove(
        tmp_path,
        [[["a/x1.py"], ["b/y1.py"]]],
        {
            "root": "# Root\n\nAll.",
            "m0": "# Mid\n\nThings.",
            "l0.0": "# Leaf A\n\nOne.",
            "l0.1": "# Leaf B\n\nTwo.",
        },
    )
    try:
        files = _files(database)
    finally:
        database.close()
    mid_dir = f"mid-{ids['m0']}"
    leaf_a = f"leaf-a-{ids['l0.0']}"
    assert f"[Leaf A]({leaf_a}/brief.md)" in files[f"{mid_dir}/brief.md"]
    assert f"{mid_dir}/{leaf_a}/brief.md" in files


def _siblings_saying(
    tmp_path: object, first: str, second: str
) -> tuple[list[str], Database]:
    database, ids = _grove(
        tmp_path,
        [[["a.py"]], [["b.py"]]],
        {
            "root": "# Root\n\nAll.",
            "m0": f"# Hrono is a knowledge base\n\n{first}",
            "m1": f"# Hrono is a knowledge base\n\n{second}",
            "l0.0": "# One\n\nx.",
            "l1.0": "# Two\n\ny.",
        },
    )
    files = _files(database)
    stems = sorted(
        path.split("/")[0].rsplit("-", 1)[0]
        for path in files
        if path.endswith("/brief.md") and path.count("/") == 1
    )
    return stems, database


def test_siblings_with_the_same_title_are_named_by_what_each_says(
    tmp_path: object,
) -> None:
    stems, database = _siblings_saying(
        tmp_path, "It stores sources.", "It serves recall."
    )
    database.close()
    assert stems == ["it-serves-recall", "it-stores-sources"]


@pytest.mark.parametrize(
    "first, second",
    [
        ("It stores sources.", "It stores sources."),
        ("", "It serves recall."),
    ],
    ids=["same-summary", "one-silent"],
)
def test_siblings_with_nothing_to_tell_them_apart_keep_the_title(
    tmp_path: object, first: str, second: str
) -> None:
    stems, database = _siblings_saying(tmp_path, first, second)
    database.close()
    assert stems == ["hrono-is-a-knowledge-base"] * 2


def test_a_summary_stem_is_not_taken_when_a_sibling_already_has_it(
    tmp_path: object,
) -> None:
    # A and B read alike; A's summary slugs to C's title, so renaming them
    # would put A and C on one stem
    database, _ = _grove(
        tmp_path,
        [[["a.py"]], [["b.py"]], [["c.py"]]],
        {
            "root": "# Root\n\nAll.",
            "m0": "# Hrono is a knowledge base\n\nIt serves recall.",
            "m1": "# Hrono is a knowledge base\n\nIt stores sources.",
            "m2": "# It serves recall\n\nElsewhere.",
            "l0.0": "# One\n\nx.",
            "l1.0": "# Two\n\ny.",
            "l2.0": "# Three\n\nz.",
        },
    )
    try:
        files = _files(database)
    finally:
        database.close()
    stems = sorted(
        path.split("/")[0].rsplit("-", 1)[0]
        for path in files
        if path.endswith("/brief.md") and path.count("/") == 1
    )
    assert len(set(stems)) == 2  # A and B keep the title; C is alone
    assert stems.count("it-serves-recall") == 1


def test_an_index_page_at_full_width_stays_within_one_section(
    tmp_path: object,
) -> None:
    # the Sections line is not allowed to push a WIDTH-entry page past
    # the budget collapse.py sizes it on
    middles = 40
    database, ids = _grove(
        tmp_path,
        [
            [[f"src/hrono/package{m}/module_{k}.py" for k in range(6)]]
            for m in range(middles)
        ],
        {
            "root": "# Root\n\nAll.",
            **{
                f"m{m}": f"# Component number {m} owns its own part of the"
                f" system\n\nIt reads and writes the records of part {m}"
                " and hands them to the next stage when it is done.\n"
                for m in range(middles)
            },
            **{f"l{m}.0": f"# Leaf {m}\n\nBody." for m in range(middles)},
        },
        apex=True,
    )
    try:
        files = _files(database, hops=4)
    finally:
        database.close()
    root = files[_page(ids["root"])]
    assert root.count("](") >= middles
    assert len(root.encode()) <= section_budget(Path("index.md"))


def test_an_index_page_below_the_root_says_where_its_children_are(
    tmp_path: object,
) -> None:
    # agents read a child's link as a path from the export's root; the page
    # names its own folder once so they can build the real one
    database, ids = _grove(
        tmp_path,
        [[["a/x.py"]], [["b/y.py"]]],
        {
            "root": "# Root\n\nAll.",
            "m0": "# Mid A\n\nAlpha things.",
            "m1": "# Mid B\n\nBeta things.",
            "l0.0": "# Leaf A\n\nLeaf alpha.",
            "l1.0": "# Leaf B\n\nLeaf beta.",
        },
        apex=True,
    )
    try:
        files = _files(database, hops=4)
    finally:
        database.close()
    page = files[_page(ids["root"])]
    assert f"These are in the folder root-{ids['root']}/." in page
    assert "These are in the folder" not in files["root.md"]


def test_a_middle_page_drops_the_part_list_its_children_repeat() -> None:
    from hrono.export.render import _index

    text = (
        "# Area\n\nIntro.\n\n## Flows\n1. A sends to B.\n\n"
        "## Other parts\n- C does c.\n\n## Hazards\n- B drops it."
    )
    kept = _index(text)
    assert "1. A sends to B." in kept and "B drops it." in kept
    assert "C does c." not in kept
