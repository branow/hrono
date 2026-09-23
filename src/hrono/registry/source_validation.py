"""Per-source-type validation for the ``sources`` collection (#141).

Dispatch is data-driven, exactly as ``connections`` does it: one validator per
source type, so M8's next reader is a map entry rather than a branch in the
write path. A type with no entry registers WITHOUT a reach check — config is
data you PUT, and a reader that cannot yet be probed is not a reason to refuse
the user's declaration; its sync will fail loudly at ``sync`` time if the
source is wrong.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from hrono.registry.git_validation import validate_git

if TYPE_CHECKING:
    from hrono.registry.descriptor import ValidationContext

Validator = Callable[[dict[str, object], "ValidationContext | None"], None]

VALIDATORS: dict[str, Validator] = {"git": validate_git}


def validate_source(
    config: dict[str, object], context: ValidationContext | None = None
) -> None:
    """Run the validator registered for this source's type, if there is one."""
    validator = VALIDATORS.get(str(config["type"]))
    if validator is None:
        return
    validator(config, context)
