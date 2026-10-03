"""#221: a condensation that is the model talking back is never cached."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.jobs.ops import JobContext
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.server.app import create_app
from hrono.summarize import store
from hrono.summarize.condense import condense
from hrono.tree.maintain import maintain
from tests.context import job_context
from tests.summarize.test_condense import MODEL
from tests.summarize.test_condense import db as condense_db  # noqa: F401
from tests.summarize.test_condense import job as condense_job
from tests.tree.test_maintain import fake_build, fake_encoder, job, make_repo
from tests.tree.test_maintain import register as register_tree

CHATTER = (
    "I don't see any FAQ content to condense — the section you pasted only "
    "has the heading. Paste the md content here and I'll condense it for you."
)
GOOD = "Defines the a() helper, which returns 1."


class Talking:
    """Talks back for one section's body, condenses the rest."""

    def __init__(self, about: str | None) -> None:
        self.about = about
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        if self.about is not None and self.about in request.content:
            return CompletionResult(CHATTER, Usage(3, 3))
        return CompletionResult(GOOD, Usage(3, 3))


def test_a_reply_that_talks_back_is_retried_and_not_cached(
    condense_db: Database,  # noqa: F811
) -> None:
    client = Talking("def a()")

    outcome = condense(condense_job(), JobContext(condense_db), client=client)

    with condense_db.connect() as conn:
        stored = store.count(conn, MODEL)
        left = store.pending(conn, MODEL)
    assert client.calls == 3  # b once, a twice
    assert outcome["condensed"] == 1 and outcome["refused"] == 1
    assert stored == 1
    assert [body for _, body in left] == [b"def a(): return 1\n"]


def test_a_short_true_condensation_is_cached(
    condense_db: Database,  # noqa: F811
) -> None:
    class Terse:
        def complete(self, request: CompletionRequest) -> CompletionResult:
            return CompletionResult("Returns 1.", Usage(1, 1))

    condense(condense_job(), JobContext(condense_db), client=Terse())

    with condense_db.connect() as conn:
        assert store.count(conn, MODEL) == 2


class Built:
    def __init__(self, database: Database, root: Path) -> None:
        self.database = database
        self.root = root

    def briefs(self) -> dict[int, int]:
        with self.database.connect() as conn:
            return {
                int(r["node_id"]): int(r["stale"])
                for r in conn.execute("SELECT node_id, stale FROM briefs")
            }


@pytest.fixture
def built(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Built]:
    monkeypatch.chdir(tmp_path)
    url = make_repo(tmp_path / "src-repo", files=9)
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_tree(conn, url)
    maintain(
        job(),
        job_context(database, tmp_path),
        encoder_for=fake_encoder,
        client=Talking(None),
        build=fake_build,
    )
    # what condense wrote for one section before #221: the chatter, cached
    with database.write() as conn:
        digest = conn.execute(
            "SELECT content_hash FROM sections WHERE path = 'f4.txt'"
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM condensations WHERE content_hash = ?", (digest,)
        )
        store.upsert(conn, digest, "sonnet", CHATTER, 1, 1)
    yield Built(database, tmp_path)
    database.close()


def test_a_stored_non_condensation_is_redone_and_its_readers_go_stale(
    built: Built,
) -> None:
    client = Talking(None)

    outcome = condense(
        condense_job(), job_context(built.database, built.root), client=client
    )

    with built.database.connect() as conn:
        holder = {
            int(r[0])
            for r in conn.execute(
                "WITH RECURSIVE up(id) AS (SELECT m.node_id FROM node_members "
                "m JOIN sections s ON s.id = m.section_id WHERE s.path = "
                "'f4.txt' UNION SELECT c.parent_id FROM node_children c JOIN "
                "up ON c.child_id = up.id) SELECT id FROM up"
            )
        }
        left = store.unusable(conn, "sonnet")
    stale = {node for node, flag in built.briefs().items() if flag}
    assert client.calls == 1 and outcome["condensed"] == 1
    assert left == ()
    assert stale == holder  # the leaf holding f4 and every topic above it
    assert len(built.briefs()) > len(stale)  # and nothing else


def test_the_stored_non_condensations_are_listed(built: Built) -> None:
    key = Fernet.generate_key()
    conn = open_database(built.root / "hrono.db")
    reconcile(conn, key)
    token = create_user(conn, "rita", "reader")[1]
    conn.commit()
    app = create_app(connection=conn, master_key=key, key_id=1)
    with TestClient(app) as http:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        answer = http.get(
            "/trees/default/unusable-condensations",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
    conn.close()

    assert answer["count"] == 1
    assert answer["condensations"][0]["path"] == "f4.txt"
    assert answer["condensations"][0]["why"] == "talks-to-the-caller"


def test_a_good_condensation_is_never_overwritten(built: Built) -> None:
    # two runs can select the same pending section; the second must not
    # replace what the first stored, nor stale anything for it
    with built.database.write() as conn:
        digest, text = conn.execute(
            "SELECT content_hash, text FROM condensations "
            "WHERE text = ? LIMIT 1",
            (GOOD,),
        ).fetchone()
        store.replace(conn, digest, "sonnet", "something else entirely", 1, 1)
        kept = store.get(conn, digest, "sonnet")["text"]

    assert kept == text
    assert not any(built.briefs().values())
