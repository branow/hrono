"""Which ``Completion`` a model's connection resolves to (#107, T44).

Dispatch is DATA, not a branch: one entry per provider, the same shape
``connection_validation._VALIDATORS`` uses, so ``openai`` (T44.1) and
``openai-compatible`` (T44.3) are later map entries rather than new code paths
through every op. Before this, four ops each carried their own
``_default_client`` hardcoding the anthropic SDK, so a connection registered
with any other provider failed at call time with no useful message.

The model's connection names the provider; a model that resolves to no
connection keeps the anthropic default, which is what every existing database
has.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from hrono.jobs.ops import JobContext
from hrono.llm.claude_code import ClaudeCodeClient
from hrono.llm.client import AnthropicClient, Completion, LLMError
from hrono.llm.openai import OpenAIClient
from hrono.registry import store

_DEFAULT_PROVIDER = "anthropic"


def client_for(context: JobContext, model: dict[str, object]) -> Completion:
    """The completion client this model's connection asks for."""
    builder = _PROVIDERS.get(provider_for(context, model))
    if builder is None:
        raise LLMError(f"unsupported provider for model: {model.get('name')}")
    return builder(context)


def provider_for(context: JobContext, model: dict[str, object]) -> str:
    """The provider named by this model's connection (#151).

    Shared with the embedding side, which dispatches on the same answer: a
    model is remote or local by whether it HAS a connection, and which remote
    by what that connection says it is.
    """
    name = model.get("connection")
    if name is None:
        return _DEFAULT_PROVIDER
    with context.database.connect() as conn:
        row = store.get(conn, "connections", str(name))
    if row is None:
        raise LLMError(f"unknown connection: {name}")
    config: dict[str, object] = json.loads(row["config"])
    return str(config.get("provider") or _DEFAULT_PROVIDER)


def _anthropic(context: JobContext) -> Completion:
    if context.cipher is None:
        raise LLMError("no cipher available for the completion client")
    return AnthropicClient(context.database, context.cipher)


def _claude_code(context: JobContext) -> Completion:
    """No credential of its own — it bills through the operator's login.

    The working directory is anchored on the database rather than the process
    cwd, because the CLI reads the project memory of wherever it starts (#107).
    """
    return ClaudeCodeClient(context.cli_dir())


def _openai(context: JobContext) -> Completion:
    """Both openai-shaped providers are one client; the connection differs."""
    return OpenAIClient(context.database, context.cipher)


_PROVIDERS: dict[str, Callable[[JobContext], Completion]] = {
    "anthropic": _anthropic,
    "claude-code": _claude_code,
    "openai": _openai,
    "openai-compatible": _openai,
}
