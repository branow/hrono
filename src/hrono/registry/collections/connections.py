"""The ``connections`` collection: provider credentials (T8.1).

A second registry instance proving the base generalizes: this is a descriptor
plus a provider-discriminated model, wired through #012's engine with no engine
change. Provider reachability validation is the follow-on (#016); the hook seam
is a no-op here.

WHICH PROVIDER TO REGISTER, and when. This is where that decision is made, so
the numbers live here rather than only in the driver that measured them:

- ``claude-code`` needs no API key and bills through the operator's existing
  Claude subscription, so it is the right first connection for trying hrono out
  and for the small incremental syncs that follow a first build — a handful of
  changed sections costs a handful of calls.
- a FIRST FULL BUILD over a large corpus should use ``anthropic``. The CLI
  carries a fixed per-call overhead no prompt can remove: a trivial call
  reported ``cache_creation_input_tokens: 18871`` and ``total_cost_usd: 0.038``,
  and each call takes 4-30 s. Measured on a real corpus, the ``condense`` pass
  over 421 sections took about 70 minutes and about $16 through the CLI. The
  same work through the ``anthropic`` provider is both cheaper and faster,
  because it pays for the content and not for the harness.

Both can be registered at once: the connection is named per MODEL, so a
``condense``-role model can point at ``anthropic`` for the build while
everything else stays on ``claude-code``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, RootModel

from hrono.registry.descriptor import Descriptor, RegistryName
from hrono.registry.validation.connection_validation import validate_connection


class ApiKeyAuth(BaseModel):
    method: Literal["api-key"]
    key: str


class NoneAuth(BaseModel):
    method: Literal["none"]


class OptionalKeyAuth(BaseModel):
    method: Literal["none", "api-key"]
    key: str | None = None


class AnthropicConnection(BaseModel):
    name: RegistryName
    provider: Literal["anthropic"]
    auth: ApiKeyAuth
    endpoint: str | None = None


class OpenAIConnection(BaseModel):
    name: RegistryName
    provider: Literal["openai"]
    auth: ApiKeyAuth
    endpoint: str | None = None


class OpenAICompatibleConnection(BaseModel):
    name: RegistryName
    provider: Literal["openai-compatible"]
    endpoint: str
    auth: OptionalKeyAuth


class ClaudeCodeConnection(BaseModel):
    name: RegistryName
    provider: Literal["claude-code"]
    auth: NoneAuth


class Connection(
    RootModel[
        Annotated[
            AnthropicConnection
            | OpenAIConnection
            | OpenAICompatibleConnection
            | ClaudeCodeConnection,
            Field(discriminator="provider"),
        ]
    ]
):
    pass


CONNECTIONS = Descriptor(
    collection="connections",
    model=Connection,
    secret_paths=(("auth", "key"),),
    write_role="writer",
    validate=validate_connection,
)
