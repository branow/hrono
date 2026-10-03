"""#217: a reply that is not a brief never stands, and only it is rewritten."""

from collections.abc import Iterator

import pytest

from hrono import pins
from hrono.db.database import Database
from hrono.jobs.ops import JobContext
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.server.triage import survey
from hrono.summarize import briefs
from hrono.summarize.brief import brief
from tests.summarize.test_brief import TREE, db, job  # noqa: F401

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
