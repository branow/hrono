"""Render the collapsed agent-facing tree (#078) to a path -> markdown mapping.

Per agent node: its stored brief text as-is (#059/#061 — already ends with its
Caution section; never regenerated), its member references re-attached from the
metadata #102 keeps them in, then a MECHANICAL child listing rendered
from the collapsed tree in code (titles + relative links, no LLM, no
hallucinated links). Leaf nodes list their sections; each section is rendered to
its own file, reassembled byte-identically from its stored passages (#032) with
an address header. Human notes render only when passed (M9 creates them; here
render-if-present). No file I/O — returns a deterministic path -> content map
that #081 materialises into a folder tree.

Every key is RELATIVE and unique (#096). The root's own brief is ``root.md``
and its sections sit beside it at the top level; every other node owns an
id-suffixed directory, so no path can start with "/" (which pathlib would let
reroot the whole export out of the output folder) and no two briefs can land on
one key.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Mapping

from hrono.export.collapse import ExportTree
from hrono.ingest.store import get_content
from hrono.summarize import briefs


def render(
    conn: sqlite3.Connection,
    tree: ExportTree,
    *,
    notes: Mapping[int, str] | None = None,
) -> dict[str, str]:
    """Render ``tree`` to a {file path -> markdown content} mapping."""
    notes = notes or {}
    parent = {
        child: node.node_id
        for node in tree.nodes.values()
        for child in node.children
    }
    files: dict[str, str] = {}

    for node_id in sorted(tree.nodes):
        node = tree.nodes[node_id]
        directory = _directory(node_id, parent, tree.root, conn)
        path = "root.md" if node_id == tree.root else _under(directory, "brief")
        files[path] = _node_markdown(conn, tree, node_id, notes.get(node_id))
        for section_id in node.sections:
            name = _section_name(conn, section_id)
            files[_under(directory, name)] = _section_markdown(conn, section_id)
    return files


def _under(directory: str, name: str) -> str:
    """Join a name under a directory, staying RELATIVE for the root ("")."""
    return f"{directory}/{name}.md" if directory else f"{name}.md"


def _node_markdown(
    conn: sqlite3.Connection,
    tree: ExportTree,
    node_id: int,
    note: str | None,
) -> str:
    node = tree.nodes[node_id]
    parts = [_brief_text(conn, node_id).rstrip()]
    if node.children:
        parts.append("## Children\n")
        parts.append(
            "\n".join(_child_entry(conn, child) for child in node.children)
        )
    elif node.sections:
        parts.append("## Sections\n")
        parts.append(
            "\n".join(
                f"- [{_section_heading(conn, sid)}]"
                f"({_section_name(conn, sid)}.md)"
                for sid in node.sections
            )
        )
    if note:
        parts.append(f"## Notes\n\n{note}")
    if node.level == tree.levels - 1:  # a LEAF: its members are source URIs
        references = _references(conn, node_id)
        if references:
            parts.append(references)
    return "\n\n".join(parts) + "\n"


def _child_entry(conn: sqlite3.Connection, child: int) -> str:
    """One line on an index page: title, link, and what the child holds.

    The summary is there so an agent can choose a branch WITHOUT opening it
    (#204); a wider page is only affordable if each entry says enough to skip
    the ones that do not matter.
    """
    link = f"- [{heading(conn, child)}]({_name(conn, child)}/brief.md)"
    summary = _summary(conn, child)
    return f"{link} — {summary}" if summary else link


def _summary(conn: sqlite3.Connection, node_id: int) -> str:
    """The brief's first sentence of prose that is not already its title."""
    title = heading(conn, node_id)
    prose = " ".join(
        _EMPHASIS.sub("", line.strip())
        for line in _brief_text(conn, node_id).splitlines()
        if line.strip() and not line.lstrip().startswith(_NOT_PROSE)
    )
    for sentence in re.split(r"(?<=[.!?])\s+", prose):
        if sentence and not sentence.startswith(title):
            return _sentence(sentence, _SUMMARY_CHARS)
    return ""


def _references(conn: sqlite3.Connection, node_id: int) -> str:
    """Re-attach a LEAF's member list, which is stored beside its text.

    #102 moved it out of ``briefs.text`` so a lexically dense path list stops
    entering the vector index and FTS as if it were prose; a leaf's list is its
    members' source URIs — provenance the export shows nowhere else — so this is
    where it is put back.

    An UPPER node's list is child NODE IDS, and the caller skips it there for
    two reasons: ``## Children`` already renders those children as titled links,
    so it would be the same thing twice in the same file; and an id is only
    meaningful while that node exists, so a brief written before a rebuild would
    have the map cite topics that have since been retired.

    The caller keys that on the node's LEVEL, not on whether it has children.
    They differ in exactly one state, and it is a real one: #114's childless
    upper node, where a rebuild re-minted the leaf ids and cascaded the root's
    edges away. Such a root has no children to render, so a child-count guard
    called it a leaf and printed its stored ids — three of which were retired on
    the QA corpus. Level is the property the member list actually depends on.
    """
    row = briefs.get(conn, node_id)
    members = json.loads(row["members"]) if row is not None else []
    if not members:
        return ""
    listed = "\n".join(f"- {member}" for member in members)
    return f"## References\n\n{listed}"


def _section_markdown(conn: sqlite3.Connection, section_id: int) -> str:
    row = conn.execute(
        "SELECT path, uri FROM sections WHERE id = ?", (section_id,)
    ).fetchone()
    body = _reassemble(conn, section_id).decode("utf-8", "replace")
    return f"# {row['path']}\n\n<!-- {row['uri']} -->\n\n{body}"


def _reassemble(conn: sqlite3.Connection, section_id: int) -> bytes:
    rows = conn.execute(
        "SELECT content_hash FROM passages WHERE section_id = ? "
        "ORDER BY ordinal, id",
        (section_id,),
    ).fetchall()
    return b"".join(
        get_content(conn, row["content_hash"]) or b"" for row in rows
    )


def _directory(
    node_id: int,
    parent: Mapping[int, int],
    root: int,
    conn: sqlite3.Connection,
) -> str:
    # the chain of names from the root down to this node, root excluded — so
    # only the ROOT is "" and every other node, parentless or not, gets its own
    # id-suffixed directory. A parentless non-root node is a defect the loader
    # refuses, but the renderer stays total: it can never collide two briefs
    # onto one key, and it can never emit a leading slash.
    parts: list[str] = []
    cur = node_id
    while cur != root:
        parts.append(_name(conn, cur))
        above = parent.get(cur)
        if above is None:
            break
        cur = above
    return "/".join(reversed(parts))


def _brief_text(conn: sqlite3.Connection, node_id: int) -> str:
    row = briefs.get(conn, node_id)
    return row["text"] if row is not None else ""


def _stored_title(conn: sqlite3.Connection, node_id: int) -> str | None:
    row = conn.execute(
        "SELECT title FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()
    if row is None:
        return None
    title = row["title"]
    return str(title).strip() or None if title else None


def heading(conn: sqlite3.Connection, node_id: int) -> str:
    """A short title for a node: the operator's if they named it (#156).

    A stored title wins outright. Deriving one from the brief is the default,
    not the rule, and a human who renamed a topic has said something the model
    cannot: what the topic is FOR in this organisation.

    The brief's SHAPE used to leak into navigation (#103): a brief opening with
    a generic ``## Summary`` heading named its export directory ``summary-2``,
    and one opening with a paragraph made the whole paragraph a link title. The
    brief is not at fault for either — a heading is a reasonable way to start a
    summary — so the fix is here rather than a shape rule that would retry and
    flag a perfectly good brief. A boilerplate heading is skipped, markdown
    emphasis is dropped, and only the first sentence is kept.
    """
    stored = _stored_title(conn, node_id)
    if stored:
        return stored
    for line in _brief_text(conn, node_id).strip().splitlines():
        title = _title(line)
        if title and _slug(title) not in _BOILERPLATE:
            return title
    return f"node {node_id}"


def _title(line: str) -> str:
    return _sentence(line, _TITLE_CHARS)


def _sentence(line: str, limit: int) -> str:
    text = _EMPHASIS.sub("", line.lstrip("#").strip())
    sentence = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0].strip()
    if len(sentence) <= limit:
        return sentence
    return sentence[:limit].rsplit(" ", 1)[0].rstrip()  # whole words


def _name(conn: sqlite3.Connection, node_id: int) -> str:
    # append the node id so sibling briefs with the same heading (LLM briefs
    # readily repeat "Overview" etc.) never collide onto one directory and drop
    # a subtree — the same collision-safety sections already have.
    return f"{_slug(heading(conn, node_id)) or 'node'}-{node_id}"


def _section_heading(conn: sqlite3.Connection, section_id: int) -> str:
    row = conn.execute(
        "SELECT path FROM sections WHERE id = ?", (section_id,)
    ).fetchone()
    return row["path"] if row is not None else f"section {section_id}"


def _section_name(conn: sqlite3.Connection, section_id: int) -> str:
    return f"{_slug(_section_heading(conn, section_id))}-{section_id}"


_TITLE_CHARS = 80
_SUMMARY_CHARS = 160
_NOT_PROSE = ("#", "-", "*", "|", ">", "```")
_EMPHASIS = re.compile(r"[*_`]+")
_BOILERPLATE = frozenset(
    {
        "summary",
        "overview",
        "brief",
        "introduction",
        "intro",
        "description",
        "topic",
        "abstract",
        "contents",
        "notes",
    }
)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
