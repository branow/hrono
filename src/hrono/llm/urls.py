"""Where an openai-shaped server's API root actually is (#152, #153).

Both spellings are in the wild and both are right: ollama's own documentation
gives ``http://localhost:11434/v1`` while a proxy is usually configured as a
bare host. Appending ``/v1`` unconditionally posts to ``/v1/v1/...`` for half
the users; never appending it breaks the other half.

Its own module because BOTH boundaries need it and neither may import the
other: the completion client calls the endpoint, and the registry validates it
at write time.
"""

from __future__ import annotations


def api_root(base: str) -> str:
    """The ``/v1`` root of ``base``, whether or not it already names one."""
    trimmed = base.rstrip("/")
    return trimmed if trimmed.endswith("/v1") else f"{trimmed}/v1"
