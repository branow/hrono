"""T34 op: `update` applies a change batch incrementally over a built tree."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster.build import ClusterResult
from hrono.cluster.incubator import MAX_AGE, pending
from hrono.cluster.recipe import MIN_POINTS
from hrono.db.database import Database
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.tree.maintain import maintain
from hrono.tree.update import update
from tests.cluster.invariant import assert_pool_invariant
from tests.context import job_context

DIMS = 8


class FakeCompletion:
    def complete(self, request: CompletionRequest) -> CompletionResult:
        return CompletionResult("a plain summary.", Usage(10, 4))


def fake_encoder(model_id: str):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (DIMS - 1) for _ in texts]

    return encode


def fake_build(vectors: object, *, init: object = None) -> ClusterResult:
    n = len(vectors)  # type: ignore[arg-type]
    return ClusterResult(
        labels=tuple(i // 3 for i in range(n)),
        attached=tuple(False for _ in range(n)),
        assignment_similarity=tuple(None for _ in range(n)),
        coords=tuple((0.0,) for _ in range(n)),
    )


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(path), *args], check=True)


def make_repo(path: Path, files: int = 9) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    for i in range(files):
        (path / f"f{i}.txt").write_text(f"module {i} does thing number {i}\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "first")
    return path.as_uri()


def edit(path: Path, name: str, text: str) -> None:
    (path / name).write_text(text)
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", f"edit {name}")


def register(conn: object, url: str) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "sources",
        "repo",
        json.dumps({"name": "repo", "type": "git", "url": url, "auth": {}}),
        None,
        "t",
    )
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "models",
        "emb",
        json.dumps(
            {
                "name": "emb",
                "kind": "embedding",
                "connection": None,
                "model": "fake",
                "params": {"dims": DIMS, "batch_size": 8},
            }
        ),
        None,
        "t",
    )
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "models",
        "sonnet",
        json.dumps(
            {
                "name": "sonnet",
                "kind": "text",
                "connection": "c",
                "model": "claude",
                "params": {},
            }
        ),
        None,
        "t",
    )
    for role in ("condense", "brief", "brief-upper"):
        registry_store.insert(
            conn,  # type: ignore[arg-type]
            "prompts",
            role,
            json.dumps({"name": role, "role": role, "template": "X {content}"}),
            None,
            "t",
        )


def _job(op: str) -> Job:
    return Job(
        id=op,
        parent_id=None,
        tree="default",
        op=op,
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Database, Path]]:
    monkeypatch.chdir(tmp_path)
    origin = tmp_path / "src-repo"
    url = make_repo(origin)
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register(conn, url)
    maintain(
        _job("maintain"),
        job_context(database, tmp_path),
        encoder_for=fake_encoder,
        client=FakeCompletion(),
        build=fake_build,
    )
    yield database, origin
    database.close()


def _section_ids(db: Database, path: str) -> list[int]:
    with db.connect() as conn:
        return sorted(
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM sections WHERE path = ?", (path,)
            ).fetchall()
        )


def _hashes(db: Database, path: str) -> set[str]:
    with db.connect() as conn:
        return {
            r["content_hash"]
            for r in conn.execute(
                "SELECT content_hash FROM sections WHERE path = ?", (path,)
            ).fetchall()
        }


def _node_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return sorted(
            int(r["id"]) for r in conn.execute("SELECT id FROM nodes")
        )


def test_update_is_registered() -> None:
    assert "update" in OPS


def test_update_swaps_changed_file_and_leaves_untouched_alone(
    built: tuple[Database, Path],
    tmp_path: Path,
) -> None:
    db, origin = built
    before_f1 = _section_ids(db, "f1.txt")  # untouched file
    old_f0 = _hashes(db, "f0.txt")

    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    update(_job("update"), job_context(db, tmp_path), encoder_for=fake_encoder)

    assert _hashes(db, "f0.txt") and _hashes(db, "f0.txt") != old_f0
    assert _section_ids(db, "f1.txt") == before_f1  # never touched
    assert _node_ids(db)  # tree intact, not destroyed


def test_update_with_no_change_is_a_noop(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, _origin = built
    nodes_before = _node_ids(db)
    with db.connect() as conn:
        sections_before = int(
            conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        )

    update(_job("update"), job_context(db, tmp_path), encoder_for=fake_encoder)

    with db.connect() as conn:
        sections_after = int(
            conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        )
    assert sections_after == sections_before
    assert _node_ids(db) == nodes_before


def alien_encoder(model_id: str):
    """An encoder that puts anything marked ``alien`` in its own direction."""

    def encode(texts: list[str]) -> list[list[float]]:
        return [
            [0.0, 1.0] + [0.0] * (DIMS - 2)
            if "alien" in text
            else [1.0] + [0.0] * (DIMS - 1)
            for text in texts
        ]

    return encode


def add_alien(origin: Path, name: str) -> None:
    (origin / "alien").mkdir(exist_ok=True)
    (origin / "alien" / name).write_text(f"alien {name} unlike everything\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", f"alien {name}")


def add_twins(origin: Path, name: str) -> None:
    """Commit the SAME body at two paths — one content hash, two sections."""
    body = f"module {name} does thing number {name}\n"
    (origin / "alien").mkdir(exist_ok=True)
    (origin / name).write_text(body)
    (origin / "alien" / name).write_text(body)
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", f"twins {name}")


def _pending(db: Database) -> list[tuple[str, int]]:
    with db.connect() as conn:
        return [(path, batch) for _, _, path, batch in pending(conn, "default")]


def _log(db: Database) -> list[tuple[str, str]]:
    with db.connect() as conn:
        return [
            (row["verdict"], row["action"])
            for row in conn.execute(
                "SELECT verdict, action FROM update_log ORDER BY id"
            ).fetchall()
        ]


def _forced_node(db: Database, path: str) -> int | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT m.node_id AS node_id FROM node_members m "
            "JOIN sections s ON s.id = m.section_id "
            "WHERE s.path = ? AND m.forced = 1",
            (path,),
        ).fetchone()
    return None if row is None else int(row["node_id"])


def test_update_parks_an_alien_chunk_then_ages_it_in(
    built: tuple[Database, Path],
    tmp_path: Path,
) -> None:
    db, origin = built
    add_alien(origin, "zz.txt")
    update(_job("update"), job_context(db, tmp_path), encoder_for=alien_encoder)

    assert _pending(db) == [("alien/zz.txt", 1)]  # sub-TAU, parked
    assert_pool_invariant(db, "default", "emb")

    for i in range(MAX_AGE + 1):  # batches 2..6 carry it past MAX_AGE
        edit(origin, "f1.txt", f"module 1 revision {i}\n")
        update(
            _job("update"), job_context(db, tmp_path), encoder_for=alien_encoder
        )
        assert_pool_invariant(db, "default", "emb")

    assert _pending(db) == []  # aged out, never stranded
    assert _forced_node(db, "alien/zz.txt") is not None
    assert ("age", "forced") in _log(db)


def test_update_drains_a_full_pool_in_the_same_batch(
    built: tuple[Database, Path],
    tmp_path: Path,
) -> None:
    db, origin = built
    for i in range(MIN_POINTS):
        add_alien(origin, f"a{i}.txt")

    update(_job("update"), job_context(db, tmp_path), encoder_for=alien_encoder)

    # a pool the real mini-pipeline can reduce never survives its own batch:
    # cores emit as leaf nodes, residual noise is force-assigned.
    assert _pending(db) == []
    assert [entry for entry in _log(db) if entry[0] == "drain"]
    assert_pool_invariant(db, "default", "emb")


def test_update_parks_only_the_twin_that_fits_nowhere(
    built: tuple[Database, Path],
    tmp_path: Path,
) -> None:
    # duplicate content, different paths: one content hash but two sections,
    # and the ALPHA-0.5 path blend gives them different combined vectors, so
    # g9.txt clears TAU while alien/g9.txt parks. The pool is keyed by SECTION
    # precisely so it can hold one without claiming the other is homeless.
    db, origin = built
    add_twins(origin, "g9.txt")
    update(_job("update"), job_context(db, tmp_path), encoder_for=alien_encoder)

    assert _pending(db) == [("alien/g9.txt", 1)]
    assert_pool_invariant(db, "default", "emb")

    for i in range(MAX_AGE + 1):  # batches 2..7 carry the twin past MAX_AGE
        edit(origin, "f1.txt", f"module 1 revision {i}\n")
        update(
            _job("update"), job_context(db, tmp_path), encoder_for=alien_encoder
        )
        assert_pool_invariant(db, "default", "emb")

    assert _pending(db) == []
    assert _forced_node(db, "alien/g9.txt") is not None
    assert _forced_node(db, "g9.txt") is None  # its homed twin never moved


def _batch(db: Database) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT batch FROM tree_batch WHERE tree = 'default'"
        ).fetchone()
    return 0 if row is None else int(row["batch"])


def add_source(db: Database, name: str, url: str) -> None:
    with db.connect() as conn, conn:
        registry_store.insert(
            conn,
            "sources",
            name,
            json.dumps({"name": name, "type": "git", "url": url, "auth": {}}),
            None,
            "t",
        )


def test_n_update_runs_advance_the_batch_counter_by_exactly_n(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, origin = built
    start = _batch(db)
    for i in range(4):
        edit(origin, "f1.txt", f"module 1 revision {i}\n")
        update(
            _job("update"), job_context(db, tmp_path), encoder_for=fake_encoder
        )
        assert _batch(db) == start + i + 1


def test_a_run_over_two_changed_sources_bumps_the_counter_once(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the defect: _next_batch lived in _update_source, so a run over three
    # changed sources counted three batches and aged parked chunks that much
    # faster than MAX_AGE intends (#099).
    db, origin = built
    second = tmp_path / "second-repo"
    add_source(db, "second", make_repo(second, files=4))
    update(_job("update"), job_context(db, tmp_path), encoder_for=fake_encoder)
    start = _batch(db)

    edit(origin, "f1.txt", "module 1 changed in the first source\n")
    edit(second, "f1.txt", "module 1 changed in the second source\n")
    update(_job("update"), job_context(db, tmp_path), encoder_for=fake_encoder)

    assert _batch(db) == start + 1  # one run, one batch — not one per source
    assert _hashes(db, "f1.txt")  # both sources' changes did land
    with db.connect() as conn:
        changed = {
            row["source"]
            for row in conn.execute(
                "SELECT DISTINCT source FROM sections WHERE path = 'f1.txt'"
            ).fetchall()
        }
    assert changed == {"repo", "second"}


def test_a_run_with_no_changes_leaves_the_counter_alone(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, _origin = built
    before = _batch(db)
    update(_job("update"), job_context(db, tmp_path), encoder_for=fake_encoder)
    assert _batch(db) == before


def test_ageing_measures_runs_not_changed_sources(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the boundary the re-run watches: a chunk parked at batch B is forced only
    # once current - B > MAX_AGE. With the counter bumping per SOURCE, two
    # changed sources per run reached that in half the runs.
    db, origin = built
    second = tmp_path / "second-repo"
    add_source(db, "second", make_repo(second, files=4))
    add_alien(origin, "zz.txt")
    update(_job("update"), job_context(db, tmp_path), encoder_for=alien_encoder)
    parked = _pending(db)
    assert parked == [("alien/zz.txt", _batch(db))]
    parked_at = parked[0][1]

    for i in range(MAX_AGE):  # MAX_AGE runs, each touching BOTH sources
        edit(origin, "f1.txt", f"first source revision {i}\n")
        edit(second, "f1.txt", f"second source revision {i}\n")
        update(
            _job("update"), job_context(db, tmp_path), encoder_for=alien_encoder
        )
        assert_pool_invariant(db, "default", "emb")

    assert _batch(db) - parked_at == MAX_AGE  # exactly at the boundary
    assert _pending(db) == [("alien/zz.txt", parked_at)]  # not forced yet

    edit(origin, "f1.txt", "one run past the boundary\n")
    edit(second, "f1.txt", "one run past the boundary\n")
    update(_job("update"), job_context(db, tmp_path), encoder_for=alien_encoder)

    assert _batch(db) - parked_at == MAX_AGE + 1
    assert _pending(db) == []  # forced only now
    assert _forced_node(db, "alien/zz.txt") is not None
