"""#217: a reply that is not a brief never stands, and only it is rewritten."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono import pins
from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.jobs.ops import JobContext
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.server.triage import survey
from hrono.summarize import briefs
from hrono.summarize.brief import brief
from hrono.tree.maintain import maintain
from tests.context import job_context
from tests.summarize.test_brief import TREE, db, job  # noqa: F401
from tests.summarize.test_shape import ECHOED, _default
from tests.tree.test_maintain import (
    FakeCompletion,
    fake_build,
    fake_encoder,
    make_repo,
)
from tests.tree.test_maintain import job as maintain_job
from tests.tree.test_maintain import register as register_tree

GOOD = "This topic groups the parsers that read the configuration files."
CHATTER = (
    "There's no task here — your message is just system context, no actual "
    "child briefs to condense. Paste the briefs and I'll merge them."
)


class Answering:
    """Talks back for one node's content until told to behave."""

    def __init__(self, refuse: str | None) -> None:
        self.refuse = refuse
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        if self.refuse is not None and self.refuse in request.content:
            return CompletionResult(CHATTER, Usage(5, 5))
        return CompletionResult(GOOD, Usage(5, 5))


def _rows(database: Database) -> dict[int, tuple[str, str, str]]:
    with database.connect() as conn:
        return {
            int(r["node_id"]): (r["text"], r["flagged"], r["created_at"])
            for r in conn.execute(
                "SELECT node_id, text, flagged, created_at FROM briefs"
            ).fetchall()
        }


def _briefless(database: Database) -> int:
    with database.connect() as conn:
        items = {item.kind: item.count for item in survey(conn, TREE)}
    return items["topics with no usable brief, or a stale one"]


@pytest.fixture
def written(db: Database) -> Iterator[Database]:  # noqa: F811
    # the condensation of a.py makes the model talk back, the other is fine
    brief(job(), JobContext(db), client=Answering("condensation of a.py"))
    yield db


def test_a_reply_that_talks_back_is_stored_flagged_and_counted(
    written: Database,
) -> None:
    rows = _rows(written)

    flags = sorted(flag for _, flag, _ in rows.values())
    assert flags == ["", "talks-to-the-caller"]
    assert _briefless(written) == 1


def test_the_next_run_rewrites_only_the_reply_that_was_not_a_brief(
    written: Database,
) -> None:
    before = _rows(written)
    behaving = Answering(None)

    outcome = brief(job(), JobContext(written), client=behaving)

    after = _rows(written)
    rewritten = [n for n in after if after[n] != before[n]]
    assert behaving.calls == 1
    assert outcome["briefed"] == 1
    assert len(rewritten) == 1 and after[rewritten[0]][:2] == (GOOD, "")
    assert _briefless(written) == 0


def test_a_brief_stored_before_the_rule_is_caught_by_it(
    written: Database,
) -> None:
    # what the gate wrote before #217: the chatter, with no flag beside it
    with written.write() as conn:
        good = next(n for n, (_, flag, _) in _rows(written).items() if not flag)
        row = briefs.get(conn, good)
        briefs.upsert(
            conn,
            good,
            CHATTER,
            model_name=row["model_name"],
            prompt_name=row["prompt_name"],
            prompt_hash=row["prompt_hash"],
            member_signature=row["member_signature"],
            input_tokens=1,
            output_tokens=1,
            model_fingerprint=row["model_fingerprint"],
        )
        found = briefs.unusable(briefs.get(conn, good))

    assert found == "talks-to-the-caller"
    assert _briefless(written) == 2


def test_a_pinned_brief_is_a_persons_and_is_not_counted(
    written: Database,
) -> None:
    flagged = next(n for n, (_, flag, _) in _rows(written).items() if flag)
    with written.write() as conn:
        pins.pin(conn, pins.BRIEF, flagged, "kept as written")

    assert _briefless(written) == 0


def test_the_stored_non_briefs_are_listed(written: Database) -> None:
    with written.connect() as conn:
        found = briefs.unusable_in(conn, TREE)

    assert [(why, text) for _, _, why, text in found] == [
        ("talks-to-the-caller", CHATTER)
    ]


def _default_prompts(conn: object) -> None:
    """The seeded brief prompts, the ones ~/hrono-demo's echo repeated."""
    for name in ECHOED:
        registry_store.replace(
            conn,  # type: ignore[arg-type]
            "prompts",
            name,
            json.dumps(
                {"name": name, "role": name, "template": _default(name)}
            ),
            None,
            "t",
        )


class Echoing:
    """Answers every brief with the demo tree's echo of its prompt."""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return CompletionResult(ECHOED["brief"], Usage(5, 5))


def test_an_echo_of_the_prompt_is_retried_and_stored_flagged(
    db: Database,  # noqa: F811
) -> None:
    with db.connect() as conn, conn:
        _default_prompts(conn)
    client = Echoing()

    brief(job(), JobContext(db), client=client)

    flags = sorted(flag for _, flag, _ in _rows(db).values())
    assert client.calls == 4  # two topics, each retried once
    assert flags == ["echoes-the-prompt", "echoes-the-prompt"]
    assert _briefless(db) == 2


@pytest.fixture
def echoed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A built tree holding one level-0 brief that is ~/hrono-demo's echo,
    stored with no flag, as it was there."""
    monkeypatch.chdir(tmp_path)
    url = make_repo(tmp_path / "src-repo", files=9)
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_tree(conn, url)
        _default_prompts(conn)
    maintain(
        maintain_job(),
        job_context(database, tmp_path),
        encoder_for=fake_encoder,
        client=FakeCompletion(),
        build=fake_build,
    )
    with database.write() as conn:
        node = conn.execute(
            "SELECT b.node_id FROM briefs b JOIN nodes n ON n.id = b.node_id "
            "WHERE n.level = 0 ORDER BY b.node_id LIMIT 1"
        ).fetchone()[0]
        row = briefs.get(conn, node)
        briefs.upsert(
            conn,
            node,
            ECHOED["brief"],
            model_name=row["model_name"],
            prompt_name=row["prompt_name"],
            prompt_hash=row["prompt_hash"],
            member_signature=row["member_signature"],
            input_tokens=1,
            output_tokens=1,
            model_fingerprint=row["model_fingerprint"],
            members=row["members"],
        )
    database.close()
    yield tmp_path


KEY = Fernet.generate_key()


def _listed(root: Path, reader: str) -> dict[str, object]:
    conn = open_database(root / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, reader, "reader")[1]
    conn.commit()
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as http:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        listed = http.get(
            f"/trees/{TREE}/unusable-briefs",
            headers={"Authorization": f"Bearer {token}"},
        ).json()
    conn.close()
    return listed


def test_a_stored_echo_is_listed_and_rewritten_by_the_next_maintain(
    echoed: Path,
) -> None:
    before = _listed(echoed, "rita")
    database = Database.at(echoed / "hrono.db")
    client = FakeCompletion()

    maintain(
        maintain_job(),
        job_context(database, echoed),
        encoder_for=fake_encoder,
        client=client,
        build=fake_build,
    )

    with database.connect() as conn:
        left = [text for (text,) in conn.execute("SELECT text FROM briefs")]
    database.close()
    assert [(b["level"], b["why"]) for b in before["briefs"]] == [
        (0, "echoes-the-prompt")
    ]
    assert ECHOED["brief"] not in left
    assert _listed(echoed, "rob")["count"] == 0
    assert client.calls == 1  # that brief alone: everything else held
