"""The two tools the demo agent has, standing in for its own file tools.

A real agent reads the exported map from a folder and the source files from
its checkout. Here the map is the tree's kept export and the files are what
hrono stored of them, so the server can see, and show, every page and file
the agent opens, and light the topic it is on.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from hrono.db.database import Database
from hrono.demo.steps import Steps
from hrono.export.saved import ROOT_PAGE, Saved
from hrono.naming import name

# A file longer than this is cut, as a file tool would page it.
LONGEST = 40_000
PREVIEW = 600


@dataclass(frozen=True)
class Tool:
    """A tool as every provider describes one: a name, what it does, inputs."""

    name: str
    description: str
    inputs: dict[str, str]

    def schema(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                key: {"type": "string", "description": said}
                for key, said in self.inputs.items()
            },
            "required": list(self.inputs),
        }


TOOLS = (
    Tool(
        "open_topic",
        "Open a page of the hrono map. Start with root.md; then open the "
        "brief.md a page links under ## Children. Returns the page's markdown.",
        {"page": "The page: root.md, or a link such as auth-12/brief.md."},
    ),
    Tool(
        "open_source",
        "Open a source file a leaf page lists under ## Sources. Returns the "
        "file's text.",
        {
            "source": "The source the file is listed under, such as repo.",
            "path": "The file's path, such as src/auth/login.py.",
        },
    ),
)


@dataclass(frozen=True)
class Opened:
    """What a tool returned, and the topic it puts the agent on."""

    text: str
    label: str
    node: int | None


class Library:
    """The tools over one tree, reporting each call as a step."""

    def __init__(
        self, database: Database, tree: str, export: Saved, steps: Steps
    ) -> None:
        self._database = database
        self._tree = tree
        self._export = export
        self._pages = export.pages()
        self._steps = steps

    def call(self, tool: str, args: dict[str, object]) -> str:
        """Run ``tool``; the model gets the text, the page gets a step."""
        with self._database.connect() as conn:
            opened = self._open(conn, tool, args)
        self._steps.add(
            "tool",
            tool=tool,
            args=args,
            label=opened.label,
            node=opened.node,
            size=len(opened.text),
            preview=opened.text[:PREVIEW],
        )
        return opened.text

    def _open(
        self, conn: sqlite3.Connection, tool: str, args: dict[str, object]
    ) -> Opened:
        if tool == "open_topic":
            return self._topic(conn, str(args.get("page", "")))
        if tool == "open_source":
            return self._source(
                conn, str(args.get("source", "")), str(args.get("path", ""))
            )
        return Opened(f"There is no tool called {tool}.", tool, None)

    def _topic(self, conn: sqlite3.Connection, asked: str) -> Opened:
        page = self._page(asked)
        if page is None:
            return Opened(
                f"No page {asked}. Start at {ROOT_PAGE} and open the links "
                "it lists.",
                asked,
                None,
            )
        node = _root(conn, self._tree) if page == ROOT_PAGE else _node(page)
        text = self._export.read(page) or ""
        return Opened(text, name(conn, node) if node else page, node)

    def _page(self, asked: str) -> str | None:
        """The export page ``asked`` names, however much of its path it has.

        A link is relative to the page it is on, and a model often passes it
        as written, so a topic is found by the id its folder ends with.
        """
        asked = asked.strip().lstrip("./")
        if asked in self._pages:
            return asked
        found = _ID.search(asked)
        if found is None:
            return None
        suffix = f"-{found.group(1)}/brief.md"
        return next((p for p in self._pages if p.endswith(suffix)), None)

    def _source(
        self, conn: sqlite3.Connection, source: str, path: str
    ) -> Opened:
        source = source.split(" @ ")[0].strip()
        path = path.strip().strip("`")
        rows = conn.execute(
            "SELECT DISTINCT s.byte_start AS start, s.byte_end AS end, "
            "c.body AS body, m.node_id AS node FROM sections s "
            "JOIN contents c ON c.content_hash = s.content_hash "
            "JOIN node_members m ON m.section_id = s.id "
            "JOIN nodes n ON n.id = m.node_id "
            "WHERE n.tree = ? AND s.source = ? AND s.path = ? "
            "ORDER BY s.byte_start",
            (self._tree, source, path),
        ).fetchall()
        label = f"{path} ({source})"
        if not rows:
            return Opened(
                f"No file {path} in source {source}. Open the paths a leaf "
                "page lists under ## Sources.",
                label,
                None,
            )
        text, reached = "", 0
        for row in rows:
            if int(row["start"]) < reached:
                continue  # a section already covered by the one before it
            text += bytes(row["body"]).decode("utf-8", "replace")
            reached = int(row["end"])
        if len(text) > LONGEST:
            text = text[:LONGEST] + f"\n\n[cut at {LONGEST} characters]"
        return Opened(text, label, int(rows[0]["node"]))


_ID = re.compile(r"-(\d+)(?:/brief\.md)?/?$")


def _node(page: str) -> int | None:
    found = _ID.search(page)
    return int(found.group(1)) if found else None


def _root(conn: sqlite3.Connection, tree: str) -> int | None:
    row = conn.execute(
        "SELECT id FROM nodes WHERE tree = ? ORDER BY level DESC, id LIMIT 1",
        (tree,),
    ).fetchone()
    return int(row["id"]) if row else None
