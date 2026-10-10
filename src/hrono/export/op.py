"""The ``export`` op: build a tree's export and keep it for the Export page."""

from __future__ import annotations

from collections.abc import Mapping

from hrono.errors import Conflict
from hrono.export import saved
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext

DEFAULT_LEVELS = 4


def export(job: Job, context: JobContext) -> Mapping[str, object]:
    """Render the tree at the scope's hop limit and store the result."""
    tree = str(job.tree)
    levels = max(2, int(job.scope.get("levels", DEFAULT_LEVELS)))  # type: ignore[call-overload]
    with context.database.connect() as conn:
        built = saved.build(conn, tree, levels)
    if built is None:
        raise Conflict(f"tree not built: {tree}", details={"tree": tree})
    with context.database.write() as conn:
        saved.save(conn, built)
    return {"files": built.files, "levels": levels}


OPS["export"] = export
