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

Every client handed out here is wrapped in the usage ledger (#201), including
one a caller injected in place of the provider's own, so no provider and no op
can make a call the ledger does not see.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from hrono.jobs import store as jobs_store
from hrono.jobs.ops import JobContext
from hrono.llm.claude_code import ClaudeCodeClient
from hrono.llm.client import AnthropicClient, Completion, LLMError
from hrono.llm.ledger import Ledgered
from hrono.llm.openai import OpenAIClient
from hrono.registry import store

_DEFAULT_PROVIDER = "anthropic"
INJECTED = "injected"  # the ledger's provider for a caller-supplied client


def client_for(
    context: JobContext,
    model: dict[str, object],
    role: str,
    *,
    client: Completion | None = None,
) -> Completion:
    """The completion client this model asks for, recording every call.

    ``client`` stands in for the provider's own (the ops' test seam). It is
    recorded the same way, so the ledger a test reads is the one production
    writes; its provider is ``INJECTED``, because no connection chose it.
    """
    if client is not None:
        return Ledgered(client, context, role=role, provider=INJECTED)
    provider = provider_for(context, model)
    inner = _build(context, provider, model)
    return Ledgered(inner, context, role=role, provider=provider)


def bounded_cli_client(
    context: JobContext, role: str, timeout: float
) -> Completion:
    """The claude-code client with its own time limit, still ledgered.

    A validation probe must end before the caller's own wait does, so it
    cannot take the client's generous default.
    """
    inner = ClaudeCodeClient(context.cli_dir(), timeout=timeout)
    return Ledgered(inner, context, role=role, provider="claude-code")


def _build(
    context: JobContext, provider: str, model: dict[str, object]
) -> Completion:
    builder = _PROVIDERS.get(provider)
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
    return ClaudeCodeClient(context.cli_dir(), wanted=_still_running(context))


def _still_running(context: JobContext) -> Callable[[], bool]:
    """Whether the job a call belongs to still wants its answer.

    The claude-code client can wait hours out a usage limit; a run that was
    stopped meanwhile must not keep it waiting. No job (a validation probe, a
    direct call) wants it for as long as the caller waits.
    """
    job_id = context.job_id
    if job_id is None:
        return lambda: True

    def running() -> bool:
        with context.database.connect() as conn:
            row = jobs_store.get(conn, job_id)
        return row is None or row["status"] == "running"

    return running


def _openai(context: JobContext) -> Completion:
    """Both openai-shaped providers are one client; the connection differs."""
    return OpenAIClient(context.database, context.cipher)


_PROVIDERS: dict[str, Callable[[JobContext], Completion]] = {
    "anthropic": _anthropic,
    "claude-code": _claude_code,
    "openai": _openai,
    "openai-compatible": _openai,
}
