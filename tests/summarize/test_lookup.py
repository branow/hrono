"""Lookups while writing a leaf brief, and the relations they leave behind."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs.ops import JobContext
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.llm.tools import SPENT, Toolbox
from hrono.registry import store as registry_store
from hrono.summarize import briefs, lookup, propagate
from hrono.summarize import store as condensations
from hrono.summarize.brief import brief
from tests.context import job_context
from tests.summarize.test_brief import (
    MODEL,
    TEMPLATE,
    TREE,
    job,
    register_brief_prompt,
    register_text_model,
)
from tests.summarize.test_propagate import FakeJudge
from tests.summarize.test_propagate import _job as propagate_job


def _section(conn: object, path: str, body: bytes, i: int) -> int:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    section_id = istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "example.com/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=i,
    )
    condensations.upsert(
        conn,  # type: ignore[arg-type]
        content_hash(body),
        MODEL,
        f"condensation of {path}",
        10,
        3,
    )
    return section_id


def _looking_tree(conn: object, on: bool = True) -> None:
    body = {"name": TREE, "sources": ["repo"], "lookups": on}
    registry_store.insert(conn, "trees", TREE, json.dumps(body), None, "t")  # type: ignore[arg-type]


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_text_model(conn)
        register_brief_prompt(conn)
        judge = {
            "name": "judge",
            "role": "judge",
            "template": "S {source} M {summary}",
        }
        registry_store.insert(
            conn, "prompts", "judge", json.dumps(judge), None, "t"
        )
        s0 = _section(conn, "pay/worker.py", b"publish(FILER_SUBJECT)\n", 0)
        s1 = _section(conn, "filer/worker.py", b"subscribe(FILER_SUBJECT)\n", 1)
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [(0, s0, False, None), (1, s1, False, None)],
            [(s0, [0.1]), (s1, [0.9])],
        )
    yield database
    database.close()


def _files() -> lookup.Files:
    return lookup.Files(
        {
            "source/repo/pay/worker.py": "a\npublish(FILER_SUBJECT)\nb\n",
            "source/repo/filer/worker.py": "subscribe(FILER_SUBJECT)\n",
            "condensed/repo/filer/worker.py.md": "Applies a filing.",
        }
    )


def test_grep_lists_files_or_shows_lines_with_context() -> None:
    files = _files()
    assert files.grep("FILER_SUBJECT", "source/**").splitlines() == [
        "source/repo/filer/worker.py",
        "source/repo/pay/worker.py",
    ]
    shown = files.grep("publish", "source/repo/pay", "content", 1)
    assert "source/repo/pay/worker.py:2: publish(FILER_SUBJECT)" in shown
    assert "source/repo/pay/worker.py:1: a" in shown


def test_a_lookup_that_finds_nothing_says_how_paths_begin() -> None:
    files = _files()
    assert "the sources are: repo" in files.read("source/pay/worker.py")
    assert "the sources are: repo" in files.grep("nowhere")
    assert files.grep("(").startswith("Not a regular expression")


def test_glob_and_read() -> None:
    files = _files()
    assert files.glob("condensed/**") == "condensed/repo/filer/worker.py.md"
    assert files.read("source/repo/pay/worker.py", 1, 1) == (
        "2\tpublish(FILER_SUBJECT)"
    )


def test_a_toolbox_stops_answering_past_its_budget() -> None:
    box = Toolbox(tools=lookup.TOOLS, answer=lambda n, a: "ok", most=1)
    assert box.call("Glob", {"pattern": "*"}) == "ok"
    assert box.call("Glob", {"pattern": "*"}) == SPENT
    assert len(box.calls) == 1


def test_split_keeps_only_declared_files_of_other_topics() -> None:
    text = (
        "The brief.\n\n## Used\n"
        "- condensed/repo/filer/worker.py.md: the filer applies it\n"
        "- source/repo/pay/worker.py: its own file\n"
        "- source/repo/nowhere.py: not in the tree\n"
        "- source/repo/filer/worker.py: the same file again\n"
        "\n## Lookups\n- FILER_SUBJECT: source/repo/filer/worker.py\n"
    )
    known = _files().texts
    body, uses = lookup.split(text, {"repo/pay/worker.py"}, known)
    assert body == "The brief."
    assert uses == (lookup.Use("repo/filer/worker.py", "the filer applies it"),)


class LookingWriter:
    """Looks one file up, then writes a brief that declares it."""

    def __init__(self) -> None:
        self.requests: list[CompletionRequest] = []
        self.answers: list[str] = []

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.requests.append(request)
        assert request.tools is not None
        self.answers.append(
            request.tools.call(
                "Grep", {"pattern": "subscribe", "path": "source/"}
            )
        )
        text = (
            "The topic publishes to FILER_SUBJECT and its consumer applies the "
            "filing.\n\n## Used\n"
            "- source/repo/filer/worker.py: the consumer subscribes\n"
            "- source/repo/pay/worker.py: own file\n"
            "\n## Lookups\n- FILER_SUBJECT: source/repo/filer/worker.py\n"
        )
        return CompletionResult(text, Usage(40, 12))


def _pay_node(db: Database) -> int:
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT m.node_id FROM node_members m JOIN sections s "
                "ON s.id = m.section_id WHERE s.path = 'pay/worker.py'"
            ).fetchone()[0]
        )


def test_a_looking_tree_stores_the_brief_and_its_relations(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        _looking_tree(conn)
    writer = LookingWriter()
    brief(job({"node": _pay_node(db)}), JobContext(db), client=writer)

    asked = writer.requests[0].content
    assert "=== source/repo/pay/worker.py ===" in asked  # the tools' paths
    assert "## Used" in asked
    assert writer.answers == ["source/repo/filer/worker.py"]
    with db.connect() as conn:
        row = briefs.get(conn, _pay_node(db))
        uses = conn.execute(
            "SELECT file, statement FROM brief_uses WHERE node_id = ?",
            (_pay_node(db),),
        ).fetchall()
    assert "## Used" not in row["text"] and "## Lookups" not in row["text"]
    assert [(u["file"], u["statement"]) for u in uses] == [
        ("repo/filer/worker.py", "the consumer subscribes")
    ]
    with db.connect() as conn:
        audit = json.loads(
            conn.execute(
                "SELECT lookups FROM briefs WHERE node_id = ?", (_pay_node(db),)
            ).fetchone()[0]
        )
    assert audit["calls"] == [
        ["Grep", {"pattern": "subscribe", "path": "source/"}]
    ]
    assert audit["account"] == "- FILER_SUBJECT: source/repo/filer/worker.py"


def test_a_brief_written_without_lookups_is_asked_again_to_look(
    db: Database,
) -> None:
    class Hasty(LookingWriter):
        """Writes straight away the first time, as v10's briefs did."""

        def complete(self, request: CompletionRequest) -> CompletionResult:
            if not self.requests:
                self.requests.append(request)
                return CompletionResult(
                    "The topic publishes to FILER_SUBJECT.\n\n## Lookups\n"
                    "- FILER_SUBJECT: not searched\n",
                    Usage(30, 9),
                )
            return super().complete(request)

    with db.connect() as conn, conn:
        _looking_tree(conn)
    writer = Hasty()
    brief(job({"node": _pay_node(db)}), JobContext(db), client=writer)

    assert len(writer.requests) == 2
    assert writer.requests[1].content.endswith(lookup.UNLOOKED)
    with db.connect() as conn:
        row = briefs.get(conn, _pay_node(db))
        uses = conn.execute(
            "SELECT file FROM brief_uses WHERE node_id = ?", (_pay_node(db),)
        ).fetchall()
    assert "consumer applies the filing" in row["text"]
    assert [u["file"] for u in uses] == ["repo/filer/worker.py"]
    assert (row["input_tokens"], row["output_tokens"]) == (70, 21)


def test_a_brief_that_looked_is_not_asked_again(db: Database) -> None:
    with db.connect() as conn, conn:
        _looking_tree(conn)
    writer = LookingWriter()
    brief(job({"node": _pay_node(db)}), JobContext(db), client=writer)
    assert len(writer.requests) == 1


def test_turning_lookups_on_rewrites_the_briefs(db: Database) -> None:
    class Plain:
        def complete(self, request: CompletionRequest) -> CompletionResult:
            assert request.tools is None
            return CompletionResult("A plain brief of this topic.", Usage(1, 1))

    brief(job(), JobContext(db), client=Plain())
    with db.connect() as conn:
        before = briefs.get(conn, _pay_node(db))["prompt_hash"]
    with db.connect() as conn, conn:
        _looking_tree(conn)
    writer = LookingWriter()
    brief(job(), JobContext(db), client=writer)
    assert len(writer.requests) == 2  # both topics are stale again
    with db.connect() as conn:
        assert briefs.get(conn, _pay_node(db))["prompt_hash"] != before
    assert TEMPLATE  # the stored prompt itself is unchanged


def _change_used_file(db: Database) -> None:
    with db.connect() as conn, conn:
        body = b"subscribe(FILER_SUBJECT)\nskip COMPLETED\n"
        digest = content_hash(body)
        istore.upsert_content(conn, digest, body)
        conn.execute(
            "UPDATE sections SET content_hash = ? "
            "WHERE path = 'filer/worker.py'",
            (digest,),
        )
        condensations.upsert(
            conn, digest, MODEL, "Skips COMPLETED filings.", 1, 1
        )


def _with_relation(db: Database) -> int:
    with db.connect() as conn, conn:
        _looking_tree(conn)
    brief(job(), JobContext(db), client=LookingWriter())
    return _pay_node(db)


def test_a_changed_used_file_is_judged_and_a_material_change_rewrites(
    db: Database, tmp_path: Path
) -> None:
    node = _with_relation(db)
    _change_used_file(db)
    judge = FakeJudge("major")
    propagate.propagate(
        propagate_job(), job_context(db, tmp_path), client=judge
    )

    # the file is also the filer topic's own member: that leaf is judged for
    # its own change, and the pay leaf for the file it looked up
    assert judge.calls == 6
    asked = next(r.content for r in judge.requests if "LOOKED-UP" in r.content)
    assert "LOOKED-UP FILES THAT CHANGED" in asked
    assert "Skips COMPLETED filings." in asked
    assert "the consumer subscribes" in asked
    with db.connect() as conn:
        assert briefs.get(conn, node)["stale"] == 1
        assert not lookup.changed_uses(conn, node)  # judged at this version


def test_a_changed_used_file_judged_none_is_not_judged_again(
    db: Database, tmp_path: Path
) -> None:
    node = _with_relation(db)
    _change_used_file(db)
    propagate.propagate(
        propagate_job(), job_context(db, tmp_path), client=FakeJudge("none")
    )
    again = FakeJudge("major")
    propagate.propagate(
        propagate_job(), job_context(db, tmp_path), client=again
    )
    assert again.calls == 0
    with db.connect() as conn:
        assert briefs.get(conn, node)["stale"] == 0


def test_the_tools_virtual_paths_become_repository_paths() -> None:
    text = (
        "See `condensed/repo/filer/config.py.md` and source/repo/README.md.\n"
        "\n## Used\n- source/repo/filer/worker.py: the consumer\n"
    )
    body, uses = lookup.split(text, set(), _files().texts)
    assert body == "See `repo/filer/config.py` and repo/README.md."
    assert uses == (lookup.Use("repo/filer/worker.py", "the consumer"),)
