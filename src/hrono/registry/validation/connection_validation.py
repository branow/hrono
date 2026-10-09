"""Provider reachability + auth validation for connections, run on write.

Dispatch is data-driven: one validator per provider, so a new provider is a map
entry, not a branch. ``anthropic`` hits the no-inference list-models
endpoint (200 = the key authenticates). ``claude-code`` has no credential at all
— it bills through the operator's login — so what it validates is that the CLI
is present and runnable, which is the failure a user would otherwise meet hours
later at ``condense`` time. A provider with no validator registers without a
check. The api-key never appears in a reason or log line.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx

from hrono.llm.urls import api_root
from hrono.registry.descriptor import ValidationFailed

if TYPE_CHECKING:
    from hrono.registry.descriptor import ValidationContext

_TIMEOUT = 10.0
_CLI_TIMEOUT = 15.0
_DEFAULT_ENDPOINT = "https://api.anthropic.com"
_OPENAI_ENDPOINT = "https://api.openai.com"
_BEARER = ("openai", "openai-compatible")

Reply = int | tuple[int, str]
Runner = Callable[[str, str, float], Reply]
Probe = Callable[[], bool]


def validate_connection(
    config: dict[str, object],
    context: ValidationContext | None = None,
    *,
    run: Runner | None = None,
    probe: Probe | None = None,
    timeout: float = _TIMEOUT,
) -> None:
    """Reject the write unless the provider validates the credential.

    ``context`` is unused here — a connection validates against its own key.
    """
    provider = str(config["provider"])
    if provider == "claude-code":  # no credential; the CLI is the credential
        _validate_claude_code(probe if probe is not None else _cli_version)
        return
    validator = _VALIDATORS.get(provider)
    if validator is None:
        return
    validator(config, run if run is not None else _default(provider), timeout)


def _default(provider: str) -> Runner:
    """The runner a provider authenticates with, resolved at CALL time.

    Anthropic sends ``x-api-key``; the openai-shaped providers send a bearer
    header. Looked up here rather than held in a table of function objects so
    that patching either name in this module actually takes effect — a table
    would capture the original function at import and quietly ignore the
    patch.
    """
    return _bearer_get if provider in _BEARER else _get


def _validate_anthropic(
    config: dict[str, object], run: Runner, timeout: float
) -> None:
    key = str(config["auth"]["key"])  # type: ignore[index]
    endpoint = config.get("endpoint") or _DEFAULT_ENDPOINT
    url = str(endpoint).rstrip("/") + "/v1/models"
    _judge(run(url, key, timeout), key)


def _validate_openai(
    config: dict[str, object], run: Runner, timeout: float
) -> None:
    """Listing models costs nothing and proves the key authenticates."""
    _check_models(config, run, timeout, _OPENAI_ENDPOINT)


def _validate_openai_compatible(
    config: dict[str, object], run: Runner, timeout: float
) -> None:
    """A local server has no default address, so it must declare one.

    The model already requires ``endpoint`` for this provider; this is the
    same rule at the other boundary, so a config that reaches here another way
    still cannot register something nothing can call.
    """
    endpoint = config.get("endpoint")
    if not endpoint:
        raise ValidationFailed(
            "an openai-compatible connection needs an endpoint"
        )
    _check_models(config, run, timeout, str(endpoint))


def _check_models(
    config: dict[str, object], run: Runner, timeout: float, fallback: str
) -> None:
    auth = config.get("auth")
    key = str(auth.get("key") or "") if isinstance(auth, dict) else ""
    endpoint = config.get("endpoint") or fallback
    _judge(run(api_root(str(endpoint)) + "/models", key, timeout), key)


_REASON_LIMIT = 200


def _judge(reply: Reply, key: str) -> None:
    """Accept a 200; otherwise refuse with the provider's own reason, if any.

    The reason is what the provider said about the call, so a person can tell
    a mistyped key from an expired one. The key itself is masked out of it: a
    provider that echoes the credential must not put it on a page or in a log.
    """
    status, said = (reply, "") if isinstance(reply, int) else reply
    if status == 200:
        return
    if key:
        said = said.replace(key, "***")
    said = said[:_REASON_LIMIT]
    if status in (401, 403):
        raise ValidationFailed(
            f"authentication failed: {said}"
            if said
            else "authentication failed"
        )
    raise ValidationFailed("cannot reach provider")


def _validate_claude_code(probe: Probe) -> None:
    """A ``claude-code`` connection is valid when the CLI answers.

    There is no key to check — it bills through the operator's own login — so
    what must be true at WRITE time is that the binary is present and runnable.
    Otherwise the failure surfaces at ``condense`` time, hours later, as a
    subprocess error on a job the user has already paid to reach.
    """
    if not probe():
        raise ValidationFailed(
            "the claude CLI is not on PATH or is not runnable"
        )


def _cli_version() -> bool:
    try:
        done = subprocess.run(  # noqa: S603 - a fixed argv, no user input
            ["claude", "--version"],  # noqa: S607
            capture_output=True,
            timeout=_CLI_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def _reason(response: httpx.Response) -> str:
    """The message a provider's JSON error carries, or nothing."""
    try:
        error = response.json()["error"]
        said = error["message"] if isinstance(error, dict) else error
    except (ValueError, KeyError, TypeError):
        return ""
    return said.strip() if isinstance(said, str) else ""


def _get(url: str, api_key: str, timeout: float) -> Reply:
    try:
        response = httpx.get(
            url,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=timeout,
        )
    except httpx.HTTPError:
        return 0
    return response.status_code, _reason(response)


def _bearer_get(url: str, api_key: str, timeout: float) -> Reply:
    """A plain bearer GET, which is what an openai-shaped server expects."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError:
        return 0
    return response.status_code, _reason(response)


_VALIDATORS: dict[str, Callable[..., None]] = {
    "anthropic": _validate_anthropic,
    "openai": _validate_openai,
    "openai-compatible": _validate_openai_compatible,
}
