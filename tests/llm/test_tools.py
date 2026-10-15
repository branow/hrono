"""Every provider runs the same call-answer loop over a toolbox."""

import json
from pathlib import Path
from types import SimpleNamespace

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.llm.claude_code import _options as sdk_options
from hrono.llm.client import AnthropicClient, CompletionRequest
from hrono.llm.openai import OpenAIClient
from hrono.llm.tools import SPENT, Tool, Toolbox
from tests.llm.test_client import (  # noqa: F401 - pytest fixtures
    ciph,
    db,
    register_connection,
    text_model,
)

READ = Tool(
    "Read",
    "Read a file.",
    {"type": "object", "properties": {"path": {"type": "string"}}},
)


def _toolbox(most: int = 15) -> Toolbox:
    return Toolbox(
        tools=(READ,),
        answer=lambda name, args: f"contents of {args['path']}",
        most=most,
    )


def _reply(blocks: list[object], tokens: int = 10) -> object:
    return SimpleNamespace(
        content=blocks,
        usage=SimpleNamespace(input_tokens=tokens, output_tokens=2),
    )


def test_anthropic_answers_each_call_then_returns_the_text(
    db: Database,  # noqa: F811
    ciph: Cipher,  # noqa: F811
) -> None:
    with db.connect() as conn:
        register_connection(conn, ciph)
    sent: list[list[dict[str, object]]] = []
    replies = [
        _reply(
            [
                SimpleNamespace(type="thinking", thinking="hm", signature="s1"),
                SimpleNamespace(type="text", text="Looking."),
                SimpleNamespace(
                    type="tool_use", id="t1", name="Read", input={"path": "a"}
                ),
            ]
        ),
        _reply([SimpleNamespace(type="text", text="The brief.")], tokens=30),
    ]

    def invoke(**kwargs: object) -> object:
        sent.append(json.loads(json.dumps(kwargs["messages"])))
        assert kwargs["tools"][0]["name"] == "Read"  # type: ignore[index]
        assert kwargs["thinking"]["type"] == "enabled"  # type: ignore[index]
        return replies[len(sent) - 1]

    box = _toolbox()
    result = AnthropicClient(db, ciph, invoke=invoke).complete(
        CompletionRequest(text_model(), "", "write it", tools=box)
    )
    assert result.text == "The brief."
    assert result.usage.input_tokens == 40  # both turns count
    assert box.calls == [("Read", {"path": "a"})]
    carried = sent[1][-2]["content"][0]  # type: ignore[index]
    assert carried == {"type": "thinking", "thinking": "hm", "signature": "s1"}
    answered = sent[1][-1]["content"][0]  # type: ignore[index]
    assert answered == {
        "type": "tool_result",
        "tool_use_id": "t1",
        "content": "contents of a",
    }


def test_openai_answers_each_call_then_returns_the_text(
    db: Database,  # noqa: F811
    ciph: Cipher,  # noqa: F811
) -> None:
    with db.connect() as conn:
        register_connection(conn, ciph)
    bodies: list[dict[str, object]] = []
    call = {
        "id": "c1",
        "type": "function",
        "function": {"name": "Read", "arguments": '{"path": "b"}'},
    }
    replies = [
        {
            "choices": [
                {"message": {"role": "assistant", "tool_calls": [call]}}
            ],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1},
        },
        {
            "choices": [{"message": {"role": "assistant", "content": "Done."}}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 3},
        },
    ]

    def send(url: str, headers: object, body: dict, timeout: float) -> dict:
        bodies.append(json.loads(json.dumps(body)))
        return replies[len(bodies) - 1]

    box = _toolbox()
    result = OpenAIClient(db, ciph, send=send).complete(
        CompletionRequest(text_model(), "", "write it", tools=box)
    )
    assert result.text == "Done."
    assert result.usage.input_tokens == 12
    assert bodies[0]["tools"][0]["function"]["name"] == "Read"  # type: ignore[index]
    assert bodies[1]["messages"][-1] == {  # type: ignore[index]
        "role": "tool",
        "tool_call_id": "c1",
        "content": "contents of b",
    }


def test_claude_code_offers_the_toolbox_as_its_only_tools(
    tmp_path: Path,
) -> None:
    box = _toolbox(most=4)
    request = CompletionRequest(
        {"name": "s", "model": "claude-sonnet-5"}, "", "x", tools=box
    )
    options = sdk_options(request, tmp_path, print)
    assert options.allowed_tools == ["mcp__hrono__Read"]
    assert set(options.mcp_servers) == {"hrono"}
    assert options.tools == []  # none of the CLI's own
    assert options.max_turns > box.most
    assert options.thinking["type"] == "enabled"  # deciding what to look up
    plain = sdk_options(
        CompletionRequest({"name": "s", "model": "m"}, "", "x"), tmp_path, print
    )
    assert not plain.mcp_servers and not plain.allowed_tools
    assert plain.thinking == {"type": "disabled"}


def test_a_spent_budget_is_said_not_raised() -> None:
    box = _toolbox(most=0)
    assert box.call("Read", {"path": "a"}) == SPENT
