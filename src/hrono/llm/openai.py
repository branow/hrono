"""The ``openai`` and ``openai-compatible`` providers.

Both halves of a provider live here, because they are the same wire protocol
and the same credential: completions through ``POST /v1/chat/completions`` and
embeddings through ``POST /v1/embeddings``.

**Over httpx, not the openai SDK.** The stack note lists the SDK, and this
deliberately does not use it: the whole point of ``openai-compatible`` is that
ollama, vllm and lm-studio speak this REST shape without being openai, httpx is
already a dependency, and a stub server in a test is then a REAL round trip
rather than a mocked client object. Two endpoints and a bearer header
are not enough surface to justify an SDK, and the SDK's retries and defaults
would be one more thing to reason about when a local server misbehaves.

A connection's ``endpoint`` overrides the base url — required for
``openai-compatible``, optional for ``openai`` (a proxy or gateway) — and its
key may be absent entirely, which is the normal case for a local server. The
endpoint may or may not already include the ``/v1`` root; both spellings are in
the wild and ``llm.urls.api_root`` accepts either.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import httpx

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Usage,
)
from hrono.llm.ledger import Tally
from hrono.llm.urls import api_root
from hrono.registry import store

BASE = "https://api.openai.com"
TIMEOUT = 300.0
_DEFAULT_MAX_TOKENS = 4096


class OpenAIClient:
    """A ``Completion`` over the openai chat-completions REST shape."""

    def __init__(
        self,
        database: Database,
        cipher: Cipher | None,
        *,
        send: object = None,
        timeout: float = TIMEOUT,
    ) -> None:
        self._database = database
        self._cipher = cipher
        self._send = send if send is not None else post_json
        self._timeout = timeout

    def complete(self, request: CompletionRequest) -> CompletionResult:
        key, base = credential(
            self._database, self._cipher, request.model.get("connection")
        )
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.content})
        payload = self._send(  # type: ignore[operator]
            api_root(base) + "/chat/completions",
            auth_headers(key),
            {
                "model": str(request.model["model"]),
                "messages": messages,
                "max_tokens": _max_tokens(request.model),
            },
            self._timeout,
        )
        return _completion(payload)


def embeddings(
    database: Database,
    cipher: Cipher | None,
    model: dict[str, object],
    *,
    send: object = None,
    timeout: float = TIMEOUT,
    tally: Tally | None = None,
) -> object:
    """Build the remote encoder for an embedding model on a connection.

    ``usage.prompt_tokens`` of each response goes to ``tally`` for the ledger.
    """
    poster = send if send is not None else post_json
    key, base = credential(database, cipher, model.get("connection"))
    name = str(model["model"])

    def encode(texts: list[str]) -> Sequence[Sequence[float]]:
        payload = poster(  # type: ignore[operator]
            api_root(base) + "/embeddings",
            auth_headers(key),
            {"model": name, "input": texts},
            timeout,
        )
        vectors = _vectors(payload, len(texts))
        if tally is not None:
            tokens = _prompt_tokens(payload)
            if tokens is not None:
                tally.add(tokens)
        return vectors

    return encode


def credential(
    database: Database, cipher: Cipher | None, name: object
) -> tuple[str | None, str]:
    """The (key, base url) a connection resolves to; the key may be absent.

    A local server usually has no credential at all, so a missing key is not an
    error here — a 401 from the server is what says the call needed one.
    """
    if name is None:
        raise LLMError("this model requires a connection")
    with database.connect() as conn:
        row = store.get(conn, "connections", str(name))
    if row is None:
        raise LLMError(f"unknown connection: {name}")
    connection: dict[str, object] = json.loads(row["config"])
    endpoint = connection.get("endpoint")
    base = str(endpoint).rstrip("/") if endpoint else BASE
    auth = connection.get("auth")
    key_id = row["key_id"]
    if not (isinstance(auth, dict) and auth.get("key")):
        return None, base
    if cipher is None or key_id is None:
        raise LLMError("no cipher available to read the connection's key")
    return cipher.decrypt(int(key_id), str(auth["key"])), base


def post_json(
    url: str, headers: dict[str, str], body: dict[str, object], timeout: float
) -> dict[str, object]:
    """One POST; any transport or status failure becomes one ``LLMError``."""
    try:
        response = httpx.post(url, headers=headers, json=body, timeout=timeout)
    except httpx.HTTPError as exc:
        raise LLMError(
            f"cannot reach the model server: {type(exc).__name__}"
        ) from exc
    if response.status_code in (401, 403):
        raise LLMError("the model server refused the credentials")
    if response.status_code != 200:
        raise LLMError(f"the model server returned {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise LLMError("the model server returned a malformed body") from exc
    if not isinstance(payload, dict):
        raise LLMError("the model server returned a malformed body")
    return payload


def _completion(payload: dict[str, object]) -> CompletionResult:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMError("the model server returned no choices")
    first = choices[0]
    message = first.get("message") if isinstance(first, dict) else None
    text = message.get("content") if isinstance(message, dict) else None
    if not isinstance(text, str):
        raise LLMError("the model server returned no message text")
    usage = payload.get("usage")
    counts = usage if isinstance(usage, dict) else {}
    prompt = int(counts.get("prompt_tokens", 0) or 0)
    cached = _cached(counts)
    model = payload.get("model")
    return CompletionResult(
        text=text,
        usage=Usage(
            input_tokens=prompt - (cached or 0),
            output_tokens=int(counts.get("completion_tokens", 0) or 0),
            cache_read=cached,
            model=model if isinstance(model, str) else None,
        ),
    )


def _cached(counts: dict[str, object]) -> int | None:
    """Cached prompt tokens, which this API counts INSIDE ``prompt_tokens``."""
    details = counts.get("prompt_tokens_details")
    cached = details.get("cached_tokens") if isinstance(details, dict) else None
    return cached if isinstance(cached, int) else None


def _vectors(
    payload: dict[str, object], expected: int
) -> Sequence[Sequence[float]]:
    """Vectors in the INPUT's order, which the index field defines.

    The API does not promise the response order matches the request's, and a
    silently reordered batch would attach every chunk to its neighbour's
    meaning — the kind of defect no test of a single input can see.
    """
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != expected:
        raise LLMError("the model server returned the wrong vector count")
    ordered: list[Sequence[float]] = [()] * expected
    for entry in data:
        if not isinstance(entry, dict):
            raise LLMError("the model server returned a malformed vector")
        index = entry.get("index", 0)
        vector = entry.get("embedding")
        if not isinstance(vector, list) or not isinstance(index, int):
            raise LLMError("the model server returned a malformed vector")
        if not 0 <= index < expected:
            raise LLMError("the model server returned a vector out of range")
        ordered[index] = [float(value) for value in vector]
    return ordered


def _prompt_tokens(payload: dict[str, object]) -> int | None:
    usage = payload.get("usage")
    tokens = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    return tokens if isinstance(tokens, int) else None


def auth_headers(key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _max_tokens(model: dict[str, object]) -> int:
    params = model.get("params")
    if isinstance(params, dict) and params.get("max_tokens") is not None:
        return int(params["max_tokens"])
    return _DEFAULT_MAX_TOKENS


__all__ = ["OpenAIClient", "credential", "embeddings"]
