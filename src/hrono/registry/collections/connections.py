"""The ``connections`` collection: provider credentials (T8.1).

A second registry instance proving the base generalizes: this is a descriptor
plus a provider-discriminated model, wired through #012's engine with no engine
change. Provider reachability validation is the follow-on (#016); the hook seam
is a no-op here.
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
