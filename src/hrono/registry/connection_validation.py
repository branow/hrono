"""Provider reachability + auth validation for connections, run on write.

Dispatch is data-driven: one validator per provider, so a new provider is a map
entry (T44), not a branch. ``anthropic`` hits the no-inference list-models
endpoint (200 = the key authenticates). Other providers keep the no-op stub
until their tickets. The api-key never appears in a reason or log line.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from hrono.registry.descriptor import ValidationFailed

_TIMEOUT = 10.0
_DEFAULT_ENDPOINT = "https://api.anthropic.com"

Runner = Callable[[str, str, float], int]


def validate_connection(
    config: dict[str, object],
    *,
    run: Runner | None = None,
    timeout: float = _TIMEOUT,
) -> None:
    """Reject the write unless the provider validates the credential."""
    validator = _VALIDATORS.get(str(config["provider"]))
    if validator is None:
        return
    validator(config, run if run is not None else _get, timeout)


def _validate_anthropic(
    config: dict[str, object], run: Runner, timeout: float
) -> None:
    key = str(config["auth"]["key"])  # type: ignore[index]
    endpoint = config.get("endpoint") or _DEFAULT_ENDPOINT
    url = str(endpoint).rstrip("/") + "/v1/models"
    status = run(url, key, timeout)
    if status == 200:
        return
    if status in (401, 403):
        raise ValidationFailed("authentication failed")
    raise ValidationFailed("cannot reach provider")


def _get(url: str, api_key: str, timeout: float) -> int:
    try:
        response = httpx.get(
            url,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=timeout,
        )
    except httpx.HTTPError:
        return 0
    return response.status_code


_VALIDATORS: dict[str, Callable[..., None]] = {
    "anthropic": _validate_anthropic,
}
