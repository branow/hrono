"""Model validation on write: embedding dims + text round-trip, by kind.

Dispatch is data-driven (one validator per kind). Probes are minimal (one tiny
input) and injectable so the suite runs offline. A model that names a
``connection`` resolves it from the connections registry and decrypts its key
only to reach the provider; the credential never appears in a reason, log, or
stored row.

The endpoint is resolved through ``llm.urls.api_root`` — the same rule the
completion client and the connection validator use — because an endpoint may
already name its ``/v1`` root. Appending one regardless probed
``/v1/v1/chat/completions`` and refused every working local server (#153).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

from hrono.llm.urls import api_root
from hrono.registry import store
from hrono.registry.descriptor import ValidationContext, ValidationFailed

_TIMEOUT = 10.0

Embed = Callable[[dict[str, object], dict[str, object] | None, float], Sequence]
Generate = Callable[[dict[str, object], dict[str, object], float], str]


def validate_model(
    config: dict[str, object],
    context: ValidationContext,
    *,
    embed: Embed | None = None,
    generate: Generate | None = None,
    timeout: float = _TIMEOUT,
) -> None:
    """Reject the write unless the model loads/reaches and behaves right."""
    validator = _VALIDATORS.get(str(config["kind"]))
    if validator is None:
        return
    validator(
        config,
        context,
        embed if embed is not None else _default_embed,
        generate if generate is not None else _default_generate,
        timeout,
    )


def _validate_embedding(
    config: dict[str, object],
    context: ValidationContext,
    embed: Embed,
    generate: Generate,
    timeout: float,
) -> None:
    connection = _resolve(config, context)
    try:
        vector = embed(config, connection, timeout)
    except ValidationFailed:
        raise
    except Exception as exc:  # noqa: BLE001 - load/backend failure
        raise ValidationFailed("cannot load embedding model") from exc
    dims = _declared_dims(config)
    if dims is not None and len(vector) != dims:
        raise ValidationFailed(
            f"embedding dims mismatch: declared {dims}, got {len(vector)}"
        )


def _validate_text(
    config: dict[str, object],
    context: ValidationContext,
    embed: Embed,
    generate: Generate,
    timeout: float,
) -> None:
    if config.get("connection") is None:
        raise ValidationFailed("text model requires a connection")
    connection = _resolve(config, context)
    assert connection is not None
    try:
        output = generate(config, connection, timeout)
    except ValidationFailed:
        raise
    except Exception as exc:  # noqa: BLE001 - connection failure
        raise ValidationFailed("cannot reach the model connection") from exc
    if not output.strip():
        raise ValidationFailed("model returned an empty response")


def _resolve(
    config: dict[str, object], context: ValidationContext
) -> dict[str, object] | None:
    name = config.get("connection")
    if name is None:
        return None
    with context.database.connect() as conn:
        row = store.get(conn, "connections", str(name))
    if row is None:
        raise ValidationFailed(f"unknown connection: {name}")
    connection: dict[str, object] = json.loads(row["config"])
    key_id = row["key_id"]
    auth = connection.get("auth")
    if isinstance(auth, dict) and key_id is not None and auth.get("key"):
        auth["key"] = context.cipher.decrypt(key_id, str(auth["key"]))
    return connection


def _declared_dims(config: dict[str, object]) -> int | None:
    params = config.get("params")
    if not isinstance(params, dict):
        return None
    dims = params.get("dims")
    return int(dims) if dims is not None else None


def _default_embed(
    config: dict[str, object],
    connection: dict[str, object] | None,
    timeout: float,
) -> Sequence:
    if connection is None:
        return _embed_in_process(str(config["model"]))
    return _embed_remote(config, connection, timeout)


def _embed_in_process(model_id: str) -> Sequence:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ValidationFailed(
            "in-process embedding backend is not installed"
        ) from exc
    return list(SentenceTransformer(model_id).encode("probe"))


def _embed_remote(
    config: dict[str, object], connection: dict[str, object], timeout: float
) -> Sequence:
    import httpx

    url = api_root(_base_url(connection)) + "/embeddings"
    response = httpx.post(
        url,
        headers=_headers(connection),
        json={"model": config["model"], "input": "probe"},
        timeout=timeout,
    )
    if response.status_code != 200:
        raise ValidationFailed("embedding endpoint rejected the request")
    data = response.json().get("data") or []
    if not data:
        raise ValidationFailed("embedding endpoint returned no vector")
    return data[0].get("embedding") or []


def _default_generate(
    config: dict[str, object], connection: dict[str, object], timeout: float
) -> str:
    import httpx

    provider = str(connection.get("provider", ""))
    body = {
        "model": config["model"],
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hi"}],
    }
    root = api_root(_base_url(connection))
    url = (
        f"{root}/messages"
        if provider == "anthropic"
        else (f"{root}/chat/completions")
    )
    response = httpx.post(
        url, headers=_headers(connection), json=body, timeout=timeout
    )
    if response.status_code != 200:
        raise ValidationFailed("model connection rejected the request")
    return _extract_text(provider, response.json())


def _base_url(connection: dict[str, object]) -> str:
    endpoint = connection.get("endpoint")
    if endpoint:
        return str(endpoint).rstrip("/")
    if str(connection.get("provider")) == "anthropic":
        return "https://api.anthropic.com"
    return "https://api.openai.com"


def _headers(connection: dict[str, object]) -> dict[str, str]:
    auth = connection.get("auth")
    key = auth.get("key") if isinstance(auth, dict) else None
    if not key:
        return {}
    if str(connection.get("provider")) == "anthropic":
        return {"x-api-key": str(key), "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {key}"}


def _extract_text(provider: str, payload: dict) -> str:
    if provider == "anthropic":
        blocks = payload.get("content") or []
        return "".join(b.get("text", "") for b in blocks if isinstance(b, dict))
    choices = payload.get("choices") or []
    if not choices:
        return ""
    return str(choices[0].get("message", {}).get("content", ""))


_VALIDATORS: dict[str, Callable[..., None]] = {
    "embedding": _validate_embedding,
    "text": _validate_text,
}
