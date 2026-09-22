"""T36: the propagate judge cascade — mark ancestors stale, marks only."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import store as cluster_store
from hrono.cluster.build import ClusterResult
from hrono.db.database import Database
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS
from hrono.llm.client import (
    Completion,
    CompletionRequest,
    CompletionResult,
    Usage,
)
from hrono.registry import store as registry_store
from hrono.summarize import briefs, propagate
from hrono.summarize.propagate import (
    _JUDGE_MAX_TOKENS,
    BEST_OF,
    _majority,
    _verdict,
)
from tests.context import job_context

TREE = "default"


class FakeJudge:
    def __init__(self, *replies: str) -> None:
        self.replies = replies
        self.calls = 0
        self.requests: list[CompletionRequest] = []

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        self.requests.append(request)
        reply = self.replies[min(self.calls - 1, len(self.replies) - 1)]
        return CompletionResult(reply, Usage(1, 1))


def _register(conn: object) -> None:
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
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "prompts",
        "judge",
        json.dumps(
            {
                "name": "judge",
                "role": "judge",
                "template": "S {source} M {summary}",
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


def _brief(conn: object, node_id: int, member_sig: str) -> None:
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node_id,
        f"brief for {node_id}",
        model_name="sonnet",
        prompt_name="brief-upper",
        prompt_hash="h",
        member_signature=member_sig,
        input_tokens=1,
        output_tokens=1,
    )


def _leaf(conn: object) -> int:
    """A level-0 node whose stored brief signature no longer matches."""
    members = []
    for i in range(2):
        body = f"leaf section {i}\n".encode()
        digest = content_hash(body)
        upsert_content(conn, digest, body)  # type: ignore[arg-type]
        members.append(
            insert_section(
                conn,  # type: ignore[arg-type]
                source="repo",
                address=Address("git", "ex/repo", "f.txt", "v1"),
                start=0,
                end=len(body),
                content_hash=digest,
                ordinal=i,
            )
        )
    node_id = cluster_store.add_leaf_node(
        conn, TREE, [(s, False, None) for s in members]
    )
    _brief(conn, node_id, member_sig="STALE-DOES-NOT-MATCH")
    return node_id


def _upper(conn: object, level: int, child_id: int) -> int:
    cursor = conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO nodes(tree, level, label, created_at) VALUES (?, ?, 0, ?)",
        (TREE, level, "t"),
    )
    node_id = int(cursor.lastrowid or 0)
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO node_children(parent_id, child_id, attached, "
        "assignment_similarity, created_at) VALUES (?, ?, 0, NULL, ?)",
        (node_id, child_id, "t"),
    )
    _brief(conn, node_id, member_sig=f"sig-{level}")
    return node_id


def _job() -> Job:
    return Job(
        id="p",
        parent_id=None,
        tree=TREE,
        op="propagate",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        _register(conn)
    yield database
    database.close()


def _run(db: Database, judge: Completion, tmp_path: Path) -> None:
    propagate.propagate(_job(), job_context(db, tmp_path), client=judge)


def _stale(db: Database, node_id: int) -> int:
    with db.connect() as conn:
        return int(briefs.get(conn, node_id)["stale"])


def test_registered() -> None:
    assert "propagate" in OPS


def test_majority_of_three() -> None:
    assert _majority(["none", "none", "major"]) == "none"
    assert _majority(["minor", "major", "major"]) == "major"
    assert _majority(["none", "minor", "major"]) == "minor"


def test_a_verdict_is_the_leading_word_not_a_substring() -> None:
    # F33: the prompt asks for one word, the model explains itself half the
    # time, and an explanation repeats the prompt's own vocabulary.
    assert _verdict("none") == "none"
    assert _verdict("minor\n\nThe removal of `as name` aliasing is...") == (
        "minor"
    )
    assert _verdict("none - this is not a major change") == "none"
    assert _verdict("minor, certainly not major") == "minor"
    assert _verdict("**MAJOR**\nthe API changed shape") == "major"


def test_prose_that_leads_with_no_verdict_is_not_a_verdict() -> None:
    # the old substring rule scored each of these; none of them answers the
    # question, and a guessed `none` is the direction that suppresses a climb.
    assert _verdict("This is a MAJOR change") is None
    assert _verdict("only a minor tweak") is None
    assert _verdict("no meaningful change") is None
    assert _verdict("") is None
    assert _verdict("   ") is None


def test_material_verdict_climbs_ancestors_bounded_by_d_max(
    db: Database,
    tmp_path: Path,
) -> None:
    with db.connect() as conn, conn:
        leaf = _leaf(conn)
        ancestors = []
        child = leaf
        for level in range(1, 7):  # six ancestors: n1..n6
            child = _upper(conn, level, child)
            ancestors.append(child)

    judge = FakeJudge("major")
    _run(db, judge, tmp_path)

    assert judge.calls == 3  # best-of-3 over the one changed leaf
    # D_MAX is 5: the nearest five ancestors are marked, the sixth is not
    assert [_stale(db, n) for n in ancestors] == [1, 1, 1, 1, 1, 0]
    with db.connect() as conn:
        log = conn.execute(
            "SELECT verdict, action, climbed_to FROM update_log"
        ).fetchall()
        drift = conn.execute(
            "SELECT drift FROM tree_batch WHERE tree = ?", (TREE,)
        ).fetchone()["drift"]
    assert len(log) == 1
    assert log[0]["verdict"] == "major" and log[0]["action"] == "propagated"
    assert log[0]["climbed_to"] == 5  # highest level marked
    assert drift == 2  # major contributes 2


def test_none_verdict_marks_nothing_and_logs_skip(
    db: Database, tmp_path: Path
) -> None:
    with db.connect() as conn, conn:
        leaf = _leaf(conn)
        parent = _upper(conn, 1, leaf)

    _run(db, FakeJudge("none"), tmp_path)

    assert _stale(db, parent) == 0  # climb never started
    with db.connect() as conn:
        row = conn.execute(
            "SELECT verdict, action, climbed_to FROM update_log"
        ).fetchone()
    assert row["action"] == "skipped" and row["climbed_to"] is None


def test_unchanged_leaf_is_not_judged(db: Database, tmp_path: Path) -> None:
    with db.connect() as conn, conn:
        # a leaf whose stored brief signature matches its members: not changed
        members = []
        body = b"stable\n"
        digest = content_hash(body)
        upsert_content(conn, digest, body)
        members.append(
            insert_section(
                conn,
                source="repo",
                address=Address("git", "ex/repo", "s.txt", "v1"),
                start=0,
                end=len(body),
                content_hash=digest,
                ordinal=0,
            )
        )
        node_id = cluster_store.add_leaf_node(
            conn, TREE, [(members[0], False, None)]
        )
        _brief(conn, node_id, member_sig=briefs.member_signature(conn, node_id))

    judge = FakeJudge("major")
    _run(db, judge, tmp_path)
    assert judge.calls == 0  # nothing changed, nothing judged


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


def _fake_encoder(model_id: str):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (DIMS - 1) for _ in texts]

    return encode


def _fake_build(vectors: object, *, init: object = None) -> ClusterResult:
    n = len(vectors)  # type: ignore[arg-type]
    return ClusterResult(
        labels=tuple(i // 3 for i in range(n)),
        attached=tuple(False for _ in range(n)),
        assignment_similarity=tuple(None for _ in range(n)),
        coords=tuple((0.0,) for _ in range(n)),
    )


def _make_repo(path: Path) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "t@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True
    )
    for i in range(9):
        (path / f"f{i}.txt").write_text(f"module {i} does thing {i}\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "one"], check=True)
    return path.as_uri()


def test_marked_ancestor_regenerates_only_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    url = _make_repo(tmp_path / "src-repo")
    database = Database.at(tmp_path / "hrono.db")
    try:
        with database.connect() as conn, conn:
            registry_store.insert(
                conn,
                "sources",
                "repo",
                json.dumps(
                    {"name": "repo", "type": "git", "url": url, "auth": {}}
                ),
                None,
                "t",
            )
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
            _register(conn)
        from hrono.tree.maintain import maintain

        maintain(
            Job(
                id="m",
                parent_id=None,
                tree=TREE,
                op="maintain",
                scope={},
                status="running",
                error=None,
                created_at="t",
                updated_at="t",
            ),
            job_context(database, tmp_path),
            encoder_for=_fake_encoder,
            client=FakeCompletion(),
            build=_fake_build,
        )

        # simulate an update that changed one leaf's membership
        with database.connect() as conn, conn:
            leaf = int(
                conn.execute(
                    "SELECT id FROM nodes WHERE tree = ? AND level = 0 "
                    "ORDER BY id LIMIT 1",
                    (TREE,),
                ).fetchone()["id"]
            )
            members = cluster_store.node_member_rows(conn, leaf)
            cluster_store.remove_member(conn, leaf, members[0][0])

        # before propagate: the parent looks fresh (#068 signature unchanged)
        from hrono.summarize.brief_upper import brief_upper

        before = FakeCompletion()
        brief_upper(
            Job(
                id="bu",
                parent_id=None,
                tree=TREE,
                op="brief-upper",
                scope={"level": 1},
                status="running",
                error=None,
                created_at="t",
                updated_at="t",
            ),
            job_context(database, tmp_path),
            client=before,
        )
        assert before.calls == 0  # nothing regenerates without propagate

        propagate.propagate(
            _job(), job_context(database, tmp_path), client=FakeJudge("major")
        )

        after = FakeCompletion()
        brief_upper(
            Job(
                id="bu2",
                parent_id=None,
                tree=TREE,
                op="brief-upper",
                scope={"level": 1},
                status="running",
                error=None,
                created_at="t",
                updated_at="t",
            ),
            job_context(database, tmp_path),
            client=after,
        )
        assert after.calls >= 1  # only the marked ancestor path regenerates
    finally:
        database.close()


def test_a_panel_member_is_re_asked_once_then_abstains(
    db: Database, tmp_path: Path
) -> None:
    with db.connect() as conn, conn:
        leaf = _leaf(conn)
        parent = _upper(conn, 1, leaf)

    # member 1 answers on the retry; members 2 and 3 answer first time
    judge = FakeJudge("waffle", "major", "major", "major")
    _run(db, judge, tmp_path)

    assert judge.calls == BEST_OF + 1  # exactly one retry, not a retry storm
    assert _stale(db, parent) == 1
    with db.connect() as conn:
        row = conn.execute("SELECT verdict, action FROM update_log").fetchone()
    assert (row["verdict"], row["action"]) == ("major", "propagated")


def test_a_panel_that_never_parses_abstains_loudly(
    db: Database, tmp_path: Path
) -> None:
    with db.connect() as conn, conn:
        leaf = _leaf(conn)
        parent = _upper(conn, 1, leaf)

    judge = FakeJudge("I cannot determine the significance of this change")
    _run(db, judge, tmp_path)

    # every member re-asked once, then abstained: no verdict, and no silent
    # `none` quietly suppressing a real cascade
    assert judge.calls == BEST_OF * 2
    assert _stale(db, parent) == 0
    with db.connect() as conn:
        row = conn.execute(
            "SELECT verdict, action, climbed_to FROM update_log"
        ).fetchone()
        drift = conn.execute(
            "SELECT COUNT(*) FROM tree_batch WHERE tree = ?", (TREE,)
        ).fetchone()[0]
    assert (row["verdict"], row["action"]) == ("unparseable", "abstained")
    assert row["climbed_to"] is None
    assert drift == 0  # an abstention is not drift


def test_a_partial_panel_still_decides(db: Database, tmp_path: Path) -> None:
    with db.connect() as conn, conn:
        leaf = _leaf(conn)
        parent = _upper(conn, 1, leaf)

    # member 1 abstains (two unparseable replies), members 2 and 3 say major
    judge = FakeJudge("waffle", "waffle", "major", "major")
    _run(db, judge, tmp_path)

    assert _stale(db, parent) == 1
    with db.connect() as conn:
        row = conn.execute("SELECT verdict, action FROM update_log").fetchone()
    assert (row["verdict"], row["action"]) == ("major", "propagated")


def test_the_judge_call_is_capped_to_a_verdict(
    db: Database, tmp_path: Path
) -> None:
    with db.connect() as conn, conn:
        _leaf(conn)

    judge = FakeJudge("none")
    _run(db, judge, tmp_path)

    assert judge.calls == BEST_OF  # BEST_OF calls per topic and no more
    params = [r.model["params"] for r in judge.requests]
    assert all(p["max_tokens"] == _JUDGE_MAX_TOKENS for p in params)
    with db.connect() as conn:
        stored = json.loads(
            registry_store.get(conn, "models", "sonnet")["config"]
        )
    assert stored["params"] == {}  # the cap is per call, not a config write


def _log_rows(db: Database) -> list[tuple[str, str]]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT verdict, action FROM update_log ORDER BY id"
        ).fetchall()
    return [(r["verdict"], r["action"]) for r in rows]


def _drift(db: Database) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT drift FROM tree_batch WHERE tree = ?", (TREE,)
        ).fetchone()
    return int(row["drift"]) if row is not None else 0


def test_a_reclaimed_re_run_judges_nothing_twice(
    db: Database, tmp_path: Path
) -> None:
    # #093 reclaims a job whose work committed but whose status write failed,
    # so the SAME propagate runs again over an unchanged tree.
    with db.connect() as conn, conn:
        leaf = _leaf(conn)
        parent = _upper(conn, 1, leaf)

    judge = FakeJudge("major")
    _run(db, judge, tmp_path)
    first = (judge.calls, _log_rows(db), _drift(db), _stale(db, parent))

    _run(db, judge, tmp_path)  # the reclaimed re-run

    assert first == (BEST_OF, [("major", "propagated")], 2, 1)
    assert judge.calls == BEST_OF  # no second panel: real money, not re-spent
    assert _log_rows(db) == [
        ("major", "propagated")
    ]  # audit not double-counted
    assert _drift(db) == 2  # one increment per judged topic, not two


def test_a_membership_change_after_a_run_is_judged_again(
    db: Database, tmp_path: Path
) -> None:
    # the fix must not suppress real work: the marker is per member SET.
    with db.connect() as conn, conn:
        leaf = _leaf(conn)
        _upper(conn, 1, leaf)

    judge = FakeJudge("major")
    _run(db, judge, tmp_path)
    assert judge.calls == BEST_OF

    with db.connect() as conn, conn:  # a new member arrives: real change
        body = b"a section that joined after the judgement\n"
        digest = content_hash(body)
        upsert_content(conn, digest, body)
        section = insert_section(
            conn,
            source="repo",
            address=Address("git", "ex/repo", "new.txt", "v1"),
            start=0,
            end=len(body),
            content_hash=digest,
            ordinal=0,
        )
        conn.execute(
            "INSERT INTO node_members(node_id, section_id, attached, forced, "
            "assignment_similarity, created_at) VALUES (?, ?, 1, 0, NULL, 't')",
            (leaf, section),
        )

    _run(db, judge, tmp_path)

    assert judge.calls == BEST_OF * 2  # judged again, because it really changed
    assert len(_log_rows(db)) == 2


def test_a_re_brief_clears_the_judged_marker(
    db: Database, tmp_path: Path
) -> None:
    # a regenerated brief has not been judged: `upsert` does not list the
    # column, so INSERT OR REPLACE resets it.
    with db.connect() as conn, conn:
        leaf = _leaf(conn)

    _run(db, FakeJudge("none"), tmp_path)
    with db.connect() as conn:
        assert briefs.get(conn, leaf)["judged_signature"] is not None

    with db.connect() as conn, conn:
        _brief(conn, leaf, member_sig="STILL-DOES-NOT-MATCH")

    with db.connect() as conn:
        assert briefs.get(conn, leaf)["judged_signature"] is None


def test_an_abstained_topic_is_judged_again_on_the_next_run(
    db: Database, tmp_path: Path
) -> None:
    # abstention is not a judgement; a re-run must try the topic again rather
    # than inherit "already handled" from a panel that answered nothing.
    with db.connect() as conn, conn:
        _leaf(conn)

    judge = FakeJudge("no idea what this change means")
    _run(db, judge, tmp_path)
    _run(db, judge, tmp_path)

    assert (
        judge.calls == BEST_OF * 4
    )  # two runs, each a full panel with retries
    assert _log_rows(db) == [
        ("unparseable", "abstained"),
        ("unparseable", "abstained"),
    ]


def test_judging_a_leaf_does_not_suppress_its_re_brief(
    db: Database, tmp_path: Path
) -> None:
    # the ticket's flagged open question, answered as a test: the judged marker
    # lives in its own column, so #064's freshness (which reads
    # `member_signature`) still sees the leaf as owing a brief after judgement.
    with db.connect() as conn, conn:
        leaf = _leaf(conn)

    with db.connect() as conn:
        before = briefs.stale_or_missing(conn, TREE, 0, "h", "sonnet")

    _run(db, FakeJudge("major"), tmp_path)

    with db.connect() as conn:
        after = briefs.stale_or_missing(conn, TREE, 0, "h", "sonnet")
    assert before == after == (leaf,)
