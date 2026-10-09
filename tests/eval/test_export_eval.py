"""The export evaluation's grading, without an agent (E004).

The runner lives under ``dev/eval/`` because running it costs money; what it
concludes from a transcript is plain code and is pinned here. The agent
sessions themselves are run by hand.
"""

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from hrono.db.database import Database
from tests.export.test_render import _files, db  # noqa: F401 - fixture

_RUNNER = Path(__file__).parents[2] / "dev" / "eval" / "run.py"
_spec = importlib.util.spec_from_file_location("export_eval", _RUNNER)
assert _spec is not None and _spec.loader is not None
run = importlib.util.module_from_spec(_spec)
sys.modules["export_eval"] = run
_spec.loader.exec_module(run)


def test_the_question_set_is_at_least_15_with_no_answer_controls() -> None:
    questions = run.load_questions(_RUNNER.parent / "questions.toml")

    assert len(questions) >= 15
    assert len({q.id for q in questions}) == len(questions)
    assert any(q.kind == "none" for q in questions)
    assert any(q.kind == "deep" for q in questions)
    for q in questions:
        assert bool(q.sources) == (q.kind != "none"), q.id
        assert bool(q.expect) == (q.kind != "none"), q.id


def test_every_settling_file_exists_in_the_repository() -> None:
    root = _RUNNER.parents[2]
    questions = run.load_questions(_RUNNER.parent / "questions.toml")

    missing = [
        (q.id, s)
        for q in questions
        for s in q.sources
        if not (root / s).is_file()
    ]

    assert missing == []


def test_a_real_export_page_names_its_source_and_a_brief_names_none(
    db: tuple[Database, dict[str, int]],  # noqa: F811 - the fixture
) -> None:
    files = _files(db[0])

    sources = {
        path: run.page_source("export", path, text)
        for path, text in files.items()
    }

    assert sorted(s for s in sources.values() if s) == ["a.py", "b.py"]
    assert sources["root.md"] is None
    assert all(
        sources[path] is None for path in files if path.endswith("brief.md")
    )


def test_a_raw_page_is_its_own_source() -> None:
    assert run.page_source("raw", "src/x.py", "# not a header") == "src/x.py"


@pytest.mark.parametrize(
    ("cited", "path"),
    [
        ("src/hrono/a.py", "src/hrono/a.py"),
        ("`src/hrono/a.py`", "src/hrono/a.py"),
        ("./src/hrono/a.py", "src/hrono/a.py"),
        ("src/hrono/a.py:42", "src/hrono/a.py"),
        ("src/hrono/a.py:40-44", "src/hrono/a.py"),
        ("git://hrono/src/hrono/a.py@abc123", "src/hrono/a.py"),
        ("src/hrono/a.py#L3", "src/hrono/a.py"),
    ],
    ids=["plain", "backticks", "dot", "line", "range", "uri", "anchor"],
)
def test_a_cited_source_normalizes_to_its_repository_path(
    cited: str, path: str
) -> None:
    assert run.normalize(cited) == path


def test_the_reply_lines_are_read_even_when_bolded() -> None:
    answer, cited = run.parse_answer(
        "Some reasoning.\n**ANSWER:** It is 40.\nSOURCE: src/a.py\n"
        "SOURCE: `README.md`\n"
    )

    assert answer == "It is 40."
    assert cited == ("src/a.py", "README.md")


def _session(corpus: Path, reads: list[str], reply: str) -> list[dict]:
    """The stream-json events the CLI emits, in the shape it emits them."""
    events: list[dict] = [{"type": "system", "subtype": "init"}]
    events.append(
        {
            "type": "assistant",
            "message": {
                "content": [
                    {
                        "type": "tool_use",
                        "name": "Glob",
                        "input": {"pattern": "*"},
                    }
                ]
            },
        }
    )
    for read in reads:
        events.append(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "looking"},
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"file_path": str(corpus / read)},
                        },
                    ]
                },
            }
        )
    events.append(
        {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": reply,
            "num_turns": len(reads) + 2,
            "total_cost_usd": 0.25,
            "usage": {
                "input_tokens": 10,
                "cache_creation_input_tokens": 100,
                "cache_read_input_tokens": 1000,
                "output_tokens": 50,
            },
        }
    )
    return events


@pytest.fixture
def export(tmp_path: Path) -> Path:
    corpus = tmp_path / "corpus"
    (corpus / "topic-1").mkdir(parents=True)
    (corpus / "root.md").write_text("# Root\n\n- [Topic](topic-1/brief.md)\n")
    (corpus / "topic-1" / "brief.md").write_text("# Topic\n\nBrief.\n")
    (corpus / "topic-1" / "src-a-py-3.md").write_text(
        "# src/a.py\n\n<!-- git://hrono/src/a.py@abc -->\n\nWIDTH = 40\n"
    )
    (corpus / "topic-1" / "src-b-py-4.md").write_text(
        "# src/b.py\n\n<!-- git://hrono/src/b.py@abc -->\n\nHEIGHT = 86\n"
    )
    return corpus


def _question(kind: str = "deep") -> object:
    if kind == "none":
        return run.Question("q9", "none", "Redis port?", (), ())
    return run.Question("q1", kind, "Width?", ("40",), ("src/a.py",))


def test_a_session_is_read_into_pages_tools_tokens_and_cost(
    export: Path,
) -> None:
    arm = run.Arm("levels-2", export, "export")
    events = _session(
        export,
        ["root.md", "topic-1/brief.md", "topic-1/src-a-py-3.md"],
        "ANSWER: 40\nSOURCE: src/a.py",
    )

    session = run.build_run(arm, "q1", events, export, 3.0)

    assert [p.path for p in session.pages] == [
        "root.md",
        "topic-1/brief.md",
        "topic-1/src-a-py-3.md",
    ]
    assert [p.source for p in session.pages] == [None, None, "src/a.py"]
    assert session.tools == ("Glob", "Read", "Read", "Read")
    assert session.tokens == 1160
    assert session.output_tokens == 50
    assert session.cost_usd == 0.25
    assert session.turns == 5
    assert session.error is None


def test_a_read_outside_the_copy_is_not_a_page(export: Path) -> None:
    arm = run.Arm("levels-2", export, "export")
    events = _session(export, ["root.md", "../escape.md"], "ANSWER: x")

    session = run.build_run(arm, "q1", events, export, 1.0)

    assert [p.path for p in session.pages] == ["root.md"]


def test_a_session_that_ran_out_of_turns_is_an_error(export: Path) -> None:
    arm = run.Arm("levels-2", export, "export")
    events = _session(export, [], "")
    events[-1] = {**events[-1], "subtype": "error_max_turns"}

    session = run.build_run(arm, "q1", events, export, 1.0)

    assert session.error == "error_max_turns"


def test_a_right_answer_citing_the_settler_is_correct_and_counts_reads(
    export: Path,
) -> None:
    arm = run.Arm("levels-2", export, "export")
    events = _session(
        export,
        ["root.md", "topic-1/brief.md", "topic-1/src-a-py-3.md"],
        "ANSWER: It is 40.\nSOURCE: git://hrono/src/a.py@abc",
    )

    graded = run.grade(
        _question(), run.build_run(arm, "q1", events, export, 1.0)
    )

    assert graded == run.Grade(True, True, True, 3, 1)


@pytest.mark.parametrize(
    ("reply", "answer_ok", "source_ok"),
    [
        ("ANSWER: It is 30.\nSOURCE: src/a.py", False, True),
        ("ANSWER: It is 40.\nSOURCE: src/b.py", True, False),
        ("ANSWER: It is 40.\nSOURCE: a.py", True, False),
        ("ANSWER: It is 40.", True, False),
    ],
    ids=["wrong-answer", "wrong-file", "bare-name", "no-source"],
)
def test_a_wrong_answer_or_source_is_not_correct(
    export: Path, reply: str, answer_ok: bool, source_ok: bool
) -> None:
    arm = run.Arm("levels-2", export, "export")
    events = _session(export, ["root.md"], reply)

    graded = run.grade(
        _question(), run.build_run(arm, "q1", events, export, 1.0)
    )

    assert (graded.answer_ok, graded.source_ok, graded.correct) == (
        answer_ok,
        source_ok,
        False,
    )
    assert graded.reads_to_answer is None


@pytest.mark.parametrize(
    ("reply", "correct"),
    [
        ("ANSWER: NOT FOUND", True),
        ("ANSWER: not found anywhere", True),
        ("ANSWER: NOT FOUND\nSOURCE: src/a.py", False),
        ("ANSWER: 6379\nSOURCE: src/a.py", False),
    ],
    ids=["refused", "lowercase", "refused-but-cited", "invented"],
)
def test_a_no_answer_control_is_correct_only_when_refused_uncited(
    export: Path, reply: str, correct: bool
) -> None:
    arm = run.Arm("levels-2", export, "export")
    events = _session(export, ["root.md"], reply)

    graded = run.grade(
        _question("none"), run.build_run(arm, "q9", events, export, 1.0)
    )

    assert graded.correct is correct


def test_the_report_totals_and_lists_the_failed_path(export: Path) -> None:
    arm = run.Arm("levels-2", export, "export")
    good = run.build_run(
        arm,
        "q1",
        _session(
            export,
            ["root.md", "topic-1/src-a-py-3.md"],
            "ANSWER: 40\nSOURCE: src/a.py",
        ),
        export,
        2.0,
    )
    bad = run.build_run(
        arm,
        "q9",
        _session(export, ["root.md", "topic-1/brief.md"], "ANSWER: 6379"),
        export,
        4.0,
    )
    isolation = run.Isolation(
        ("--safe-mode",), "NONE", run.CANARY, ("Read",), ()
    )

    report = run.render_report(
        [arm], [_question(), _question("none")], [good, bad], isolation, "m"
    )

    assert "| levels-2 | 1/2 | 1/2 | 2/2 | 2.0 | 2.0 | 1/1 |" in report
    assert "### levels-2 / q9: Redis port?" in report
    assert "  2. `topic-1/brief.md`" in report
    assert "### levels-2 / q1" not in report


def test_reads_to_the_settler_skip_a_section_that_does_not_settle(
    export: Path,
) -> None:
    arm = run.Arm("levels-2", export, "export")
    events = _session(
        export,
        ["root.md", "topic-1/src-b-py-4.md", "topic-1/src-a-py-3.md"],
        "ANSWER: 40\nSOURCE: src/a.py",
    )

    graded = run.grade(
        _question(), run.build_run(arm, "q1", events, export, 1.0)
    )

    assert graded.reads_to_answer == 3


def test_a_rerender_grades_recorded_sessions_without_an_agent(
    export: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    twin = tmp_path / "twin"
    shutil.copytree(export, twin)
    other = tmp_path / "other"
    shutil.copytree(export, other)
    (other / "root.md").write_text("# Root\n\nShallower.\n")
    arms = [
        run.Arm("a", export, "export"),
        run.Arm("b", twin, "export"),
        run.Arm("c", other, "export"),
    ]
    reply = "ANSWER: 40\nSOURCE: src/a.py"
    reads = ["root.md", "topic-1/brief.md", "topic-1/src-a-py-3.md"]
    sessions = [
        run.build_run(arm, "q01", _session(export, reads, reply), export, 1.0)
        for arm in arms
    ]
    (out / "runs.jsonl").write_text(
        "".join(json.dumps(asdict(s)) + "\n" for s in sessions)
    )
    isolation = run.Isolation(
        ("--safe-mode",), "NONE", run.CANARY, (), (), verified=True
    )
    (out / "isolation.json").write_text(json.dumps(asdict(isolation)))
    questions = tmp_path / "questions.toml"
    questions.write_text(
        '[[question]]\nid = "q01"\nkind = "deep"\nquestion = "Width?"\n'
        'expect = ["40"]\nsources = ["src/a.py"]\n'
    )

    code = run.main(
        [
            "--out",
            str(out),
            "--arm",
            f"a={export}",
            "--arm",
            f"b={twin}",
            "--arm",
            f"c={other}",
            "--questions",
            str(questions),
            "--rerender",
        ]
    )

    report = (out / "report.md").read_text()
    assert code == 0
    assert "| a | 1/1 | 1/1 | 1/1 | 3.0 | 3.0 | 1/1 |" in report
    assert "a and b are byte-identical folders" in report
    assert report.count("byte-identical") == 1
    assert "- q01: root.md > 1/brief.md > 1/src-a-py-3.md" in report
    assert "## Isolation: verified" in report


def test_folders_that_differ_by_one_byte_are_not_twins(export: Path) -> None:
    before = run.fingerprint(export)
    (export / "topic-1" / "brief.md").write_text("# Topic\n\nBrief!\n")

    assert run.fingerprint(export) != before


@pytest.mark.parametrize(
    ("cited", "correct"),
    [
        ("topic-1/src-a-py-3.md", True),
        ("/tmp/hrono-eval-x/corpus/topic-1/src-a-py-3.md", True),
        ("topic-1/src-b-py-4.md", False),
        ("root.md", False),
    ],
    ids=["page", "absolute-page", "other-page", "brief"],
)
def test_an_export_page_cited_counts_as_the_file_it_carries(
    export: Path, cited: str, correct: bool
) -> None:
    arm = run.Arm("levels-2", export, "export")
    session = run.build_run(
        arm,
        "q1",
        _session(export, ["root.md"], f"ANSWER: 40\nSOURCE: {cited}"),
        export,
        1.0,
    )
    isolation = run.Isolation((), "", "", (), (), verified=True)

    report = run.render_report([arm], [_question()], [session], isolation, "m")

    assert ("| levels-2 | 1/1 |" in report) is correct


@pytest.mark.parametrize(
    ("control", "isolated", "mark", "verified"),
    [
        (f"{run.CANARY}, graphify", "NONE", "graphify", True),
        (f"{run.CANARY}", "NONE", "", True),
        ("NONE", "NONE", "", False),
        (f"{run.CANARY}", "NONE", "graphify", False),
        (f"{run.CANARY}, graphify", f"I see {run.CANARY}", "graphify", False),
        (f"{run.CANARY}, graphify", "the GraphiFy skill", "graphify", False),
        (f"{run.CANARY}", 'userEmail: "a@b.io"', "", False),
        (f"{run.CANARY}", "my user is someone@example.com", "", False),
        (f"{run.CANARY}", "I know of a userEmail entry", "", False),
    ],
    ids=[
        "both-seen-none-leaked",
        "no-mark-canary-only",
        "control-misses-canary",
        "control-misses-mark",
        "isolated-quotes-canary",
        "isolated-quotes-mark",
        "isolated-quotes-user-email-entry",
        "isolated-quotes-an-address",
        "isolated-names-the-user-context-key",
    ],
)
def test_isolation_is_verified_only_when_the_control_sees_and_nothing_leaks(
    control: str, isolated: str, mark: str, verified: bool
) -> None:
    assert run.isolation_verdict(control, isolated, mark) is verified


def test_the_isolation_check_asks_both_sessions_and_reports_the_mark() -> None:
    asked: list[tuple[str, ...]] = []

    def probe(prompt: str, model: str, flags: tuple[str, ...]) -> tuple:
        asked.append(tuple(flags))
        if flags:
            return "NONE", [
                {"subtype": "init", "tools": ["Read"], "mcp_servers": []}
            ]
        return f"{run.CANARY} and zebra", []

    isolation = run.check_isolation("haiku", "zebra", probe=probe)

    assert asked == [run.ISOLATION, ()]
    assert isolation.verified
    assert isolation.tools == ("Read",)
    report = run.render_isolation(isolation)
    assert "~/.claude/CLAUDE.md carries `zebra`" in report
    assert "NOT tested" not in report


def test_a_report_without_an_operator_mark_says_user_memory_was_untested() -> (
    None
):
    isolation = run.Isolation(
        ("--safe-mode",), "NONE", run.CANARY, (), (), verified=True
    )

    report = run.render_isolation(isolation)

    assert "## Isolation: verified" in report
    assert "user memory was NOT tested" in report


def _fake_claude(sessions: dict[str, object]):
    """subprocess.run as the CLI behaves, keyed by the question asked."""

    def fake(argv: list[str], *, input: str, **kwargs: object) -> object:
        outcome = sessions[input]
        if isinstance(outcome, BaseException):
            raise outcome
        return subprocess.CompletedProcess(argv, 0, outcome, "")

    return fake


def _stream(events: list[dict]) -> str:
    return "".join(json.dumps(e) + "\n" for e in events)


def test_a_timed_out_or_garbled_session_is_an_error_and_the_rest_are_kept(
    export: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = _stream(_session(export, ["root.md"], "ANSWER: 40\nSOURCE: a"))
    garbled = good.replace('{"type": "result"', '{"type": "resu', 1)
    partial = _stream(_session(export, ["root.md"], "x")[:2])
    monkeypatch.setattr(
        run.subprocess,
        "run",
        _fake_claude(
            {
                "ok?": good,
                "garbled?": garbled,
                "slow?": subprocess.TimeoutExpired("claude", 900, partial),
            }
        ),
    )
    questions = [
        run.Question(q, "deep", f"{q}?", ("40",), ("src/a.py",))
        for q in ("ok", "garbled", "slow")
    ]
    args = argparse.Namespace(
        jobs=2, model="haiku", max_turns=5, out=tmp_path, tools=run.TOOLS
    )

    run._ask_all([run.Arm("a", export, "export")], questions, args)

    recorded = {r.question: r for r in run.load_runs(tmp_path / "runs.jsonl")}
    assert recorded["ok"].error is None
    assert recorded["ok"].answer == "40"
    assert recorded["garbled"].error == "1 malformed stream-json line(s)"
    assert recorded["slow"].error == "timed out after 900s"
    assert recorded["slow"].tools == ("Glob",)
    assert (tmp_path / "transcripts" / "a" / "slow.jsonl").read_text()


def test_a_session_that_raises_is_an_error_and_the_rest_are_kept(
    export: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    good = _stream(_session(export, ["root.md"], "ANSWER: 40\nSOURCE: a"))
    monkeypatch.setattr(
        run.subprocess,
        "run",
        _fake_claude(
            {
                "first?": good,
                "second?": RuntimeError("boom"),
                "third?": good,
            }
        ),
    )
    questions = [
        run.Question(q, "deep", f"{q}?", ("40",), ("src/a.py",))
        for q in ("first", "second", "third")
    ]
    args = argparse.Namespace(
        jobs=1, model="haiku", max_turns=5, out=tmp_path, tools=run.TOOLS
    )

    returned = run._ask_all([run.Arm("a", export, "export")], questions, args)

    recorded = {r.question: r for r in run.load_runs(tmp_path / "runs.jsonl")}
    assert set(recorded) == {"first", "second", "third"}
    assert len(returned) == 3
    assert recorded["second"].error == "RuntimeError: boom"
    assert recorded["second"].arm == "a"
    assert recorded["first"].error is None
    assert recorded["third"].error is None
    assert recorded["third"].answer == "40"


def test_a_rerender_of_a_subset_reports_only_the_arms_and_questions_named(
    export: Path, tmp_path: Path
) -> None:
    out = tmp_path / "out"
    out.mkdir()
    reply = "ANSWER: 40\nSOURCE: src/a.py"
    events = _session(export, ["root.md"], reply)
    sessions = [
        run.build_run(run.Arm(arm, export, "export"), q, events, export, 1.0)
        for arm in ("a", "b")
        for q in ("q01", "q02")
    ]
    (out / "runs.jsonl").write_text(
        "".join(json.dumps(asdict(s)) + "\n" for s in sessions)
    )
    isolation = run.Isolation(
        ("--safe-mode",), "NONE", run.CANARY, (), (), verified=True
    )
    (out / "isolation.json").write_text(json.dumps(asdict(isolation)))
    questions = tmp_path / "questions.toml"
    questions.write_text(
        "".join(
            f'[[question]]\nid = "{q}"\nkind = "deep"\nquestion = "W?"\n'
            'expect = ["40"]\nsources = ["src/a.py"]\n'
            for q in ("q01", "q02")
        )
    )
    argv = ["--out", str(out), "--questions", str(questions), "--rerender"]

    code = run.main([*argv, "--arm", f"a={export}", "--only", "q01"])

    report = (out / "report.md").read_text()
    assert code == 0
    assert "| a | 1/1 |" in report
    assert "### b " not in report
    assert "q02" not in report
    with pytest.raises(SystemExit, match="no recorded session for c/q01"):
        run.main([*argv, "--arm", f"c={export}", "--only", "q01"])


def test_only_names_a_question_that_does_not_exist(
    export: Path, tmp_path: Path
) -> None:
    questions = tmp_path / "questions.toml"
    questions.write_text(
        '[[question]]\nid = "q01"\nkind = "deep"\nquestion = "W?"\n'
        'expect = ["40"]\nsources = ["src/a.py"]\n'
    )
    argv = [
        "--out",
        str(tmp_path / "out"),
        "--questions",
        str(questions),
        "--arm",
        f"a={export}",
    ]

    with pytest.raises(SystemExit, match="no such question q09, q10"):
        run.main([*argv, "--only", "q01,q10,q09"])
    assert not (tmp_path / "out").exists()


def test_a_report_redacts_an_email_a_reply_quoted(export: Path) -> None:
    arm = run.Arm("levels-2", export, "export")
    session = run.build_run(
        arm,
        "q1",
        _session(export, ["root.md"], "ANSWER: mail me at me@example.com"),
        export,
        1.0,
    )
    isolation = run.Isolation(
        (), 'userEmail: "orest@example.com"', run.CANARY, (), (), False
    )

    report = run.render_report([arm], [_question()], [session], isolation, "m")

    assert "@" not in report.replace("@@", "")
    assert report.count(run.REDACTED) >= 2


def test_a_failed_probe_quoting_an_address_reaches_neither_file_nor_stderr(
    export: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def probe(prompt: str, model: str, flags: tuple[str, ...]) -> tuple:
        return 'userEmail: "orest@example.com"', []

    out = tmp_path / "out"

    code = run.main(["--out", str(out), "--arm", f"a={export}"], probe)

    assert code == 2
    assert "orest@example.com" not in (out / "isolation.json").read_text()
    err = capsys.readouterr().err
    assert "orest@example.com" not in err
    assert run.REDACTED in err
