"""The loop's ``Chat`` for an openai or openai-compatible connection."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from hrono.demo.agents.loop import Message, Reply, Use, specs
from hrono.llm.client import LLMError, Usage
from hrono.llm.openai import auth_headers, post_json
from hrono.llm.urls import api_root

MAX_TOKENS = 4096
TIMEOUT = 300.0

Post = Callable[
    [str, dict[str, str], dict[str, object], float], dict[str, object]
]


@dataclass
class OpenAIChat:
    """Chat completions with tools against one server and model."""

    key: str | None
    base: str
    model: str
    system: str
    post: Post = post_json

    def user(self, text: str) -> Message:
        return {"role": "user", "content": text}

    def results(self, done: list[tuple[Use, str]]) -> list[Message]:
        return [
            {"role": "tool", "tool_call_id": use.id, "content": text}
            for use, text in done
        ]

    def ask(self, history: list[Message]) -> Reply:
        payload = self.post(
            api_root(self.base) + "/chat/completions",
            auth_headers(self.key),
            {
                "model": self.model,
                "max_tokens": MAX_TOKENS,
                "messages": [
                    {"role": "system", "content": self.system},
                    *history,
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": spec["name"],
                            "description": spec["description"],
                            "parameters": spec["schema"],
                        },
                    }
                    for spec in specs()
                ],
            },
            TIMEOUT,
        )
        return _reply(payload)


def _reply(payload: dict[str, object]) -> Reply:
    choices = payload.get("choices")
    first = choices[0] if isinstance(choices, list) and choices else None
    message = first.get("message") if isinstance(first, dict) else None
    if not isinstance(message, dict):
        raise LLMError("the model server returned no message")
    calls = message.get("tool_calls") or []
    uses = tuple(_use(call) for call in calls if isinstance(call, dict))
    text = message.get("content")
    counts = payload.get("usage")
    counts = counts if isinstance(counts, dict) else {}
    model = payload.get("model")
    said: Message = {"role": "assistant", "content": text or ""}
    if calls:
        said["tool_calls"] = calls
    return Reply(
        text=text if isinstance(text, str) else "",
        uses=uses,
        usage=Usage(
            input_tokens=int(counts.get("prompt_tokens", 0) or 0),
            output_tokens=int(counts.get("completion_tokens", 0) or 0),
            model=model if isinstance(model, str) else None,
        ),
        said=said,
    )


def _use(call: dict[str, object]) -> Use:
    function = call.get("function")
    function = function if isinstance(function, dict) else {}
    try:
        args = json.loads(str(function.get("arguments") or "{}"))
    except ValueError:
        args = {}
    return Use(
        id=str(call.get("id", "")),
        tool=str(function.get("name", "")),
        args=args if isinstance(args, dict) else {},
    )
