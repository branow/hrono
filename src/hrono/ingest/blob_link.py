"""Where a git section's file lives on its host, at the commit it was read at.

The address is `git://<host>/<owner>[/<repo>]/<path>@<commit>`: a discovery
source stops its instance at the owner, so the repo is the path's first
segment there. An instance is already free of credentials (`git_instance`),
so a link built from it cannot carry any.
"""

from __future__ import annotations

from urllib.parse import quote

_BLOB = {
    "github.com": "blob",
    "gitlab.com": "-/blob",
    "bitbucket.org": "src",
}


def blob_url(
    instance: str, path: str, commit: str, first: int, last: int
) -> str | None:
    """The host's page for the file at `commit`, or None for an unknown host.

    The line anchor is each host's own spelling of a range.
    """
    host, _, rest = instance.partition("/")
    kind = _BLOB.get(host)
    if kind is None or not rest:
        return None
    repo = rest
    if "/" not in rest and host != "gitlab.com":
        name, _, path = path.partition("/")
        repo = f"{rest}/{name}"
    if not path:
        return None
    base = f"https://{host}/{repo}/{kind}/{quote(commit)}/{quote(path)}"
    return base + _anchor(host, first, last)


def _anchor(host: str, first: int, last: int) -> str:
    if host == "bitbucket.org":
        return f"#lines-{first}:{last}" if last > first else f"#lines-{first}"
    if host == "gitlab.com":
        return f"#L{first}-{last}" if last > first else f"#L{first}"
    return f"#L{first}-L{last}" if last > first else f"#L{first}"
