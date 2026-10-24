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

Grep finds only the words a writer guesses, and the other side of a
connection often uses other ones: bcreg's old payment listener reads
`entity.filings`, while the pay API sends to `BUSINESS_PAY_TOPIC`, so the
writer found only a test sender and concluded the shapes match (round 15).
``Search`` ranks the files by what they do - their condensations, embedded
with the tree's embedding model: a plain-words question finds a sender
named differently.

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
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

import numpy

from hrono.llm.tools import Tool, Toolbox
from hrono.recall import query
from hrono.registry.collections.trees import sources_of

# a test file is left out of a lookup by meaning: it reads like a question
# about its code and would take the slots the code should have
TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.\w+$|\.(spec|test)\.\w+$"
)
SOURCE = "source/"
CONDENSED = "condensed/"
MOST_CALLS = 15
MOST_USES = 12  # relations kept per brief: a popular file must not fan out
ANSWER_CHARS = 12_000  # one tool answer at most
OWN = (
    "This is one of this topic's own files: its condensation is given above. "
    "Not counted; spend the lookups on the other parts."
)
GREP_LINES = 20  # matching lines shown per file
SEARCH_FILES = 10  # files a Search answers with
GREP_ALSO = 5  # files close in meaning, shown under a grep's hits
MEANING_CHARS = 2000  # of a condensation, embedded for Search
_VECTORS: dict[tuple[str, str], numpy.ndarray] = {}  # (model, text hash)
Encode = Callable[[list[str]], Sequence[Sequence[float]]]

INSTRUCTION = """

Before writing, look up what this topic connects to: your first replies are \
lookups, and the brief is your last reply, written after them, never instead \
of them. A connection your Lookups section calls not searched sends the \
brief back to be written again. You have read-only tools \
over the files of the whole system: `source/<source>/<path>` is the text of \
each source file and `condensed/<source>/<path>.md` its condensation. Use \
`Grep` (a regular expression, optionally limited to a path glob) and `Glob` \
to find files, and `Read` to read one. To learn what another file does, \
read its condensation first: the whole file - its checks, listeners and \
defaults - in one lookup; open its source for an exact line. This topic's \
own files are given above under their paths: spend the lookups on the other \
parts.

First list every connection the topic's files show - each message, queue, \
endpoint, call, table, document or configuration key that names another \
part. Then, for each, find the other side and read what it does there, in \
this order, because the lookups run out:
- What it receives: who sends it in the running system - never a test, \
fixture or script - and when, and whether what that sender sends is what \
this topic reads. The sender often names things differently: use `Search`, \
when it is offered, with plain words for what the sender does (for example \
`publishes payment completed events`).
- Records it saves through another part's model or shares with another part \
(a table, file or document): the other owner's definition, and which of its \
rules - validations, listeners, defaults - run when this topic writes, and \
which this topic bypasses. What a save sets on its own - a status a listener \
derives, a default - is this topic's effect: write it in the step that \
saves (`save() -> <model>'s <listener> sets <field> to <value>`), never as \
"behaviour not in this topic".
- What it sends: the handler that receives it, and what that handler checks, \
saves and does when it fails. A configuration file only tells you a name; \
search for that name until you reach the code that acts on it.
- What it calls: what the called endpoint or function really selects, \
returns or changes - never what its name suggests.
Where either side picks where the work goes - a topic, queue, route or \
handler chosen per type, product or status by a function, map or \
configuration - read that choice and copy the whole mapping into the brief \
(`ORDER -> orders-topic, REFUND -> refunds-topic, else -> default-topic`), \
never only the function's name.
- Another part that does the same job (an old and a new path, two consumers \
of the same work): read it, and the sender it gets the work from, and \
compare them step by step - which checks, reviews and duplicate guards each \
has, and whether this topic would accept what the other's sender sends.
The other side often lives in another source than this topic's: search \
every source (`condensed/**`), never only this topic's own. Mark something \
"(behaviour not in this topic)" only after you searched for it and did not \
find it.

In the brief, write a file as its repository path (`<source>/<path>`), never \
with the tools' `source/` or `condensed/` prefix.

After the brief, add a section `## Used`: one line for each looked-up file on \
the other side of a connection or shared record that a statement in the \
brief comes from - `- <path>: <the statement>`, with the path exactly as the \
tools print it - and nothing for files you opened but did not use, for \
helpers read only for background, or for this topic's own files. Then a \
section `## Lookups`: one line per connection you listed - \
`- <connection>: <the path found>`, or \
`- <connection>: not found (searched: <patterns>)` - and always one line \
`- sender: <the live sender's path, for each thing this topic receives>`, \
or `- sender: not found (searched: <patterns and Search queries>)`, or \
`- sender: none (<why: it receives nothing>)`. A brief without the sender \
line is sent back."""

# a connection the writer's own account says it never searched: "not
# searched", "not looked up", "not read", "no lookup" - but not "not found
# (searched: ...)", which is a search that came back empty
_UNSEARCHED = re.compile(
    r"\bnot (?:searched|looked up|read|opened|pursued)\b"
    r"|\bno (?:lookups?|searches)\b",
    re.IGNORECASE,
)


_SENDER = re.compile(r"-\s*\**`?sender\b", re.IGNORECASE)
NO_SENDER = (
    "- sender: missing (who sends this topic what it receives, in the "
    "running system: search by words and by meaning)"
)


def unsearched(text: str) -> tuple[str, ...]:
    """The lines of a brief's ``## Lookups`` that admit no search was made.

    A missing ``sender`` line is one: on bcreg the old payment listener's
    writer found only a test sender by grep and never looked for the live
    one, so its brief said the shapes match (round 15).
    """
    lines = [line.strip() for line in accounting(text).splitlines()]
    missing = [line for line in lines if line and _UNSEARCHED.search(line)]
    if not any(_SENDER.match(line) for line in lines):
        missing.append(NO_SENDER)
    return tuple(missing)


def again(missing: Iterable[str], looked: bool) -> str:
    """What a brief is told when it is asked to look once more."""
    if not looked:
        said = "wrote the brief without a single lookup"
    else:
        said = "left these connections unsearched:\n" + "\n".join(missing)
    return (
        f"\n\nYour last reply {said}\n\nLook them up first: for each "
        "connection, search for the other side and read what it does, then "
        "write the whole brief, with its Used and Lookups sections."
    )


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


SEARCH = Tool(
    "Search",
    "Find files by what they do, when you do not know the words they use - "
    "a sender, receiver or caller that names things differently from this "
    "topic. `query`: plain words (for example `publishes payment completed "
    "events`). Returns the closest files, best first, tests left out, each "
    "with the first line of its condensation.",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)


@dataclass(frozen=True)
class Meanings:
    """The tree's source passages as unit vectors, each with its file."""

    names: tuple[str, ...]  # the file of each row, as ``<source>/<path>``
    matrix: numpy.ndarray
    encode: Encode

    def near(self, question: str) -> list[str]:
        """The files closest to ``question``, best first, each once."""
        if not self.names:
            return []
        asked = numpy.atleast_2d(
            numpy.asarray(
                self.encode(query.sentences(question)), dtype=numpy.float64
            )
        )
        norms = numpy.linalg.norm(asked, axis=1)
        asked = asked[norms > 0.0] / norms[norms > 0.0, None]
        if len(asked) == 0:
            return []
        cosine = (self.matrix @ asked.T).max(axis=1)
        out: list[str] = []
        for row in numpy.argsort(-cosine, kind="stable"):
            if self.names[row] not in out:
                out.append(self.names[row])
            if len(out) == SEARCH_FILES:
                break
        return out


def meanings(texts: Mapping[str, str], encode: Encode, model: str) -> Meanings:
    """The tree's condensations, ready to rank by what each file does.

    A question in plain words is matched against the condensations, not the
    code: on bcreg, the code's own embeddings never put the pay API's sender
    in the top ten for "publishes payment completed events", and its
    condensations put both of its senders there. Each vector is kept for the
    process, so the next brief embeds only what changed.
    """
    names = sorted(
        name.removeprefix(CONDENSED).removesuffix(".md")
        for name in texts
        if name.startswith(CONDENSED) and not TEST_PATH.search(name)
    )
    bodies = [texts[CONDENSED + name + ".md"][:MEANING_CHARS] for name in names]
    keys = [
        (model, hashlib.sha256(body.encode()).hexdigest()) for body in bodies
    ]
    todo = sorted({k for k in keys if k not in _VECTORS})
    if todo:
        new = {k: body for k, body in zip(keys, bodies, strict=True)}
        for k, vector in zip(todo, encode([new[k] for k in todo]), strict=True):
            _VECTORS[k] = numpy.asarray(vector, dtype=numpy.float64)
    if not names:
        return Meanings((), numpy.zeros((0, 0)), encode)
    matrix = numpy.vstack([_VECTORS[k] for k in keys])
    norms = numpy.linalg.norm(matrix, axis=1, keepdims=True)
    return Meanings(
        tuple(names), matrix / numpy.where(norms == 0.0, 1.0, norms), encode
    )


@dataclass(frozen=True)
class Files:
    """Every file a leaf brief writer may look at, by its virtual path."""

    texts: Mapping[str, str]
    meanings: Meanings | None = None  # Search by meaning, when embedded

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
        found_text = "\n".join(out)[: ANSWER_CHARS + 60]
        if mode == "content":
            # a matched line shows one function; what runs on every save of
            # the same record is shown with it, as a slice's read does
            for name in sorted({line.split(":", 1)[0] for line in out}):
                whole = (
                    name
                    if name.startswith(CONDENSED)
                    else CONDENSED + name.removeprefix(SOURCE) + ".md"
                )
                if whole in self.texts:
                    hooks = _on_save(self.texts[whole])
                    if hooks:
                        found_text += f"\n{name} also runs on save:\n{hooks}"
        return (found_text or "No match. " + self.hint()) + self._also(
            pattern, {line.split(":", 1)[0] for line in out}
        )

    def _also(self, pattern: str, shown: set[str]) -> str:
        """The files closest in meaning to a grep's words, not among its hits.

        Words and meaning are one search: the other side of a connection
        often uses other words, and a grep alone never shows it.
        """
        words = " ".join(re.findall(r"[A-Za-z][A-Za-z0-9]+", pattern))
        if self.meanings is None or not words:
            return ""
        hits = {file_of(name) for name in shown}
        close = [n for n in self.meanings.near(words) if n not in hits]
        if not close:
            return ""
        return "\n\nClose in meaning, in other words:\n" + self._listed(
            close[:GREP_ALSO]
        )

    def _listed(self, names: Iterable[str]) -> str:
        """Each file with the first line of its condensation."""
        lines = []
        for name in names:
            condensed = self.texts.get(CONDENSED + name + ".md", "")
            first = next(
                (line.strip() for line in condensed.splitlines() if line),
                "",
            )
            lines.append(SOURCE + name + (f" - {first[:200]}" if first else ""))
        return "\n".join(lines)

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
        every = text.splitlines()
        lines = every[max(0, offset) : max(0, offset) + limit]
        body = "\n".join(
            f"{max(0, offset) + i + 1}\t{line}" for i, line in enumerate(lines)
        )[:ANSWER_CHARS]
        whole = CONDENSED + path.removeprefix(SOURCE) + ".md"
        partial = (
            offset > 0 or len(lines) < len(every) or len(body) >= ANSWER_CHARS
        )
        if partial and path.startswith(SOURCE) and whole in self.texts:
            # a slice shows one function; what else the file does on the
            # same record - a listener, a default - sits outside it
            first, last = max(0, offset) + 1, max(0, offset) + len(lines)
            body += (
                f"\n(lines {first}-{last} of {len(every)}; {whole} covers "
                "the whole file)"
            )
            # and what runs on every save is shown whatever the slice: the
            # bcreg writer read a model's query twice and never its listener
            hooks = _on_save(self.texts[whole])
            if hooks:
                body += "\nThis file also runs on save:\n" + hooks
        return body or "(empty)"

    def search(self, question: str) -> str:
        if self.meanings is None:
            return "Search by meaning is not available here; use Grep."
        listed = self._listed(self.meanings.near(question))
        return listed or "No file found. " + self.hint()

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
            if name == "Search":
                return self.search(str(arguments.get("query", "")))
            return self.read(
                str(arguments.get("path", "")),
                int(str(arguments.get("offset") or 0)),
                int(str(arguments.get("limit") or 400)),
            )
        except ValueError as exc:
            return f"Bad argument: {exc}."


_HOOK = re.compile(
    r"\blisten|\bbefore_(?:insert|update|save|delete|flush)\b"
    r"|\bafter_(?:insert|update|save|delete|commit)\b|\bpre_save\b"
    r"|\bpost_save\b|@validates\b|\bsignal",
    re.IGNORECASE,
)


def _on_save(condensation: str) -> str:
    """The lines of a file's condensation about what runs when it is saved.

    A save hook's rules sit on lines naming the hook (``receive_before_change``
    after the line that says it listens on before_update), so a line naming a
    hooked function is kept too.
    """
    lines = condensation.splitlines()
    hooked = {
        name
        for line in lines
        if _HOOK.search(line)
        for name in re.findall(r"`(\w+)`", line)
    }
    kept = [
        line
        for line in lines
        if _HOOK.search(line)
        or any(re.search(rf"\b{re.escape(n)}\b", line) for n in hooked)
    ]
    return "\n".join(kept)[:3000]


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


def toolbox(found: Files, own: Iterable[str] = ()) -> Toolbox:
    """The lookup tools over ``found``; reading ``own`` files is free."""
    mine = {SOURCE + name for name in own} | {
        CONDENSED + name + ".md" for name in own
    }

    def free(name: str, arguments: Mapping[str, object]) -> str | None:
        if name == "Read" and str(arguments.get("path", "")) in mine:
            return OWN
        return None

    tools = TOOLS if found.meanings is None else (*TOOLS, SEARCH)
    return Toolbox(tools=tools, answer=found.answer, most=MOST_CALLS, free=free)


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


def accounting(text: str) -> str:
    """The writer's ``## Lookups`` section: each connection, found or not."""
    _, found, tail = text.partition("\n## Lookups")
    return tail.strip() if found else ""


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
        # the brief writes repository paths, and writers carry that into
        # Used: v10 lost 16 of 26 relations to the missing prefix
        name = file_of(match.group(1)) or match.group(1)
        if name in mine or SOURCE + name not in known:
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
