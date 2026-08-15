"""The ``hrono`` command-line entry point.

Only ``serve`` exists today; it runs the server. The client subcommands
(``recall``, ``sources``, ...) that make this a thin HTTP client land with the
CLI foundation milestone.
"""

from __future__ import annotations

import typer
import uvicorn

app = typer.Typer(add_completion=False)


@app.callback()
def main() -> None:
    """hrono — a hierarchical knowledge base for AI agents."""


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the hrono HTTP server (owns the database and all compute)."""
    uvicorn.run(
        "hrono.server.app:create_app",
        host=host,
        port=port,
        factory=True,
    )
