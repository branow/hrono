"""T44.2: the claude-code CLI driven headless as a Completion provider."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from hrono.llm.claude_code import (
    MAX_TURNS,
    SYSTEM,
    TIMEOUT,
    ClaudeCodeClient,
)
from hrono.llm.client import CompletionRequest, LLMError

MODEL: dict[str, object] = {"name": "cc", "model": "haiku", "params": {}}


def _ok(text: str = "a summary", **over: object) -> str:
    payload: dict[str, object] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": text,
        "usage": {"input_tokens": 9, "output_tokens": 100},
        "api_error_status": None,
    }
    payload.update(over)
    return json.dumps(payload)


class Recorder:
    """A fake CLI: records how it was invoked, replies with what it is given."""

    def __init__(self, code: int = 0, out: str = "", err: str = "") -> None:
        self.reply = (code, out or _ok(), err)
        self.argv: list[str] = []
        self.content = ""
        self.cwd: Path | None = None
        self.timeout = 0.0

    def __call__(
        self, argv: list[str], content: str, cwd: Path, timeout: float
    ) -> tuple[int, str, str]:
        self.argv, self.content, self.cwd, self.timeout = (
            argv,
            content,
            cwd,
            timeout,
        )
        return self.reply


def _request(
    system: str = "", content: str = "condense this"
) -> CompletionRequest:
    return CompletionRequest(model=MODEL, system=system, content=content)


def test_a_reply_becomes_text_and_usage(tmp_path: Path) -> None:
    runner = Recorder()
    client = ClaudeCodeClient(tmp_path / "cli", run=runner)

    result = client.complete(_request())

    assert result.text == "a summary"
    assert (result.usage.input_tokens, result.usage.output_tokens) == (9, 100)
    assert runner.content == "condense this"  # the prompt goes on stdin


def test_the_cli_runs_from_hronos_own_directory(tmp_path: Path) -> None:
    # the CLI reads the PROJECT MEMORY of wherever it starts: run inside a repo
    # carrying a CLAUDE.md it answers as that project's agent, which is how a
    # probe of `def add(a,b)` once came back "Ready to implement T1".
    runner = Recorder()
    workdir = tmp_path / "cache" / "cli"
    client = ClaudeCodeClient(workdir, run=runner)

    client.complete(_request())

    assert runner.cwd == workdir
    assert workdir.is_dir()  # created, not assumed


def test_the_argv_is_a_one_shot_text_completion(tmp_path: Path) -> None:
    runner = Recorder()
    ClaudeCodeClient(tmp_path, run=runner).complete(_request(system="be terse"))

    argv = runner.argv
    assert argv[0:2] == ["claude", "-p"]
    assert argv[argv.index("--model") + 1] == "haiku"
    # the cap is for FINISHING an answer, not for holding a conversation —
    # one turn made the CLI answer `error_max_turns` on a large section and
    # killed a build 78 condensations in (#197)
    assert argv[argv.index("--max-turns") + 1] == str(MAX_TURNS)
    assert MAX_TURNS > 1
    assert argv[argv.index("--allowed-tools") + 1] == ""  # no tool use
    # the operator's CLAUDE.md, skills, hooks, plugins and output style are
    # not part of a summarization call (#200)
    assert "--safe-mode" in argv
    assert argv[argv.index("--output-format") + 1] == "json"
    assert argv[argv.index("--system-prompt") + 1] == "be terse"


def test_no_system_prompt_from_the_caller_still_replaces_the_CLI_s_own(
    tmp_path: Path,
) -> None:
    """#200: every caller in `summarize` passes `system=""`, meaning "my
    instructions are all in the content". Passing no flag let the CLI keep the
    Claude Code agent prompt, and a 6 KB brief prompt came back as "There's no
    actual question or task in your message. What do you need?"."""
    runner = Recorder()
    ClaudeCodeClient(tmp_path, run=runner).complete(_request())

    assert runner.argv[runner.argv.index("--system-prompt") + 1] == SYSTEM
    assert SYSTEM  # a blank one would be no replacement at all


def test_a_payload_error_is_an_llm_error_not_an_exit_code(
    tmp_path: Path,
) -> None:
    # exit 0 with is_error set: the JSON decides, not the return code.
    runner = Recorder(out=_ok(is_error=True, subtype="error_during_execution"))

    with pytest.raises(LLMError, match="refused"):
        ClaudeCodeClient(tmp_path, run=runner).complete(_request())


def test_an_upstream_error_is_reported_as_one(tmp_path: Path) -> None:
    runner = Recorder(out=_ok(api_error_status="overloaded_error"))

    with pytest.raises(LLMError, match="overloaded_error"):
        ClaudeCodeClient(tmp_path, run=runner).complete(_request())


def test_a_nonzero_exit_with_empty_stderr_still_explains_itself(
    tmp_path: Path,
) -> None:
    # measured during the QA run: exit 1, nothing on stderr, the explanation on
    # stdout. An error that only reports the exit code tells the user nothing.
    runner = Recorder(code=1, out="cwd was wrong, no session", err="")

    with pytest.raises(LLMError, match="cwd was wrong"):
        ClaudeCodeClient(tmp_path, run=runner).complete(_request())


def test_a_timeout_surfaces_as_one_llm_error(tmp_path: Path) -> None:
    def slow(*_args: object) -> tuple[int, str, str]:
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1.0)

    with pytest.raises(LLMError, match="timed out"):
        ClaudeCodeClient(tmp_path, run=slow).complete(_request())


def test_a_missing_binary_surfaces_as_one_llm_error(tmp_path: Path) -> None:
    def missing(*_args: object) -> tuple[int, str, str]:
        raise FileNotFoundError("claude")

    with pytest.raises(LLMError, match="could not be run"):
        ClaudeCodeClient(tmp_path, run=missing).complete(_request())


def test_the_timeout_is_generous_and_passed_through(tmp_path: Path) -> None:
    # a large judge prompt measured 32 s; the default must not cut it off.
    runner = Recorder()
    ClaudeCodeClient(tmp_path, run=runner).complete(_request())

    assert TIMEOUT >= 300.0
    assert runner.timeout == TIMEOUT


def _stub_cli(tmp_path: Path, body: str) -> Path:
    """A real executable named `claude`, so the REAL subprocess path runs."""
    binary = tmp_path / "bin" / "claude"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_text(body)
    binary.chmod(0o755)
    return binary.parent


def test_the_real_subprocess_path_marshals_argv_stdin_and_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # #108: the injected runner proves the wiring and cannot prove that the
    # subprocess call itself works. This drives the REAL `_subprocess` — real
    # argv, real stdin, real exit code, real JSON — against a stub binary, so
    # there is no API cost and no dependency on being logged in.
    script = (
        "#!/bin/sh\n"
        'stdin="$(cat)"\n'
        'printf \'{"subtype":"success","is_error":false,'
        '"result":"cwd=%s stdin=%s model=%s","usage":{"input_tokens":1,'
        '"output_tokens":2}}\' "$(pwd -P)" "$stdin" "$3"\n'
    )
    monkeypatch.setenv(
        "PATH", f"{_stub_cli(tmp_path, script)}:{os.environ['PATH']}"
    )
    workdir = tmp_path / "cli"
    client = ClaudeCodeClient(workdir)  # no run= : the real subprocess

    result = client.complete(_request(content="hello"))

    # the stub reports what the real call actually handed it
    assert "stdin=hello" in result.text
    assert "model=haiku" in result.text
    assert f"cwd={workdir.resolve()}" in result.text  # hrono's dir, not cwd
    assert (result.usage.input_tokens, result.usage.output_tokens) == (1, 2)


def test_the_real_subprocess_path_reports_a_failing_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = '#!/bin/sh\necho "no session available"\nexit 1\n'
    monkeypatch.setenv(
        "PATH", f"{_stub_cli(tmp_path, script)}:{os.environ['PATH']}"
    )

    with pytest.raises(LLMError, match="no session available"):
        ClaudeCodeClient(tmp_path / "cli").complete(_request())
