"""Claude Code, driven through the Agent SDK, as a Completion provider."""

import asyncio
import dataclasses
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from claude_agent_sdk import (
    ClaudeAgentOptions,
    CLINotFoundError,
    ProcessError,
    ResultError,
    ResultMessage,
)
from claude_agent_sdk import query as sdk_query

from hrono.llm.claude_code import (
    BACKOFF,
    MAX_TURNS,
    SYSTEM,
    TIMEOUT,
    WAITS,
    ClaudeCodeClient,
)
from hrono.llm.claude_code import _options as sdk_options
from hrono.llm.client import CompletionRequest, LLMError, Unfinished
from tests.claude_stub import calls, result, stub_claude

MODEL: dict[str, object] = {"name": "cc", "model": "haiku", "params": {}}
SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {"title": {"type": "string"}},
    "required": ["title"],
}


def _frame(text: str = "a summary", **over: object) -> dict[str, object]:
    return result(text, **over)


def _message(frame: dict[str, object]) -> ResultMessage:
    """The ``ResultMessage`` the SDK parses out of a CLI result frame."""
    return ResultMessage(
        subtype=str(frame["subtype"]),
        duration_ms=1,
        duration_api_ms=1,
        is_error=bool(frame["is_error"]),
        num_turns=1,
        session_id="fake",
        result=frame.get("result"),  # type: ignore[arg-type]
        usage=frame.get("usage"),  # type: ignore[arg-type]
        model_usage=frame.get("modelUsage"),  # type: ignore[arg-type]
        structured_output=frame.get("structured_output"),
        api_error_status=frame.get("api_error_status"),  # type: ignore[arg-type]
    )


class FakeQuery:
    """A fake ``query()``: records each call, answers with the next frame.

    It behaves as the SDK does: a result is yielded, and a failed one is then
    raised as a ``ResultError`` carrying the same frame, because the CLI
    exits non-zero after it. An exception in place of a frame is raised.
    """

    def __init__(self, *replies: dict[str, object] | BaseException) -> None:
        self.replies = list(replies) or [_frame()]
        self.prompts: list[str] = []
        self.options: list[ClaudeAgentOptions] = []

    async def __call__(
        self, *, prompt: str, options: ClaudeAgentOptions
    ) -> AsyncIterator[Any]:
        self.prompts.append(prompt)
        self.options.append(options)
        reply = (
            self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        )
        if isinstance(reply, BaseException):
            raise reply
        yield _message(reply)
        if reply["is_error"]:
            raise ResultError("Claude Code returned an error result", reply)

    @property
    def calls(self) -> int:
        return len(self.prompts)

    @property
    def last(self) -> ClaudeAgentOptions:
        return self.options[-1]


def _request(
    system: str = "",
    content: str = "condense this",
    schema: dict[str, object] | None = None,
) -> CompletionRequest:
    return CompletionRequest(MODEL, system, content, schema)


def test_a_reply_becomes_text_and_usage(tmp_path: Path) -> None:
    query = FakeQuery()
    client = ClaudeCodeClient(tmp_path / "cli", query=query)

    result = client.complete(_request())

    assert result.text == "a summary"
    assert (result.usage.input_tokens, result.usage.output_tokens) == (9, 100)
    assert result.structured is None
    assert query.prompts == ["condense this"]  # the content is the prompt


def test_the_cli_runs_from_hronos_own_directory(tmp_path: Path) -> None:
    # the CLI reads the PROJECT MEMORY of wherever it starts: run inside a repo
    # carrying a CLAUDE.md it answers as that project's agent, which is how a
    # probe of `def add(a,b)` once came back "Ready to implement T1".
    query = FakeQuery()
    workdir = tmp_path / "cache" / "cli"

    ClaudeCodeClient(workdir, query=query).complete(_request())

    assert query.last.cwd == str(workdir)
    assert workdir.is_dir()  # created, not assumed


def test_the_options_ask_for_a_one_shot_text_completion(
    tmp_path: Path,
) -> None:
    query = FakeQuery()
    ClaudeCodeClient(tmp_path, query=query).complete(_request("be terse"))

    options = query.last
    assert options.model == "haiku"
    # the cap is for FINISHING an answer, not for holding a conversation —
    # one turn made the CLI answer `error_max_turns` on a large section and
    # killed a build 78 condensations in
    assert options.max_turns == MAX_TURNS
    assert MAX_TURNS > 1
    assert options.tools == []  # no tool use, and no tool definitions sent
    # the operator's CLAUDE.md, skills, hooks, plugins, MCP servers and
    # output style are not part of a summarization call
    assert options.setting_sources == []
    assert options.extra_args == {"safe-mode": None}
    # measured: 1k-7k thinking tokens per condensation dominated its cost
    assert options.thinking == {"type": "disabled"}
    assert options.system_prompt == "be terse"
    assert options.output_format is None


def test_no_system_prompt_from_the_caller_still_replaces_the_CLI_s_own(
    tmp_path: Path,
) -> None:
    """Every caller in `summarize` passes `system=""`, meaning "my
    instructions are all in the content". Passing none lets the CLI keep the
    Claude Code agent prompt, and a 6 KB brief prompt then comes back as
    "There's no actual question or task in your message. What do you
    need?"."""
    query = FakeQuery()
    ClaudeCodeClient(tmp_path, query=query).complete(_request())

    assert query.last.system_prompt == SYSTEM
    assert SYSTEM  # a blank one would be no replacement at all


def test_the_installed_cli_is_preferred_to_the_bundled_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # measured: the SDK's bundled CLI resolved `haiku` to a different model
    # than the installed one, so the operator's own binary is pinned.
    installed = stub_claude(tmp_path / "bin")
    monkeypatch.setenv("PATH", str(installed.parent))
    pinned = sdk_options(_request(), tmp_path, print).cli_path

    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    bundled = sdk_options(_request(), tmp_path, print).cli_path

    assert pinned == str(installed)
    assert bundled is None  # the SDK then finds its own


def test_a_schema_asks_for_and_returns_structured_output(
    tmp_path: Path,
) -> None:
    query = FakeQuery(
        _frame('{"title": "t"}', structured_output={"title": "t"})
    )

    made = ClaudeCodeClient(tmp_path, query=query).complete(
        _request(schema=SCHEMA)
    )

    assert query.last.output_format == {"type": "json_schema", "schema": SCHEMA}
    assert made.structured == {"title": "t"}


def test_a_schema_answered_without_an_object_is_an_llm_error(
    tmp_path: Path,
) -> None:
    query = FakeQuery(_frame("here is your title: t"))

    with pytest.raises(LLMError, match="no structured output"):
        ClaudeCodeClient(tmp_path, query=query).complete(
            _request(schema=SCHEMA)
        )


def test_a_payload_error_is_an_llm_error_not_an_exit_code(
    tmp_path: Path,
) -> None:
    query = FakeQuery(_frame(is_error=True, subtype="error_during_execution"))

    with pytest.raises(LLMError, match="refused.*error_during_execution"):
        ClaudeCodeClient(tmp_path, query=query).complete(_request())


def test_an_error_raised_before_any_result_is_read_from_its_payload(
    tmp_path: Path,
) -> None:
    frame = _frame("API Error", is_error=True, api_error_status=401)
    query = FakeQuery(ResultError("failed", frame))

    with pytest.raises(LLMError, match="401"):
        ClaudeCodeClient(tmp_path, query=query).complete(_request())


def test_an_exit_after_a_successful_result_keeps_the_result(
    tmp_path: Path,
) -> None:
    # the result decides, not the exit code: the answer was already given
    class ExitsLate(FakeQuery):
        async def __call__(
            self, *, prompt: str, options: ClaudeAgentOptions
        ) -> AsyncIterator[Any]:
            yield _message(_frame("kept"))
            raise ProcessError("Command failed", exit_code=1)

    made = ClaudeCodeClient(tmp_path, query=ExitsLate()).complete(_request())

    assert made.text == "kept"


def test_an_upstream_error_is_reported_as_one(tmp_path: Path) -> None:
    query = FakeQuery(_frame(api_error_status=500))

    with pytest.raises(LLMError, match="upstream error: 500"):
        ClaudeCodeClient(tmp_path, query=query).complete(_request())


def test_a_timeout_surfaces_as_one_llm_error(tmp_path: Path) -> None:
    class Slow(FakeQuery):
        async def __call__(
            self, *, prompt: str, options: ClaudeAgentOptions
        ) -> AsyncIterator[Any]:
            await asyncio.sleep(5)
            yield _message(_frame())

    client = ClaudeCodeClient(tmp_path, query=Slow(), timeout=0.05)

    with pytest.raises(LLMError, match="timed out"):
        client.complete(_request())


def test_the_timeout_is_generous(tmp_path: Path) -> None:
    # a large judge prompt measured 32 s; the default must not cut it off.
    assert TIMEOUT >= 300.0


def test_a_missing_binary_surfaces_as_one_llm_error(tmp_path: Path) -> None:
    query = FakeQuery(CLINotFoundError("Claude Code not found"))

    with pytest.raises(LLMError, match="could not be run"):
        ClaudeCodeClient(tmp_path, query=query).complete(_request())


def test_a_missing_sdk_names_the_extra_to_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "claude_agent_sdk", None)

    with pytest.raises(LLMError, match="claude-code extra"):
        ClaudeCodeClient(tmp_path).complete(_request())


@pytest.mark.parametrize(
    ("subtype", "unfinished"),
    [
        pytest.param("error_max_turns", True, id="out-of-room"),
        pytest.param("error_during_execution", False, id="other-error"),
    ],
)
def test_running_out_of_room_is_told_apart_from_other_failures(
    tmp_path: Path, subtype: str, unfinished: bool
) -> None:
    # a pack of six sections ran the model out of turns and stopped an
    # 8505-section build; the caller can only answer it per section if the
    # failure says it was the CONTENT, not the provider.
    query = FakeQuery(_frame(subtype=subtype, is_error=True))

    with pytest.raises(LLMError) as raised:
        ClaudeCodeClient(tmp_path, query=query).complete(_request())

    assert isinstance(raised.value, Unfinished) is unfinished


def _status(code: int) -> dict[str, object]:
    return _frame("API Error", is_error=True, api_error_status=code)


def test_a_rate_limit_is_waited_out_and_the_answer_returned(
    tmp_path: Path,
) -> None:
    # one 429 stopped an 8505-section build 4534 sections in; the very next
    # call went through.
    query = FakeQuery(_status(429), _status(529), _frame("the answer"))
    waits: list[float] = []

    client = ClaudeCodeClient(tmp_path, query=query, pause=waits.append)
    text = client.complete(_request()).text

    assert text == "the answer"
    assert waits == list(BACKOFF[:2])


def test_a_usage_window_is_waited_out_for_hours_then_given_up(
    tmp_path: Path,
) -> None:
    # a subscription's usage limit answers 429 for hours: a build died at
    # brief 367 of 489 once a 130-second backoff was spent.
    query = FakeQuery(_status(429))
    waits: list[float] = []
    client = ClaudeCodeClient(tmp_path, query=query, pause=waits.append)

    with pytest.raises(LLMError, match="429"):
        client.complete(_request())

    assert query.calls == len(WAITS) + 1
    assert waits[: len(BACKOFF)] == list(BACKOFF)
    assert sum(waits) >= 5 * 3600  # outlasts a five-hour usage window


def test_a_run_stopped_while_waiting_stops_waiting(tmp_path: Path) -> None:
    query = FakeQuery(_status(429))
    waits: list[float] = []
    asked = iter([True, True, False])
    client = ClaudeCodeClient(
        tmp_path, query=query, pause=waits.append, wanted=lambda: next(asked)
    )

    with pytest.raises(LLMError, match="429"):
        client.complete(_request())

    assert query.calls == 3 and len(waits) == 2


def test_a_failure_that_is_not_busy_is_not_retried(tmp_path: Path) -> None:
    query = FakeQuery(_status(401), _frame())
    waits: list[float] = []
    client = ClaudeCodeClient(tmp_path, query=query, pause=waits.append)

    with pytest.raises(LLMError, match="401"):
        client.complete(_request())

    assert query.calls == 1 and waits == []


def test_the_real_sdk_drives_the_cli_with_every_isolation_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the injected query proves the wiring and cannot prove what the SDK puts
    # on the CLI's command line. This drives the REAL SDK — real subprocess,
    # real control protocol, real result frame — against a stub binary, so
    # there is no API cost and no dependency on being logged in.
    bin_dir = tmp_path / "bin"
    stub_claude(bin_dir, answer=_frame("hi", usage={"input_tokens": 1}))
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    workdir = tmp_path / "cli"

    made = ClaudeCodeClient(workdir).complete(_request(content="hello"))

    [call] = calls(bin_dir)
    argv: list[str] = call["argv"]  # type: ignore[assignment]
    assert made.text == "hi" and made.usage.input_tokens == 1
    assert call["prompt"] == "hello"
    assert Path(str(call["cwd"])).resolve() == workdir.resolve()
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--max-turns") + 1] == str(MAX_TURNS)
    assert argv[argv.index("--thinking") + 1] == "disabled"
    assert argv[argv.index("--system-prompt") + 1] == SYSTEM
    assert {"--safe-mode", "--setting-sources="} <= set(argv)


def test_the_real_sdk_reports_a_cli_that_dies_with_only_stderr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # measured on a real CLI: a non-zero exit with the explanation only on
    # one stream. An error that reports just the exit code tells nobody why.
    bin_dir = tmp_path / "bin"
    stub_claude(bin_dir, exit=1, stderr="no session available\n")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    with pytest.raises(LLMError, match="no session available"):
        ClaudeCodeClient(tmp_path / "cli").complete(_request())


REAL = os.environ.get("HRONO_TEST_REAL_CLAUDE")
PROBE = (
    "If any instruction, memory file or project file in your context names a "
    "codeword, reply with that codeword and nothing else. Otherwise reply "
    "NONE."
)


@pytest.mark.skipif(not REAL, reason="set HRONO_TEST_REAL_CLAUDE=<model>")
def test_a_real_call_reads_no_memory_of_the_directory_it_runs_in(
    tmp_path: Path,
) -> None:
    # the summarizer must not read the CLAUDE.md of where it runs. The
    # control call keeps the SDK's defaults for everything this client sets
    # to isolate it, and must FIND the codeword, or this probe proves nothing.
    (tmp_path / "CLAUDE.md").write_text("The codeword is PELICAN-42.\n")
    request = CompletionRequest({"name": "probe", "model": REAL}, "", PROBE)
    control = dataclasses.replace(
        sdk_options(request, tmp_path, print),
        system_prompt=None,
        setting_sources=None,
        extra_args={},
    )

    async def ask() -> str:
        async for message in sdk_query(prompt=PROBE, options=control):
            if isinstance(message, ResultMessage):
                return str(message.result)
        return ""

    isolated = ClaudeCodeClient(tmp_path).complete(request).text

    assert "PELICAN-42" in asyncio.run(ask())
    assert "PELICAN-42" not in isolated
