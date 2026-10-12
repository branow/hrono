"""The Demo page: an agent's turn over the tree, step by step."""

import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from hrono.db.database import Database
from hrono.demo import session
from hrono.demo.agents import mcp
from hrono.demo.agents.claude_code import ClaudeCode
from hrono.demo.agents.loop import Looped, Reply, Use
from hrono.demo.steps import Steps
from hrono.demo.tools import Library
from hrono.export import saved
from hrono.llm.client import Usage
from hrono.recall.engine import Recall
from hrono.registry import store
from tests.server.test_ui_export import TREE, Panel, panel  # noqa: F401


def _library(panel: Panel) -> tuple[Library, Steps]:  # noqa: F811
    panel.export()
    export = saved.load(panel.conn, TREE)  # type: ignore[arg-type]
    assert export is not None
    steps = Steps()
    return Library(Database.adopt(panel.conn), TREE, export, steps), steps  # type: ignore[arg-type]


def _link(library: Library) -> str:
    """A child link as the root page writes it."""
    root = library.call("open_topic", {"page": "root.md"})
    return root.split("](")[1].split(")")[0]


def test_the_tools_open_pages_and_files_and_say_where(panel: Panel) -> None:  # noqa: F811
    library, steps = _library(panel)

    root = library.call("open_topic", {"page": "root.md"})
    leaf = library.call("open_topic", {"page": "./" + _link(library)})
    code = library.call(
        "open_source", {"source": "repo @ v1", "path": "alpha.py"}
    )
    lost = library.call("open_topic", {"page": "nowhere.md"})

    assert "## Children" in root
    assert "## Sources" in leaf
    assert code == "alpha body\n"
    assert lost.startswith("No page nowhere.md")
    shown = [step.data for step in steps.since(0)]
    assert [s["tool"] for s in shown][:3] == [
        "open_topic",
        "open_topic",
        "open_topic",
    ]
    assert all(isinstance(s["node"], int) for s in shown[:4])
    assert shown[-1]["node"] is None


def test_the_tools_answer_over_mcp(panel: Panel) -> None:  # noqa: F811
    library, _ = _library(panel)

    def say(method: str, **params: object) -> dict[str, object]:
        reply = mcp.answer(
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            library,
        )
        assert reply is not None
        return reply

    assert (
        say("initialize", protocolVersion="2025-11-25")["result"][
            "protocolVersion"
        ]
        == "2025-11-25"
    )
    listed = say("tools/list")["result"]["tools"]  # type: ignore[index]
    assert [tool["name"] for tool in listed] == ["open_topic", "open_source"]
    called = say("tools/call", name="open_topic", arguments={"page": "root.md"})
    assert "## Children" in called["result"]["content"][0]["text"]  # type: ignore[index]
    assert "error" in say("resources/list")
    assert mcp.answer({"method": "notifications/initialized"}, library) is None


class Scripted:
    """A model that opens the root, then answers."""

    def __init__(self) -> None:
        self.seen: list[list[dict[str, object]]] = []

    def user(self, text: str) -> dict[str, object]:
        return {"role": "user", "content": text}

    def results(self, done: list[tuple[Use, str]]) -> list[dict[str, object]]:
        return [{"role": "tool", "content": text} for _, text in done]

    def ask(self, history: list[dict[str, object]]) -> Reply:
        self.seen.append(list(history))
        usage = Usage(input_tokens=10, output_tokens=2)
        if len(self.seen) == 1:
            use = Use("1", "open_topic", {"page": "root.md"})
            return Reply(
                "Reading the map.", (use,), usage, {"role": "assistant"}
            )
        return Reply("It signs tokens.", (), usage, {"role": "assistant"})


def test_the_loop_runs_tools_until_the_model_answers(panel: Panel) -> None:  # noqa: F811
    library, steps = _library(panel)
    calls = []
    chat = Scripted()
    agent = Looped(chat, library, steps, calls.append, "brief", "anthropic")

    agent.turn("How are tokens signed?")

    assert [s.kind for s in steps.since(0)] == ["say", "tool", "answer"]
    assert chat.seen[1][-1]["role"] == "tool"  # the page went back to it
    assert [(c.role, c.ok) for c in calls] == [("demo", True), ("demo", True)]


def test_the_cli_turn_reads_the_stream_and_resumes(panel: Panel) -> None:  # noqa: F811
    steps, calls, commands = Steps(), [], []
    lines = [
        {"type": "system", "subtype": "init", "session_id": "s-1"},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "Opening the root."},
                    {"type": "tool_use", "name": "mcp__hrono__open_topic"},
                ]
            },
        },
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "x"}]},
        },
        {
            "type": "result",
            "subtype": "success",
            "result": "It signs tokens.",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        },
    ]

    def run(command: list[str], workdir: Path, prompt: str) -> list[str]:
        commands.append(command)
        return [json.dumps(line) for line in lines]

    agent = ClaudeCode(
        "sonnet",
        "system",
        "http://x/demo/c/mcp",
        Path("/w"),
        steps,
        calls.append,
        run=run,
    )
    agent.turn("q1")
    agent.turn("q2")

    assert [s.kind for s in steps.since(0)] == ["say", "answer"] * 2
    assert "--resume" not in commands[0]
    assert commands[1][-2:] == ["--resume", "s-1"]
    assert calls[0].input_tokens == 5 and calls[0].provider == "claude-code"


@pytest.fixture
def demo(panel: Panel, monkeypatch: pytest.MonkeyPatch) -> Panel:  # noqa: F811
    """The panel with a model on a connection, and no embedding model."""
    store.insert(
        panel.conn,  # type: ignore[arg-type]
        "connections",
        "claude",
        json.dumps(
            {
                "name": "claude",
                "provider": "claude-code",
                "auth": {"method": "none"},
            }
        ),
        None,
        "now",
    )
    store.insert(
        panel.conn,  # type: ignore[arg-type]
        "models",
        "brief",
        json.dumps(
            {
                "name": "brief",
                "kind": "text",
                "connection": "claude",
                "model": "sonnet",
            }
        ),
        None,
        "now",
    )
    panel.conn.commit()  # type: ignore[attr-defined]
    monkeypatch.setattr(
        session, "ask", lambda *a: Recall(hits=(), message="nothing confident")
    )
    return panel


def test_the_page_says_it_is_a_demonstration_and_asks_for_an_export(
    demo: Panel,
) -> None:
    demo.sign_in("reader")

    before = demo.client.get(f"/ui/trees/{TREE}/demo?tree={TREE}").text
    demo.export()
    after = demo.client.get(f"/ui/trees/{TREE}/demo?tree={TREE}").text

    assert "A demonstration, not the real setup" in before
    assert "Export this tree first" in before
    assert 'id="connection"' in after and "claude (claude-code)" in after
    assert '"connection": "claude"' in after


def test_a_turn_streams_its_steps_and_its_tools_answer_the_cli(
    demo: Panel, monkeypatch: pytest.MonkeyPatch
) -> None:
    demo.export()
    demo.sign_in("writer")
    urls: list[str] = []

    def fake(self: ClaudeCode, prompt: str) -> None:
        urls.append(self.url)
        self.steps.add("answer", text="**done**")

    monkeypatch.setattr(ClaudeCode, "turn", fake)

    started = demo.client.post(
        f"/ui/trees/{TREE}/demo/ask",
        data={"question": "How are tokens signed?", "model": "brief"},
    ).json()
    talk = started["conversation"]
    body = demo.client.get(
        f"/ui/trees/{TREE}/demo/{talk}/steps?after={started['after']}"
    ).text
    tools = demo.client.post(
        urlsplit(urls[0]).path,
        json={"jsonrpc": "2.0", "id": 7, "method": "tools/list"},
    )

    kinds = [
        json.loads(line[6:])["kind"]
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
    assert kinds == ["asked", "recall", "prompt", "answer", "done"]
    assert "<strong>done</strong>" in body
    assert urls[0].endswith(f"/demo/{talk}/mcp")
    assert tools.json()["id"] == 7
    assert demo.client.post("/demo/nobody/mcp", json={}).status_code == 404


def test_a_reader_cannot_start_a_turn(demo: Panel) -> None:
    demo.export()
    demo.sign_in("reader")

    reply = demo.client.post(
        f"/ui/trees/{TREE}/demo/ask",
        data={"question": "q", "model": "brief"},
        follow_redirects=False,
    )

    assert reply.status_code in (303, 403)
