"""`update` applies a change batch incrementally over a built tree."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import placement
from hrono.cluster.build import ClusterResult
from hrono.cluster.incubator import pending
from hrono.cluster.recipe import MIN_POINTS
from hrono.db.database import Database
from hrono.export import store as export_store
from hrono.export.collapse import collapse
from hrono.export.render import render
from hrono.jobs.model import Job
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.summarize import store as condensations
from hrono.summarize.resolve import resolve_prompt, resolve_text_model
from hrono.summarize.shape import talks_back
from hrono.tree.maintain import maintain
from hrono.tree.settle import settle
from hrono.tree.update import update
from tests import world
from tests.cluster.harness import planted_groups
from tests.cluster.invariant import (
    assert_every_leaf_is_reachable,
    assert_pool_invariant,
)
from tests.context import job_context
from tests.repo_template import memoized

DIMS = 8


class FakeCompletion:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return CompletionResult(
            "This topic covers the module's API and how its parts fit.",
            Usage(10, 4),
        )


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


@memoized
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


def run_update(db: Database, tmp_path: Path) -> FakeCompletion:
    """Drive `update` the way the worker does; it is an LLM caller."""
    client = FakeCompletion()
    update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=client,
    )
    return client


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


@pytest.fixture(scope="module")
def _world(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """The tree `maintain` builds over a nine-file repo, built once."""
    root = tmp_path_factory.mktemp("world")
    with pytest.MonkeyPatch.context() as patch:
        patch.chdir(root)
        url = make_repo(root / "src-repo")
        database = Database.at(root / "hrono.db")
        with database.connect() as conn, conn:
            register(conn, url)
        maintain(
            _job("maintain"),
            job_context(database, root),
            encoder_for=fake_encoder,
            client=FakeCompletion(),
            build=fake_build,
        )
        database.close()
    return root, world.snapshot(root, tmp_path_factory.mktemp("copy"))


@pytest.fixture
def tmp_path(_world: tuple[Path, Path]) -> Path:
    """Shadows pytest's: every test here starts in the built world."""
    root, copy = _world
    return world.restore(copy, root)


@pytest.fixture
def built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Database, Path]]:
    monkeypatch.chdir(tmp_path)
    database = Database.at(tmp_path / "hrono.db")
    yield database, tmp_path / "src-repo"
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


def test_update_swaps_changed_file_and_leaves_untouched_alone(
    built: tuple[Database, Path],
    tmp_path: Path,
) -> None:
    db, origin = built
    before_f1 = _section_ids(db, "f1.txt")  # untouched file
    old_f0 = _hashes(db, "f0.txt")

    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    run_update(db, tmp_path)

    assert _hashes(db, "f0.txt") and _hashes(db, "f0.txt") != old_f0
    assert _section_ids(db, "f1.txt") == before_f1  # never touched
    assert _node_ids(db)  # tree intact, not destroyed


def test_update_with_no_change_is_a_noop(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, _origin = built
    nodes_before = _node_ids(db)
    batch_before = _batch(db)
    with db.connect() as conn:
        sections_before = int(
            conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        )

    run_update(db, tmp_path)

    with db.connect() as conn:
        sections_after = int(
            conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        )
    assert sections_after == sections_before
    assert _node_ids(db) == nodes_before
    assert _batch(db) == batch_before  # a run with no changes keeps the counter


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


def test_update_homes_an_alien_chunk_in_the_run_that_parks_it(
    built: tuple[Database, Path],
    tmp_path: Path,
) -> None:
    # sub-TAU, so it parks; the pool is too small to cluster, so the end of
    # the SAME run force-assigns it to its nearest topic. Nothing waits for a
    # later run.
    db, origin = built
    add_alien(origin, "zz.txt")
    update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=alien_encoder,
        client=FakeCompletion(),
    )

    assert _pending(db) == []  # homed, never stranded
    assert _forced_node(db, "alien/zz.txt") is not None
    assert ("home", "forced") in _log(db)
    assert_pool_invariant(db, "default", "emb")


def test_update_drains_a_full_pool_in_the_same_run(
    built: tuple[Database, Path],
    tmp_path: Path,
) -> None:
    db, origin = built
    for i in range(MIN_POINTS):
        add_alien(origin, f"a{i}.txt")

    update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=alien_encoder,
        client=FakeCompletion(),
    )

    # a pool the real mini-pipeline can reduce never survives its own run:
    # cores emit as leaf nodes, residual noise is force-assigned.
    assert _pending(db) == []
    assert [entry for entry in _log(db) if entry[0] == "drain"]
    assert_pool_invariant(db, "default", "emb")


def test_update_parks_only_the_twin_that_fits_nowhere(
    built: tuple[Database, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # duplicate content, different paths: one content hash but two sections,
    # and the folder view gives them different clustering vectors: g9.txt
    # sits with the root files (0.908), alien/g9.txt one folder away (0.881).
    # Identical text in one repository clears the real TAU either way, so the
    # bar is set between the two. The pool is keyed by SECTION precisely so
    # it can hold one without claiming the other is homeless, and the run's
    # home pass forces only the parked twin.
    monkeypatch.setattr(placement, "TAU", 0.895)
    db, origin = built
    add_twins(origin, "g9.txt")
    update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=alien_encoder,
        client=FakeCompletion(),
    )

    assert _pending(db) == []
    assert_pool_invariant(db, "default", "emb")
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
            _job("update"),
            job_context(db, tmp_path),
            encoder_for=fake_encoder,
            client=FakeCompletion(),
        )
        assert _batch(db) == start + i + 1


def test_a_run_over_two_changed_sources_bumps_the_counter_once(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the batch counter must advance once per run, not once per source: the
    # batch a run stamps on the chunks it parks names that run.
    db, origin = built
    second = tmp_path / "second-repo"
    add_source(db, "second", make_repo(second, files=4))
    run_update(db, tmp_path)
    start = _batch(db)

    edit(origin, "f1.txt", "module 1 changed in the first source\n")
    edit(second, "f1.txt", "module 1 changed in the second source\n")
    run_update(db, tmp_path)

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


def rename(origin: Path, old: str, new: str) -> None:
    _git(origin, "mv", old, new)
    _git(origin, "commit", "-qm", f"rename {old} -> {new}")


def _node_of(db: Database, path: str) -> tuple[int | None, float | None]:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT m.node_id AS node, m.assignment_similarity AS sim "
            "FROM node_members m JOIN sections s ON s.id = m.section_id "
            "WHERE s.path = ?",
            (path,),
        ).fetchone()
    return (None, None) if row is None else (int(row["node"]), row["sim"])


def _counts(db: Database) -> tuple[int, int]:
    with db.connect() as conn:
        return (
            int(
                conn.execute("SELECT COUNT(*) FROM node_members").fetchone()[0]
            ),
            int(conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]),
        )


def _signatures(db: Database) -> dict[int, str]:
    with db.connect() as conn:
        return {
            int(r["id"]): r["signature"]
            for r in conn.execute("SELECT id, signature FROM nodes").fetchall()
        }


def test_a_pure_rename_keeps_the_section_in_its_node(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # `git mv` of byte-identical content must not eject the file from its
    # cluster and park it — ALPHA 0.5 makes the path half the blended
    # vector's norm, so a rename alone can drop a working member below TAU.
    db, origin = built
    node_before, sim_before = _node_of(db, "f1.txt")
    assert node_before is not None
    members_before, _ = _counts(db)
    signatures_before = _signatures(db)

    rename(origin, "f1.txt", "renamed.txt")
    run_update(db, tmp_path)

    assert _node_of(db, "f1.txt") == (None, None)  # the old path is gone
    assert _node_of(db, "renamed.txt") == (node_before, sim_before)
    members_after, _ = _counts(db)
    assert members_after == members_before  # membership count unchanged
    assert _pending(db) == []  # nothing parked
    assert _signatures(db) == signatures_before  # content signature untouched
    assert_pool_invariant(db, "default", "emb")


def test_a_rename_does_not_re_embed_the_content(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, origin = built
    _, embeddings_before = _counts(db)
    (origin / "moved").mkdir()
    rename(origin, "f2.txt", "moved/f2.txt")
    run_update(db, tmp_path)
    _, embeddings_after = _counts(db)
    # exactly one new vector: the new PATH string, never the content again
    assert embeddings_after == embeddings_before + 1


def test_a_rename_that_changes_the_grammar_is_a_normal_change(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the one move that is not in place: a new extension splits the file under
    # a different grammar, so the sections are not the same content any more.
    db, origin = built
    rename(origin, "f3.txt", "f3.md")
    run_update(db, tmp_path)
    node, _ = _node_of(db, "f3.md")
    assert node is not None  # still placed, just not short-circuited
    assert_pool_invariant(db, "default", "emb")


def test_renaming_a_force_homed_chunk_leaves_nothing_pending(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the alien is parked and homed by force in its first run; renaming it
    # later must not strand it outside the tree either.
    db, origin = built
    add_alien(origin, "zz.txt")
    update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=alien_encoder,
        client=FakeCompletion(),
    )
    assert _forced_node(db, "alien/zz.txt") is not None

    rename(origin, "alien/zz.txt", "alien/renamed-zz.txt")
    update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=alien_encoder,
        client=FakeCompletion(),
    )

    assert _pending(db) == []
    assert _node_of(db, "alien/renamed-zz.txt")[0] is not None
    assert_pool_invariant(db, "default", "emb")


def test_a_rename_preserves_a_recorded_similarity(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the fixture's build records no similarity, so drive one first: a NEW file
    # joins through the placement rule and its similarity is stored. The rename
    # must carry THAT number, not re-derive or blank it.
    db, origin = built
    (origin / "f9.txt").write_text("module 9 does thing number 9\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "add f9")
    run_update(db, tmp_path)
    node_before, sim_before = _node_of(db, "f9.txt")
    assert node_before is not None
    assert sim_before is not None  # a real recorded assignment

    rename(origin, "f9.txt", "f9-renamed.txt")
    run_update(db, tmp_path)

    assert _node_of(db, "f9-renamed.txt") == (node_before, sim_before)


_PLANTED, _ = planted_groups(
    groups=2, per_group=7, dim=DIMS - 1, spread=0.1, noise=0, seed=1
)


def planted(model_id: str):
    """Aliens land in two real cores; the corpus keeps its flat direction."""

    def encode(texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            if "alien a" in text:
                index = int(text.split("alien a")[1].split(".")[0])
                out.append([0.0] + [float(v) for v in _PLANTED[index]])
            else:
                out.append([1.0] + [0.0] * (DIMS - 1))
        return out

    return encode


def test_a_leaf_update_drained_in_is_healed_by_the_next_settle(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # attach-by-proximity's residual, driven rather than argued. `update`
    # writes no brief, so a drained leaf is unreachable from root.md the
    # moment it is born. But update condenses what it ingests, so the next
    # settle can brief that leaf, which gives it the brief vector the attach
    # places it by: the gap lasts until the next settle, not a full pass.
    db, origin = built
    before = _leaf_ids(db)
    for i in range(14):
        add_alien(origin, f"a{i}.txt")

    update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=planted,
        client=FakeCompletion(),
    )

    emitted = set(_leaf_ids(db)) - set(before)
    assert emitted  # the drain turned the pool into a new topic
    assert _nodes_holding(db, "alien/") & emitted  # the chunks live there
    assert emitted.isdisjoint(_briefed(db))  # update never briefs
    assert emitted.isdisjoint(_parented(db))  # ... so nothing to place it by
    assert_pool_invariant(db, "default", "emb")
    assert _condensed(db, "alien/")  # but update DID condense what it ingested

    # so a settle now heals it: the condensations are there, so the leaf briefs,
    # so it has a brief vector, so attach-by-proximity can parent it.
    settle(
        _job("settle"),
        job_context(db, tmp_path),
        force=True,
        build=fake_build,
        encoder_for=planted,
        client=FakeCompletion(),
    )

    homes = _nodes_holding(db, "alien/")
    assert homes
    assert homes <= _briefed(db)
    assert homes <= _parented(db)
    files = _export(db)
    for node_id in homes:
        directory = next(
            p.rsplit("/", 1)[0]
            for p in files
            if p.endswith(f"-{node_id}/brief.md")
        )
        assert directory in files["root.md"]  # reachable by walking the map
    assert_every_leaf_is_reachable(db, "default")


def _condensed(db: Database, prefix: str) -> int:
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM condensations c "
                "JOIN sections s ON s.content_hash = c.content_hash "
                "WHERE s.path LIKE ?",
                (f"{prefix}%",),
            ).fetchone()[0]
        )


def _nodes_holding(db: Database, prefix: str) -> set[int]:
    with db.connect() as conn:
        return {
            int(r["node_id"])
            for r in conn.execute(
                "SELECT m.node_id FROM node_members m "
                "JOIN sections s ON s.id = m.section_id "
                "WHERE s.path LIKE ?",
                (f"{prefix}%",),
            ).fetchall()
        }


def _leaf_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return [
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE tree = 'default' AND level = 0"
            ).fetchall()
        ]


def _parented(db: Database) -> set[int]:
    with db.connect() as conn:
        return {
            int(r["child_id"])
            for r in conn.execute("SELECT child_id FROM node_children")
        }


def _briefed(db: Database) -> set[int]:
    with db.connect() as conn:
        return {
            int(r["node_id"])
            for r in conn.execute("SELECT node_id FROM briefs")
        }


def _export(db: Database) -> dict[str, str]:
    with db.connect() as conn:
        stored = export_store.load(conn, "default")
        assert stored is not None
        return render(conn, collapse(stored, 3))


def _uncovered_members(db: Database) -> int:
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM node_members m "
                "JOIN nodes n ON n.id = m.node_id "
                "LEFT JOIN section_coords c "
                "  ON c.tree = n.tree AND c.section_id = m.section_id "
                "WHERE n.tree = 'default' AND n.level = 0 "
                "AND c.section_id IS NULL"
            ).fetchone()[0]
        )


def test_an_update_leaves_every_member_with_a_coordinate(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # incremental placement decides by dot product and produces no UMAP
    # coordinate, so without a fill ONE update would break `stored_coords`'
    # coverage.
    db, origin = built
    assert _uncovered_members(db) == 0  # the full build covers everything

    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    run_update(db, tmp_path)

    assert _uncovered_members(db) == 0


def test_a_rebuild_after_an_update_warm_inits(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # and the consequence that matters: settle only runs BECAUSE churn
    # accumulated, and churn must not destroy the warm path.
    from hrono.cluster import op as cluster_op

    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    run_update(db, tmp_path)

    seen: dict[str, object] = {}

    def capture(vectors: object, *, init: object = None) -> ClusterResult:
        seen["init"] = init
        return fake_build(vectors, init=init)

    cluster_op.cluster(
        _job("cluster"), job_context(db, tmp_path), build=capture
    )

    assert seen["init"] is not None


def _uncondensed_members(db: Database) -> list[str]:
    with db.connect() as conn:
        return [
            r["path"]
            for r in conn.execute(
                "SELECT DISTINCT s.path AS path FROM node_members m "
                "JOIN sections s ON s.id = m.section_id "
                "WHERE NOT EXISTS (SELECT 1 FROM condensations d "
                "                  WHERE d.content_hash = s.content_hash)"
            ).fetchall()
        ]


def test_update_condenses_what_it_ingests(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # update must condense, not leave it to `maintain`: otherwise a section
    # an update brought in reaches the tree unsummarised until a full build —
    # and a brief reduces over condensations while its citations do not.
    db, origin = built
    assert _uncondensed_members(db) == []

    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    (origin / "brand-new.txt").write_text("a module that did not exist\n")
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "add a new file")

    client = run_update(db, tmp_path)

    assert _uncondensed_members(db) == []  # new AND changed, both covered
    assert client.calls  # it really did call out, not skip the stage


def test_a_second_update_over_unchanged_content_condenses_nothing(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the content-hash cache is what keeps this proportional to the change.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    first = run_update(db, tmp_path)
    assert first.calls

    second = run_update(db, tmp_path)

    assert second.calls == 0


def test_a_sync_that_changed_sources_reports_what_condense_spent(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # `_outcome` promises the `condense` key "when it ran", changed or not.
    db, origin = built
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")

    outcome = update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )

    assert outcome["changed"] is True
    assert outcome["condense"]["condensed"] >= 1  # type: ignore[index]


_TALKED_BACK = "Could you paste the file you would like me to condense?"


def test_an_update_over_unchanged_content_redoes_a_talked_back_condensation(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # `unusable-condensations` promises the next sync redoes these, so condense
    # must run even when no source changed — or on a steady tree the promise
    # is never kept.
    db, _ = built
    with db.connect() as conn, conn:
        model = str(resolve_text_model(conn, {}, "condense")["name"])
        digest = conn.execute(
            "SELECT content_hash FROM condensations WHERE model_name = ? "
            "ORDER BY content_hash LIMIT 1",
            (model,),
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM condensations WHERE content_hash = ?", (digest,)
        )
        condensations.upsert(  # what a run before the gate stored
            conn, digest, model, _TALKED_BACK, 1, 1
        )

    client = run_update(db, tmp_path)  # no source changed

    assert client.calls == 1  # exactly the one, nothing else re-condensed
    with db.connect() as conn:
        assert condensations.unusable(conn, model) == ()


class Refusing(FakeCompletion):
    """Talks back whenever the section is f4's, condenses everything else."""

    def complete(self, request: CompletionRequest) -> CompletionResult:
        if "module 4" not in request.content:
            return super().complete(request)
        self.calls += 1
        return CompletionResult(_TALKED_BACK, Usage(10, 4))


def _talk_back_on_f4(db: Database) -> tuple[str, str]:
    """Store a talk-back as f4's condensation, as an older run could."""
    with db.connect() as conn, conn:
        model = str(resolve_text_model(conn, {}, "condense")["name"])
        digest = conn.execute(
            "SELECT content_hash FROM sections WHERE path = 'f4.txt'"
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM condensations WHERE content_hash = ?", (digest,)
        )
        condensations.upsert(conn, digest, model, _TALKED_BACK, 1, 1)
    return model, digest


def _refusing_update(db: Database, tmp_path: Path) -> Refusing:
    client = Refusing()
    update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=client,
    )
    return client


def test_a_refused_redo_is_not_paid_again_on_an_unchanged_sync(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # a refusal is never cached, so without a guard the talk-back stays and
    # every sync of a steady tree pays two calls to be refused again, forever
    db, _ = built
    model, digest = _talk_back_on_f4(db)

    first = _refusing_update(db, tmp_path)
    second = _refusing_update(db, tmp_path)

    with db.connect() as conn:
        listed = [d for d, _, _ in condensations.unusable(conn, model)]
        request = condensations.request_for(
            resolve_text_model(conn, {}, "condense"),
            resolve_prompt(conn, "condense")[1],
        )
        held = condensations.redo(conn, model, request)
    assert first.calls == 2  # the redo and its one retry
    assert second.calls == 0
    assert held == ()  # nothing for a steady sync to run condense for
    assert listed == [digest]  # still on the operator's list


def test_a_refused_section_with_nothing_stored_is_listed_and_held(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # a NEW body refused on its first condense has no row to fail the gate;
    # it is listed from its refusal and not retried by the next changed sync
    db, origin = built
    edit(origin, "f4.txt", "module 4 was rewritten and the model refuses\n")
    first = _refusing_update(db, tmp_path)
    edit(origin, "f0.txt", "module 0 changed as well\n")

    second = _refusing_update(db, tmp_path)

    with db.connect() as conn:
        model = str(resolve_text_model(conn, {}, "condense")["name"])
        listed = condensations.unusable(conn, model)
    assert first.calls == 2
    assert second.calls == 1  # f0's new body only
    assert [(why, text) for _, why, text in listed] == [
        ("asks-the-caller", _TALKED_BACK)
    ]


def test_a_changed_body_is_condensed_after_a_refusal(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    db, origin = built
    model, digest = _talk_back_on_f4(db)
    _refusing_update(db, tmp_path)
    edit(origin, "f4.txt", "the file is now about something else\n")

    again = _refusing_update(db, tmp_path)

    with db.connect() as conn:
        now = conn.execute(
            "SELECT content_hash FROM sections WHERE path = 'f4.txt'"
        ).fetchone()[0]
        kept = condensations.get(conn, now, model)
    assert now != digest
    assert again.calls == 1  # the new body, condensed
    assert kept is not None and not talks_back(kept["text"])


@pytest.mark.parametrize(
    ("collection", "name", "field", "value"),
    [
        pytest.param("models", "sonnet", "model", "claude-2", id="model"),
        pytest.param("prompts", "condense", "template", "Y {content}", id="p"),
    ],
)
def test_a_changed_model_or_prompt_retries_a_refusal(
    built: tuple[Database, Path],
    tmp_path: Path,
    collection: str,
    name: str,
    field: str,
    value: str,
) -> None:
    db, _ = built
    _talk_back_on_f4(db)
    _refusing_update(db, tmp_path)
    with db.connect() as conn, conn:
        row = registry_store.get(conn, collection, name)
        config = {**json.loads(row["config"]), field: value}
        registry_store.replace(
            conn, collection, name, json.dumps(config), None, "t2"
        )

    again = _refusing_update(db, tmp_path)

    assert again.calls == 2  # asked again under the new request


def test_an_update_with_nothing_to_do_needs_no_text_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the condense stage resolves the text model before it looks at what is
    # pending, so an unguarded call would make a no-op run fail with "no text
    # model available" — an error naming a stage the user never asked for.
    monkeypatch.chdir(tmp_path)
    database = Database.at(tmp_path / "bare.db")
    try:
        with database.connect() as conn, conn:
            registry_store.insert(
                conn,
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
        update(  # no sources, no text model, nothing to do
            _job("update"),
            job_context(database, tmp_path),
            encoder_for=fake_encoder,
        )
    finally:
        database.close()


def test_update_ingests_only_the_sources_its_tree_declares(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    """The incremental door is scoped to the job's tree, like the build.

    `update` must not iterate the WHOLE source registry regardless of the
    job's tree, or `hrono tree sync beta` pulls another tree's sources into
    beta.
    """
    db, origin = built
    second = tmp_path / "second-repo"
    add_source(db, "second", make_repo(second, files=4))
    with db.connect() as conn, conn:
        registry_store.insert(
            conn,
            "trees",
            "default",
            json.dumps({"name": "default", "sources": ["repo"]}),
            None,
            "t",
        )

    edit(origin, "f1.txt", "the declared source changed\n")
    edit(second, "f1.txt", "the undeclared source changed too\n")
    run_update(db, tmp_path)

    with db.connect() as conn:
        ingested = {
            row["source"]
            for row in conn.execute(
                "SELECT DISTINCT source FROM sections "
                "WHERE source_type != 'node'"
            ).fetchall()
        }
    assert ingested == {"repo"}  # `second` was never this tree's to ingest


def _member_of(db: Database, section_id: int) -> int | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT node_id FROM node_members WHERE section_id = ?",
            (section_id,),
        ).fetchone()
    return None if row is None else int(row["node_id"])


def test_a_membership_pin_survives_an_edit_to_the_pinned_file(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    """A membership pin holds through the ingest door.

    Reconcile drops a changed file's sections and the 0030 trigger deletes
    their pins with them, so unless the pin is carried over ANY edit to a
    pinned file — including edits that leave the pinned section's bytes
    untouched — silently releases the operator's hold and lets placement
    move the chunk.
    """
    from hrono import pins

    db, origin = built
    section = _section_ids(db, "f0.txt")[0]
    anchor = _member_of(db, section)
    assert anchor is not None
    with db.connect() as conn, conn:
        pins.pin(conn, pins.MEMBERSHIP, section, reason="hand", anchor=anchor)

    edit(origin, "f0.txt", "a completely different module zero now\n")
    run_update(db, tmp_path)

    successor = _section_ids(db, "f0.txt")[0]
    with db.connect() as conn:
        held = pins.held_for(conn, pins.MEMBERSHIP, [successor])
    assert held == {successor: (anchor, "hand")}
    assert _member_of(db, successor) == anchor  # held in place, not re-scored


def test_a_membership_pin_survives_a_full_resplit(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    # the maintenance door of the same revert: `split` clears the whole
    # source and re-inserts every section under a new id, and the 0030
    # trigger wiped every membership pin with the old rows.
    from hrono import pins
    from hrono.ingest.split_op import split_source

    db, _origin = built
    section = _section_ids(db, "f0.txt")[0]
    anchor = _member_of(db, section)
    with db.connect() as conn, conn:
        pins.pin(conn, pins.MEMBERSHIP, section, reason="hand", anchor=anchor)

    split_source(
        Job(
            id="sp",
            parent_id=None,
            tree="default",
            op="split",
            scope={"name": "repo"},
            status="running",
            error=None,
            created_at="t",
            updated_at="t",
        ),
        job_context(db, tmp_path),
    )

    successor = _section_ids(db, "f0.txt")[0]
    assert successor != section  # the re-split really re-minted the id
    with db.connect() as conn:
        held = pins.held_for(conn, pins.MEMBERSHIP, [successor])
    assert held == {successor: (anchor, "hand")}


def test_update_rescues_a_section_an_earlier_run_left_homeless(
    built: tuple[Database, Path], tmp_path: Path
) -> None:
    """The crash-shaped hole: the window between update's two commits.

    An update that dies between its reconcile commit and its placement leaves
    sections in no node and no pool, and the next diff sees stored == current
    — so unless something looks for them, nothing places them again short of a
    full maintain.
    """
    db, _origin = built
    section = _section_ids(db, "f2.txt")[0]
    with db.connect() as conn, conn:
        conn.execute(
            "DELETE FROM node_members WHERE section_id = ?", (section,)
        )
        conn.execute("DELETE FROM pending WHERE section_id = ?", (section,))

    outcome = update(
        _job("update"),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )

    assert outcome.get("rescued") == 1
    with db.connect() as conn:
        placed = conn.execute(
            "SELECT 1 FROM node_members WHERE section_id = ?", (section,)
        ).fetchone()
        parked = conn.execute(
            "SELECT 1 FROM pending WHERE section_id = ?", (section,)
        ).fetchone()
    assert placed is not None or parked is not None  # never homeless again
