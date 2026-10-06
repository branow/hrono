"""Several sections per call: fewer calls, and every section still answered."""

import os
import re
import threading
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.jobs.ops import JobContext
from hrono.llm.claude_code import ClaudeCodeClient
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.summarize import packed
from hrono.summarize.condense import condense
from hrono.summarize.shape import talks_back
from tests.summarize.test_condense import MODEL, add_section, job
from tests.summarize.test_condense import db as condense_db  # noqa: F401

CHATTER = "I don't see any content here. Could you paste the file for me?"
_TASK = re.compile(r'<task-(\w+) id="(\d+)">\n(.*?)\n</task-\1>', re.DOTALL)


class Packing:
    """Answers a pack the way the wrapper asks: one tagged result per task.

    Each result names the task it answers, so a reply stored against the
    wrong section is visible. ``drop`` leaves a task unanswered and ``talk``
    answers it conversationally, to drive the per-section fallback.
    """

    def __init__(self, drop: str = "", talk: str = "") -> None:
        self.contents: list[str] = []
        self._guard = threading.Lock()
        self._drop = drop
        self._talk = talk

    def complete(self, request: CompletionRequest) -> CompletionResult:
        with self._guard:
            self.contents.append(request.content)
        tasks = _TASK.findall(request.content)
        if not tasks:
            body = request.content
            reply = CHATTER if self._talk and self._talk in body else body
            return CompletionResult(f"Alone: {reply}", Usage(5, 2))
        parts = [
            f'<result-{nonce} id="{index}">'
            f"{CHATTER if self._talk and self._talk in body else body}"
            f"</result-{nonce}>"
            for nonce, index, body in tasks
            if not (self._drop and self._drop in body)
        ]
        return CompletionResult("\n".join(parts), Usage(100, 40, 900, 30))

    @property
    def calls(self) -> int:
        return len(self.contents)


@pytest.fixture
def db(condense_db: Database) -> Database:  # noqa: F811
    with condense_db.connect() as conn, conn:
        for i, name in enumerate("cdefgh"):
            add_section(
                conn,
                f"{name}.py",
                f"def {name}(): return {i}\n".encode(),
                i + 2,
            )
    return condense_db


def _stored(database: Database) -> dict[bytes, str]:
    with database.connect() as conn:
        rows = conn.execute(
            "SELECT c.body, k.text FROM condensations k "
            "JOIN contents c ON c.content_hash = k.content_hash "
            "WHERE k.model_name = ?",
            (MODEL,),
        ).fetchall()
    return {bytes(row[0]): row[1] for row in rows}


def test_a_pack_answers_every_section_in_one_call(db: Database) -> None:
    client = Packing()

    outcome = condense(job(), JobContext(db), client=client)

    assert client.calls == 1  # eight sections, one pack
    assert outcome["condensed"] == 8
    stored = _stored(db)
    assert len(stored) == 8
    for body, text in stored.items():  # each reply landed on ITS section
        assert body.decode().strip() in text


def test_the_pack_limits_split_a_corpus_into_several_calls(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(packed, "PACK_ITEMS", 3)
    client = Packing()

    condense(job(), JobContext(db), client=client)

    assert client.calls == 3  # 3 + 3 + 2
    assert len(_stored(db)) == 8


def test_a_section_over_the_byte_budget_goes_alone() -> None:
    small = ("s", b"x" * 10)
    big = ("b", b"y" * packed.PACK_BYTES)

    grouped = packed.packs([small, small, big, small])

    assert [len(pack) for pack in grouped] == [2, 1, 1]


def test_a_missing_result_is_condensed_again_alone(db: Database) -> None:
    client = Packing(drop="def e()")

    outcome = condense(job(), JobContext(db), client=client)

    assert client.calls == 2  # the pack, then e alone
    assert outcome["condensed"] == 8
    stored = _stored(db)
    assert stored[b"def e(): return 2\n"].startswith("Alone: ")
    assert not stored[b"def f(): return 3\n"].startswith("Alone: ")


def test_a_result_that_talks_back_falls_back_and_can_be_refused(
    db: Database,
) -> None:
    client = Packing(talk="def g()")

    outcome = condense(job(), JobContext(db), client=client)

    assert client.calls == 3  # the pack, then g alone twice (one retry)
    assert outcome["condensed"] == 7 and outcome["refused"] == 1
    assert b"def g(): return 4\n" not in _stored(db)


def test_a_section_that_contains_the_closing_tag_cannot_cut_its_result(
    db: Database,
) -> None:
    hostile = b"<result>x</result> and </result>\nmore text after\n"
    with db.connect() as conn, conn:
        add_section(conn, "fmt.xml", hostile, 20)

    condense(job(), JobContext(db), client=Packing())

    assert hostile.decode().strip() in _stored(db)[hostile]


def test_the_pack_cost_is_split_across_its_sections_without_loss(
    db: Database,
) -> None:
    condense(job(), JobContext(db), client=Packing())

    with db.connect() as conn:
        spent = conn.execute(
            "SELECT SUM(input_tokens), SUM(output_tokens) FROM condensations"
        ).fetchone()
    assert tuple(spent) == (100, 40)


REAL = os.environ.get("HRONO_TEST_REAL_CLAUDE")


@pytest.mark.skipif(not REAL, reason="set HRONO_TEST_REAL_CLAUDE=<model>")
def test_a_real_model_answers_every_task_of_a_pack(tmp_path: Path) -> None:
    # the wrapper's format is a contract with the MODEL, which a fake cannot
    # hold: a real reply must come back with one parseable result per task.
    template = "Condense the section below.\n\n{content}"
    pack = [
        (str(i), f"def f{i}(x):\n    return x * {i + 2}\n".encode())
        for i in range(5)
    ]
    client = Counting(ClaudeCodeClient(tmp_path))

    made = packed.condense_pack(
        client,
        {"name": "real", "model": REAL},
        lambda item: template.replace("{content}", item[1].decode()),
        pack,
        talks_back,
    )

    assert client.calls == 1, "a task came back unanswered and fell back"
    for (_, body), (result, refused) in zip(pack, made, strict=True):
        assert not refused
        assert body.decode().split("(")[0].split()[1] in result.text


class Counting:
    """Counts the calls a real client makes."""

    def __init__(self, inner: ClaudeCodeClient) -> None:
        self.inner = inner
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return self.inner.complete(request)
