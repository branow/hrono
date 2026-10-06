"""Why a run failed, said in words, with what to do about it (#213).

A failed run used to show ``llm-error`` and the driver's sentence, and nothing
else: not the stage, not the section, not a next step. Every error CODE hrono
can raise has a plain sentence and a remedy here, keyed by the code — a test
walks every error class and fails when one has no entry, so a new code cannot
reach a run page unexplained. The raw message is still shown, behind a
disclosure, because it is the detail an operator pastes into a bug report.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# code -> (what happened, what to do next)
SAID: dict[str, tuple[str, str]] = {
    "llm-error": (
        "A call to the language model did not come back with an answer.",
        "Check the model and its connection in Settings, then retry: work "
        "already done is kept and is not paid for again.",
    ),
    "embed-error": (
        "The embedding model could not turn text into vectors.",
        "Check the embedding model in Settings. A model that runs on this "
        "server needs the embedding backend installed "
        '(uv pip install "hrono[embed]").',
    ),
    "cluster-error": (
        "Grouping sections into topics failed.",
        "Make sure the topic-grouping backend is installed "
        "(pip install 'hrono[cluster]'), then retry.",
    ),
    "too-few-points": (
        "There were too few sections to group into topics.",
        "Add a source with more files, or widen the source's filter, and "
        "sync again.",
    ),
    "sync-error": (
        "A source could not be fetched.",
        "Check the source's address and credentials in Settings, and that "
        "this server can reach it, then retry.",
    ),
    "split-error": (
        "The fetched files could not be cut into sections.",
        "Retry. If it fails again on the same file, exclude that file in the "
        "source's filter.",
    ),
    "crash-loop": (
        "This job took its worker down on every try, so it was stopped "
        "instead of being retried again.",
        "Check the server log for what crashed (often memory), fix or shrink "
        "the input, then retry the run.",
    ),
    "shared-corpus": (
        "This tree is unscoped, and other trees exist: building it would "
        "ingest sources that belong to them, and two trees over one source "
        "corrupt each other.",
        "Give the tree its own sources in Settings (or hrono tree config "
        "set), then retry.",
    ),
    "linked-cache": (
        "The local copy of a source is a link hrono will not follow.",
        "Remove the link from the cache directory and sync again.",
    ),
    "decrypt-error": (
        "A stored secret could not be decrypted with this server's key.",
        "Start the server with the master key the secrets were saved under, "
        "or enter the secret again in Settings.",
    ),
    "wrong-master-key": (
        "The server is running with a different master key than the one the "
        "secrets were saved under.",
        "Restart it with the original key file.",
    ),
    "master-key-error": (
        "The master key could not be used.",
        "Restart the server with a valid key file.",
    ),
    "master-key-invalid": (
        "The master key file does not hold a valid key.",
        "Make one with 'hrono admin new-key' or point the server at the "
        "right file.",
    ),
    "master-key-missing": (
        "The server was started without a master key.",
        "Restart it with --key-file or HRONO_MASTER_KEY set.",
    ),
    "master-key-unreadable": (
        "The master key file could not be read.",
        "Check the file's permissions and restart the server.",
    ),
    "not-hrono-database": (
        "The database file is not one hrono made.",
        "Point the server at a hrono database with --db.",
    ),
    "reset-incomplete": (
        "A reset stopped part way.",
        "Run the reset again; it finishes what it started.",
    ),
    "bad-request": (
        "The run was started with something hrono could not use.",
        "Check what was asked for and start it again.",
    ),
    "validation-error": (
        "Some configuration did not pass its checks.",
        "Correct it in Settings and retry.",
    ),
    "not-found": (
        "Something the run needed is no longer there.",
        "Check that the source, model or tree it names still exists.",
    ),
    "conflict": (
        "Another run was changing the same tree.",
        "Wait for it to finish, then retry.",
    ),
    "unavailable": (
        "Something the run needed was busy or still starting.",
        "Retry in a moment.",
    ),
    "unauthorized": (
        "The run was started without valid credentials.",
        "Sign in again and retry.",
    ),
    "login-required": (
        "The run was started without valid credentials.",
        "Sign in again and retry.",
    ),
    "forbidden": (
        "The account that started the run may not do this.",
        "Ask an admin to run it, or to change your role.",
    ),
    "internal-error": (
        "Something inside hrono failed.",
        "Retry. If it fails the same way, the message below is what to report.",
    ),
}


@dataclass(frozen=True)
class Failure:
    """A failed run, for a person: where, on what, why, and what next."""

    stage: str | None
    item: str | None
    says: str
    next: str
    code: str
    raw: str


def explain(
    code: str | None, message: str | None, details: Mapping[str, object] | None
) -> Failure:
    """One failure in plain words, the raw message kept alongside."""
    known = code or "internal-error"
    says, then = SAID.get(known, SAID["internal-error"])
    found = details or {}
    stage = found.get("stage")
    item = found.get("item")
    return Failure(
        stage=str(stage) if stage else None,
        item=str(item) if item else None,
        says=says,
        next=then,
        code=known,
        raw=message or "",
    )
