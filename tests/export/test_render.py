"""T30: render the collapsed tree to markdown files."""

from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database, open_database
from hrono.export.collapse import collapse
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
    database = Database(open_database(tmp_path / "hrono.db"))  # type: ignore[operator]
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
    database, _ = db
    files = _files(database)
    assert "root.md" in files
    root = files["root.md"]
    assert "# Root overview" in root  # stored brief as-is
    assert "## Children" in root
    assert "[Alpha topic](alpha-topic/brief.md)" in root  # mechanical link
    assert "[Beta topic](beta-topic/brief.md)" in root


def test_leaf_lists_sections_and_carries_caution(
    db: tuple[Database, dict[str, int]],
) -> None:
    files = _files(db[0])
    alpha = files["alpha-topic/brief.md"]
    assert "Caution: none." in alpha  # the stored Caution rendered as-is
    assert "## Sections" in alpha


def test_section_reassembles_byte_identically(
    db: tuple[Database, dict[str, int]],
) -> None:
    database, ids = db
    files = _files(database)
    section_files = [
        p
        for p in files
        if p.startswith("alpha-topic/") and p != "alpha-topic/brief.md"
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
    without = _files(database)
    assert "## Notes" not in without["alpha-topic/brief.md"]
    with_notes = _files(database, notes={ids["n0"]: "a human note"})
    assert "## Notes" in with_notes["alpha-topic/brief.md"]
    assert "a human note" in with_notes["alpha-topic/brief.md"]


def test_output_is_deterministic(db: tuple[Database, dict[str, int]]) -> None:
    assert _files(db[0]) == _files(db[0])
