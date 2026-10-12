"""The loop's ``Chat`` for an anthropic connection: the messages API."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hrono.demo.agents.loop import Message, Reply, Use, specs
from hrono.llm.client import LLMError, Usage

MAX_TOKENS = 4096

Create = Callable[..., object]


@dataclass
class AnthropicChat:
    """Requests to one model, with its key and endpoint already resolved."""

    key: str
    endpoint: str | None
    model: str
    system: str
    create: Create | None = None  # the SDK's ``messages.create``; a test seam

    def user(self, text: str) -> Message:
        return {"role": "user", "content": text}

    def results(self, done: list[tuple[Use, str]]) -> list[Message]:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": use.id,
                        "content": text,
                    }
                    for use, text in done
                ],
            }
        ]

    def ask(self, history: list[Message]) -> Reply:
        try:
            response = self._create()(
                model=self.model,
                max_tokens=MAX_TOKENS,
                system=self.system,
                messages=history,
                tools=[
                    {
                        "name": spec["name"],
                        "description": spec["description"],
                        "input_schema": spec["schema"],
                    }
                    for spec in specs()
                ],
            )
        except Exception as exc:  # noqa: BLE001 - any SDK/transport failure
            raise LLMError(f"the model request failed: {exc}") from exc
        return _reply(response)

    def _create(self) -> Create:
        if self.create is not None:
            return self.create
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError("anthropic SDK is not installed") from exc
        kwargs: dict[str, object] = {"api_key": self.key}
        if self.endpoint:
            kwargs["base_url"] = self.endpoint
        return anthropic.Anthropic(**kwargs).messages.create  # type: ignore[arg-type]


def _reply(response: object) -> Reply:
    blocks: list[dict[str, object]] = []
    text, uses = "", []
    for block in getattr(response, "content", None) or []:
        kind = getattr(block, "type", "")
        if kind == "text":
            text += str(getattr(block, "text", ""))
            blocks.append({"type": "text", "text": getattr(block, "text", "")})
        elif kind == "tool_use":
            use = Use(
                id=str(getattr(block, "id", "")),
                tool=str(getattr(block, "name", "")),
                args=dict(getattr(block, "input", None) or {}),
            )
            uses.append(use)
            blocks.append(
                {
                    "type": "tool_use",
                    "id": use.id,
                    "name": use.tool,
                    "input": use.args,
                }
            )
    usage = getattr(response, "usage", None)
    model = getattr(response, "model", None)
    return Reply(
        text=text,
        uses=tuple(uses),
        usage=Usage(
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            cache_read=getattr(usage, "cache_read_input_tokens", None),
            cache_creation=getattr(usage, "cache_creation_input_tokens", None),
            model=model if isinstance(model, str) else None,
        ),
        said={"role": "assistant", "content": blocks},
    )
