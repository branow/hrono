"""Text completion over the anthropic SDK — the one LLM call seam.

``AnthropicClient.complete`` takes a resolved text-kind model config, a system
prompt, and the content to summarise, resolves and decrypts the provider key
from the model's ``connection`` via the secrets cipher (the only way it reads
the secret — never logged, returned, or persisted in cleartext), calls the
provider, and returns ``(text, usage)`` with input/output token counts. Any
SDK/transport/auth failure surfaces as one ``LLMError``, never a raw traceback.

Two seams: ops depend on the ``Completion`` protocol so a fake drives their
tests offline; the client's own ``invoke`` seam stands in for the SDK call so
this module is testable without network or tokens. The ``anthropic`` import is
lazy and contained here, so the rest of the codebase never imports it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.errors import DomainError
from hrono.registry import store

_DEFAULT_MAX_TOKENS = 4096


class LLMError(DomainError):
    """A completion call failed (reason is client-safe, never a traceback)."""

    code = "llm-error"


class Unfinished(LLMError):
    """The model ran out of room before it finished answering this content.

    A property of the CONTENT, not of the provider's health: the same
    material fails the same way on a retry, so a caller may record it and
    move on, where any other ``LLMError`` has to stop the run.
    """

    code = "llm-unfinished"


@dataclass(frozen=True)
class Usage:
    """Token accounting for one completion (drives cost/provenance later).

    ``input_tokens`` never includes cached input: a provider that reports a
    cache hit or a cache write has it in ``cache_read`` / ``cache_creation``,
    and one that reports neither leaves them None, which is unknown rather than
    zero. ``model`` is what the provider says it ran.
    """

    input_tokens: int
    output_tokens: int
    cache_read: int | None = None
    cache_creation: int | None = None
    model: str | None = None


@dataclass(frozen=True)
class CompletionRequest:
    """A resolved text-model config plus the system prompt and user content.

    ``schema`` is a JSON schema the answer must satisfy. Only the
    ``claude-code`` provider honours it today; the others accept it and
    answer in plain text, so a caller that sets it reads ``structured`` and
    must cope with None.
    """

    model: dict[str, object]
    system: str
    content: str
    schema: dict[str, object] | None = None


@dataclass(frozen=True)
class CompletionResult:
    """The answer's text, its usage, and the object a ``schema`` asked for."""

    text: str
    usage: Usage
    structured: dict[str, object] | None = None


class Completion(Protocol):
    """The op-facing seam: summarisation ops depend on this, not the SDK."""

    def complete(self, request: CompletionRequest) -> CompletionResult: ...


Invoke = Callable[..., object]


class AnthropicClient:
    """A ``Completion`` over the anthropic SDK, credential fed by cipher.

    A request's ``schema`` is ignored for now: the answer comes back as text
    and ``structured`` stays None.
    """

    def __init__(
        self,
        database: Database,
        cipher: Cipher,
        *,
        invoke: Invoke | None = None,
    ) -> None:
        self._database = database
        self._cipher = cipher
        self._invoke = invoke if invoke is not None else _default_invoke

    def complete(self, request: CompletionRequest) -> CompletionResult:
        key, base_url = self._credential(request.model)
        try:
            response = self._invoke(
                api_key=key,
                base_url=base_url,
                model=str(request.model["model"]),
                system=request.system,
                content=request.content,
                max_tokens=_max_tokens(request.model),
            )
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 - any SDK/transport failure
            raise LLMError("completion request failed") from exc
        return _read(response)

    def _credential(self, model: dict[str, object]) -> tuple[str, str | None]:
        return credential(self._database, self._cipher, model.get("connection"))


def credential(
    database: Database, cipher: Cipher, name: object
) -> tuple[str, str | None]:
    """The (api key, endpoint) an anthropic connection resolves to."""
    if name is None:
        raise LLMError("text model requires a connection")
    with database.connect() as conn:
        row = store.get(conn, "connections", str(name))
    if row is None:
        raise LLMError(f"unknown connection: {name}")
    connection: dict[str, object] = json.loads(row["config"])
    auth = connection.get("auth")
    key_id = row["key_id"]
    if not (isinstance(auth, dict) and auth.get("key") and key_id):
        raise LLMError("connection has no api key")
    key = cipher.decrypt(key_id, str(auth["key"]))
    endpoint = connection.get("endpoint")
    return key, str(endpoint).rstrip("/") if endpoint else None


def _max_tokens(model: dict[str, object]) -> int:
    params = model.get("params")
    if isinstance(params, dict) and params.get("max_tokens") is not None:
        return int(params["max_tokens"])
    return _DEFAULT_MAX_TOKENS


def _read(response: object) -> CompletionResult:
    blocks = getattr(response, "content", None) or []
    text = "".join(getattr(block, "text", "") for block in blocks)
    usage = getattr(response, "usage", None)
    model = getattr(response, "model", None)
    return CompletionResult(
        text=text,
        usage=Usage(
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            cache_read=_count(getattr(usage, "cache_read_input_tokens", None)),
            cache_creation=_count(
                getattr(usage, "cache_creation_input_tokens", None)
            ),
            model=model if isinstance(model, str) else None,
        ),
    )


def _count(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _default_invoke(
    *,
    api_key: str,
    base_url: str | None,
    model: str,
    system: str,
    content: str,
    max_tokens: int,
) -> object:
    try:
        import anthropic
    except ImportError as exc:
        raise LLMError("anthropic SDK is not installed") from exc

    client_kwargs: dict[str, object] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    create_kwargs: dict[str, object] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if system:
        create_kwargs["system"] = system
    return anthropic.Anthropic(**client_kwargs).messages.create(**create_kwargs)
