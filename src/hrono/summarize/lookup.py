"""Lookups while writing a leaf brief: the tree's files, read-only.

A topic's own condensations say what IT does; what a hard question needs is
often on the other side of a connection - who consumes the message it
publishes, what an endpoint it calls really selects. Traced on the bcreg
corpus (docs/evaluations/2026-10-defines-uses/, rounds 8 and 9), a brief
written without looking described an endpoint from its name and got it
wrong; with lookups it found the real query.

What the writer may see is what exists when a leaf brief is written: condense
runs over every section of the tree before any brief, so every file's text
and condensation, and no brief. They are laid out as files because that is
what a model searches well - ``source/<source>/<path>`` (the text) and
``condensed/<source>/<path>.md`` (its condensations) - behind three tools
shaped like Claude Code's ``Grep``, ``Glob`` and ``Read``. They are answered
from the database: no path outside the tree exists, nothing is written, and
there is no shell.

A lookup into another branch is a dependency the tree's shape does not hold.
The writer ends its brief with ``## Used`` - each looked-up file a statement
came from - and only those, less the topic's own files, are kept: as
``brief_uses`` rows that ``propagate`` follows when such a file changes.
"""

from __future__ import annotations

import fnmatch
import hashlib
import re
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from hrono.llm.tools import Tool, Toolbox
from hrono.registry.collections.trees import sources_of

SOURCE = "source/"
CONDENSED = "condensed/"
MOST_CALLS = 15
MOST_USES = 12  # relations kept per brief: a popular file must not fan out
ANSWER_CHARS = 12_000  # one tool answer at most
GREP_LINES = 20  # matching lines shown per file

INSTRUCTION = """

Before writing, look up what this topic connects to. You have read-only tools \
over the files of the whole system: `source/<source>/<path>` is the text of \
each source file and `condensed/<source>/<path>.md` its condensation. Use \
`Grep` (a regular expression, optionally limited to a path glob) and `Glob` \
to find files, and `Read` to read one. This topic's own files are given \
above under their paths: spend the lookups on the other parts.

First list every connection the topic's files show - each message, queue, \
endpoint, call, table, document or configuration key that names another \
part. Then, for each, find the other side and read what it does there:
- What it sends: the handler that receives it, and what that handler checks, \
saves and does when it fails. A configuration file only tells you a name; \
search for that name until you reach the code that acts on it.
- What it receives: who sends it, and when.
- What it calls: what the called endpoint or function really selects, \
returns or changes - never what its name suggests.
- Records it shares with another part (a table, file or document): the other \
owner's definition, and which of its rules - validations, listeners, \
defaults - apply when this topic writes, and which this topic bypasses.
Mark something "(behaviour not in this topic)" only after you searched for \
it and did not find it.

In the brief, write a file as its repository path (`<source>/<path>`), never \
with the tools' `source/` or `condensed/` prefix.

After the brief, add a section `## Used`: one line for each looked-up file on \
the other side of a connection or shared record that a statement in the \
brief comes from - `- <path>: <the statement>`, with the path exactly as the \
tools print it - and nothing for files you opened but did not use, for \
helpers read only for background, or for this topic's own files. Then a \
section `## Lookups`: one line per connection you listed - \
`- <connection>: <the path found>`, or \
`- <connection>: not found (searched: <patterns>)`."""

TOOLS = (
    Tool(
        "Grep",
        "Search file contents with a regular expression. `path`: optional "
        "glob that limits the files (for example `source/api/src/**`). "
        "`mode`: `files` lists matching paths (the default), `content` shows "
        "matching lines with path and line number. `context`: lines around "
        "each match. `ignore_case`: true for a case-insensitive search.",
        {
            "type": "object",
            "properties": {
                "pattern": {"type": "string"},
                "path": {"type": "string"},
                "mode": {"type": "string", "enum": ["files", "content"]},
                "context": {"type": "integer"},
                "ignore_case": {"type": "boolean"},
            },
            "required": ["pattern"],
        },
    ),
    Tool(
        "Glob",
        "List file paths matching a glob, for example "
        "`source/api/**/config.py`.",
        {
            "type": "object",
            "properties": {"pattern": {"type": "string"}},
            "required": ["pattern"],
        },
    ),
    Tool(
        "Read",
        "Read one file by path, with numbered lines. `offset`: first line "
        "(0-based); `limit`: how many lines.",
        {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "offset": {"type": "integer"},
                "limit": {"type": "integer"},
            },
            "required": ["path"],
        },
    ),
)


@dataclass(frozen=True)
class Files:
    """Every file a leaf brief writer may look at, by its virtual path."""

    texts: Mapping[str, str]

    def grep(
        self,
        pattern: str,
        path: str = "",
        mode: str = "files",
        context: int = 0,
        ignore_case: bool = False,
    ) -> str:
        try:
            found = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
        except re.error as exc:
            return f"Not a regular expression: {exc}."
        out: list[str] = []
        size = 0
        for name in sorted(self.texts):
            if path and not _within(name, path):
                continue
            lines = self.texts[name].splitlines()
            hits = [i for i, line in enumerate(lines) if found.search(line)]
            if not hits:
                continue
            if mode == "content":
                shown: list[str] = []
                for i in hits[:GREP_LINES]:
                    lo, hi = (
                        max(0, i - context),
                        min(len(lines), i + 1 + context),
                    )
                    shown += [
                        f"{name}:{j + 1}: {lines[j]}" for j in range(lo, hi)
                    ]
                out += shown
            else:
                out.append(name)
            size = sum(len(line) + 1 for line in out)
            if size > ANSWER_CHARS:
                out.append("... more: narrow the pattern or the path.")
                break
        return "\n".join(out)[: ANSWER_CHARS + 60] or "No match. " + self.hint()

    def glob(self, pattern: str) -> str:
        names = [name for name in sorted(self.texts) if _within(name, pattern)]
        listed = "\n".join(names[:200])
        if len(names) > 200:
            listed += f"\n... {len(names) - 200} more: narrow the pattern."
        return listed or "No file matches. " + self.hint()

    def read(self, path: str, offset: int = 0, limit: int = 400) -> str:
        text = self.texts.get(path)
        if text is None:
            return "No such file. " + self.hint()
        lines = text.splitlines()[max(0, offset) : max(0, offset) + limit]
        body = "\n".join(
            f"{max(0, offset) + i + 1}\t{line}" for i, line in enumerate(lines)
        )
        return body[:ANSWER_CHARS] or "(empty)"

    def hint(self) -> str:
        roots = sorted({name.split("/")[1] for name in self.texts})
        return (
            "Paths begin source/<source>/ or condensed/<source>/; the sources "
            "are: " + ", ".join(roots[:30])
        )

    def answer(self, name: str, arguments: Mapping[str, object]) -> str:
        """One tool call, answered; a bad argument is said, never raised."""
        try:
            if name == "Grep":
                return self.grep(
                    str(arguments.get("pattern", "")),
                    str(arguments.get("path") or ""),
                    str(arguments.get("mode") or "files"),
                    int(str(arguments.get("context") or 0)),
                    bool(arguments.get("ignore_case")),
                )
            if name == "Glob":
                return self.glob(str(arguments.get("pattern", "")))
            return self.read(
                str(arguments.get("path", "")),
                int(str(arguments.get("offset") or 0)),
                int(str(arguments.get("limit") or 400)),
            )
        except ValueError as exc:
            return f"Bad argument: {exc}."


def _within(name: str, pattern: str) -> bool:
    """A glob match, where a pattern naming a folder takes all below it."""
    pattern = pattern.strip()
    return (
        fnmatch.fnmatchcase(name, pattern)
        or fnmatch.fnmatchcase(name, pattern.rstrip("/") + "/*")
        or (not any(c in pattern for c in "*?[") and name.startswith(pattern))
    )


def files(conn: sqlite3.Connection, tree: str, condense_model: str) -> Files:
    """The tree's sections as files: each one's text and condensations."""
    scoped = sources_of(conn, tree)
    text: dict[str, list[str]] = {}
    condensed: dict[str, list[str]] = {}
    for row in conn.execute(
        "SELECT s.source AS source, s.path AS path, c.body AS body, "
        "d.text AS cond FROM sections s JOIN contents c USING (content_hash) "
        "LEFT JOIN condensations d ON d.content_hash = s.content_hash "
        "AND d.model_name = ? WHERE s.source_type != 'node' "
        "ORDER BY s.source, s.path, s.id",
        (condense_model,),
    ):
        if scoped is not None and row["source"] not in scoped:
            continue
        name = f"{row['source']}/{row['path']}"
        body = row["body"]
        text.setdefault(name, []).append(
            body.decode("utf-8", "replace") if isinstance(body, bytes) else body
        )
        if row["cond"]:
            condensed.setdefault(name, []).append(row["cond"])
    out = {SOURCE + name: "\n".join(parts) for name, parts in text.items()}
    out.update(
        {
            CONDENSED + name + ".md": "\n\n".join(p)
            for name, p in condensed.items()
        }
    )
    return Files(out)


def toolbox(found: Files) -> Toolbox:
    return Toolbox(tools=TOOLS, answer=found.answer, most=MOST_CALLS)


def file_of(path: str) -> str | None:
    """The ``source/path`` a virtual path stands for, or None."""
    for prefix in (SOURCE, CONDENSED):
        if path.startswith(prefix):
            name = path[len(prefix) :]
            if prefix == CONDENSED:
                name = name.removesuffix(".md")
            return name
    return None


@dataclass(frozen=True)
class Use:
    """One looked-up file a statement of the brief came from."""

    file: str  # "<source>/<path>"
    statement: str


def split(
    text: str, own: Iterable[str], known: Mapping[str, str]
) -> tuple[str, tuple[Use, ...]]:
    """The brief without its ``## Used``/``## Lookups`` tail, and its uses.

    A use is kept only when it names a file of the tree that is not one of
    the topic's own (``own``, as ``<source>/<path>``), once per file, at most
    ``MOST_USES``: a looked-up file is a relation, a member already is one.
    """
    head, _, tail = text.partition("\n## Used")
    head = _repository_paths(head)
    used_part = tail.split("\n## Lookups", 1)[0]
    mine = set(own)
    uses: list[Use] = []
    for match in re.finditer(
        r"^\s*-\s*`?([^`\s:]+)`?\s*:\s*(.+)$", used_part, re.M
    ):
        name = file_of(match.group(1))
        if name is None or name in mine or SOURCE + name not in known:
            continue
        if any(use.file == name for use in uses):
            continue
        uses.append(Use(name, match.group(2).strip()))
    return head.rstrip(), tuple(uses[:MOST_USES])


_END = r"(?=[`'\")\s,;]|[.:](?:\s|$)|$)"
_CONDENSED_PATH = re.compile(r"\bcondensed/([\w.\-/]+?)\.md" + _END)
_SOURCE_PATH = re.compile(r"\bsource/([\w.\-/]+?)" + _END)


def _repository_paths(text: str) -> str:
    """The tools' virtual paths, as the repository paths an agent can open."""
    text = _CONDENSED_PATH.sub(lambda m: m.group(1), text)
    return _SOURCE_PATH.sub(lambda m: m.group(1), text)


def signature(conn: sqlite3.Connection, file: str) -> str:
    """What a used file is now: its sections' content hashes, signed.

    A file that is gone signs as the empty set, so its loss reads as change.
    """
    source, _, path = file.partition("/")
    hashes = sorted(
        str(row["content_hash"])
        for row in conn.execute(
            "SELECT content_hash FROM sections WHERE source = ? AND path = ?",
            (source, path),
        )
    )
    return hashlib.sha256(",".join(hashes).encode("utf-8")).hexdigest()


def store_uses(
    conn: sqlite3.Connection, node_id: int, uses: Iterable[Use]
) -> None:
    """Replace a brief's relations with the ones it was just written with."""
    conn.execute("DELETE FROM brief_uses WHERE node_id = ?", (node_id,))
    conn.executemany(
        "INSERT INTO brief_uses(node_id, file, signature, statement) "
        "VALUES (?, ?, ?, ?)",
        [(node_id, u.file, signature(conn, u.file), u.statement) for u in uses],
    )


def changed_uses(
    conn: sqlite3.Connection, node_id: int
) -> tuple[tuple[str, str], ...]:
    """Each used file of a brief whose content moved, with its statement."""
    return tuple(
        (str(row["file"]), str(row["statement"]))
        for row in conn.execute(
            "SELECT file, signature, statement FROM brief_uses "
            "WHERE node_id = ? ORDER BY file",
            (node_id,),
        )
        if signature(conn, str(row["file"])) != row["signature"]
    )


def settle_uses(conn: sqlite3.Connection, node_id: int) -> None:
    """Record each used file as it is now: judged, so not judged again."""
    for row in conn.execute(
        "SELECT file FROM brief_uses WHERE node_id = ?", (node_id,)
    ).fetchall():
        conn.execute(
            "UPDATE brief_uses SET signature = ? "
            "WHERE node_id = ? AND file = ?",
            (signature(conn, str(row["file"])), node_id, row["file"]),
        )
