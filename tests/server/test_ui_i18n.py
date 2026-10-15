"""The dashboard is whole in both languages.

Three checks keep it so. Every piece of text a template shows is wrapped for
translation (``_()`` or ``n_()``), so nothing is English by omission. Every
wrapped string has its Ukrainian, with the same ``{slots}``. And the switch
itself works: the cookie changes the page, and the catalog loads.
"""

from __future__ import annotations

import ast
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from hrono.server import i18n

SERVER = Path(__file__).parents[2] / "src" / "hrono" / "server"
TEMPLATES = SERVER / "templates"
READ_ATTRS = frozenset(
    {"title", "data-tip", "placeholder", "aria-label", "alt", "label"}
)
# Words that read the same in both languages: names and units.
SAME = frozenset({"hrono", "EN", "UA", "KB", "MB", "B", "ID", "Git", "git"})
JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
COMMENT = re.compile(r"\{#.*?#\}", re.S)
WORD = re.compile(r"[A-Za-z][A-Za-z'’-]+")


class Bare(HTMLParser):
    """Text and readable attributes a template writes in plain English."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in ("script", "style", "code", "kbd", "pre", "svg"):
            self._skip += 1
        for name, value in attrs:
            if name in READ_ATTRS and value:
                self._check(value)

    def handle_startendtag(self, tag: str, attrs: list) -> None:
        for name, value in attrs:
            if name in READ_ATTRS and value:
                self._check(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "code", "kbd", "pre", "svg"):
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self._check(data)

    def _check(self, text: str) -> None:
        words = [w for w in WORD.findall(text) if w not in SAME]
        if words:
            self.found.append(" ".join(text.split()))


def _bare(path: Path) -> list[str]:
    source = COMMENT.sub("", path.read_text("utf-8"))
    parser = Bare()
    parser.feed(JINJA.sub("\x00", source))
    return parser.found


@pytest.mark.parametrize(
    "template", sorted(p.name for p in TEMPLATES.glob("*.html"))
)
def test_a_template_shows_no_unwrapped_english(template: str) -> None:
    assert _bare(TEMPLATES / template) == []


def _wrapped() -> set[tuple[str, ...]]:
    """Every literal passed to ``_()`` or ``n_()``, in templates and code."""
    found: set[tuple[str, ...]] = set()
    string = r"(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')"
    single = re.compile(
        r"(?<![\w.])_\(\s*" + string + r"(?:\s*,\s*context=" + string + ")?"
    )
    plural = re.compile(
        r"(?<![\w.])n_\(\s*[^,()]+(?:\([^()]*\))?\s*,\s*"
        + string
        + r"\s*,\s*"
        + string
    )
    for path in [*TEMPLATES.glob("*.html"), *SERVER.rglob("*.py")]:
        text = path.read_text("utf-8")
        for match in single.finditer(text):
            said = ast.literal_eval(match.group(1))
            if match.group(2):
                said = f"{ast.literal_eval(match.group(2))}::{said}"
            found.add((said,))
        for match in plural.finditer(text):
            found.add(
                (
                    ast.literal_eval(match.group(1)),
                    ast.literal_eval(match.group(2)),
                )
            )
    return found


def _slots(text: str) -> set[str]:
    return set(re.findall(r"\{(\w*)\}", text))


def test_every_wrapped_string_has_its_ukrainian() -> None:
    uk = i18n.catalog("uk")
    missing = []
    for wrapped in sorted(_wrapped()):
        entry = uk.get("|".join(wrapped))
        whole = (
            isinstance(entry, str)
            if len(wrapped) == 1
            else isinstance(entry, list) and len(entry) == 3
        )
        if not whole:
            missing.append("|".join(wrapped))
    assert missing == []


def test_a_translation_keeps_the_slots_of_its_english() -> None:
    wrong = []
    for key, entry in i18n.catalog("uk").items():
        english = _slots(key.split("|")[0]) | _slots(key.split("|")[-1])
        for form in [entry] if isinstance(entry, str) else entry:
            if _slots(form) != english:
                wrong.append(key)
    assert wrong == []


@pytest.mark.parametrize(
    ("count", "form"),
    [(1, 0), (21, 0), (2, 1), (4, 1), (23, 1), (5, 2), (11, 2), (12, 2)],
)
def test_ukrainian_counts_take_three_forms(count: int, form: int) -> None:
    assert i18n._slavic(count) == form


def test_the_cookie_picks_the_language() -> None:
    assert i18n.chosen("hrono_lang=uk") == "uk"
    assert i18n.chosen("hrono_lang=fr") == "en"
    assert i18n.chosen("") == "en"
