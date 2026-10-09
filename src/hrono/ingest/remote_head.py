"""Where a git source's remote is NOW, without reading a byte of it.

`git ls-remote <url> HEAD` asks the remote for the commit its default branch
points at and nothing else — no clone, no fetch, no content. Set beside the
commit the last sync pinned, it answers whether the source has moved since,
which is the only way to know a tree is behind before a sync spends anything.

The credential travels exactly as it does for a sync and for validation:
through `git_auth`, never in the URL, never in a returned value.
"""

from __future__ import annotations

import subprocess

from hrono.registry.validation.git_auth import git_auth


def remote_head(config: dict[str, object], timeout: float) -> str | None:
    """The commit the remote's HEAD is at, or None when it cannot be read.

    None covers every way of not knowing — unreachable, refused, timed out,
    an empty repository; a failed `ls-remote` prints nothing — because the
    caller's honest answer to all of them is
    the same: "could not compare".
    """
    auth = config.get("auth")
    auth_dict = auth if isinstance(auth, dict) else {"method": "none"}
    with git_auth(str(config["url"]), auth_dict) as (url, env, config_args):
        try:
            done = subprocess.run(
                ["git", *config_args, "ls-remote", "--", url, "HEAD"],
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return None
    fields = done.stdout.split()
    return fields[0] if fields else None
