"""The dashboard in English or Ukrainian.

English is the source: every string a page shows is written in English in
the template or the code, wrapped in ``_()`` (or ``n_()`` when it carries a
count), and the English text is its own key. Ukrainian lives in
``locales/uk/*.json``, one file per area of the dashboard, merged at load.
A string missing from the catalog is shown in English, never as a key.

The language is the reader's choice, kept in a cookie like the theme, and
read once per request by ``Language`` into a context variable, so code that
builds a message deep in a view (a flash, a label) translates it without the
request being threaded down to it. The API and the CLI stay English.
"""

from __future__ import annotations

import json
from contextvars import ContextVar
from datetime import datetime
from functools import cache
from http.cookies import SimpleCookie
from pathlib import Path

from starlette.types import ASGIApp, Receive, Scope, Send

# code -> the label the switcher shows
LANGS = {"en": "EN", "uk": "UA"}
DEFAULT = "en"
COOKIE = "hrono_lang"
LOCALES = Path(__file__).parent / "locales"

_current: ContextVar[str] = ContextVar("hrono_lang", default=DEFAULT)

Entry = str | list[str]


def current() -> str:
    """The language of the page being rendered."""
    return _current.get()


def other(lang: str) -> str:
    """The language the switcher offers from ``lang``."""
    return "uk" if lang == "en" else "en"


@cache
def catalog(lang: str = "uk") -> dict[str, Entry]:
    """Every translation for ``lang``, from all its files.

    Two files may carry the same English string only with the same
    translation; a conflict is a mistake in the catalog, raised at load.
    """
    merged: dict[str, Entry] = {}
    for path in sorted((LOCALES / lang).glob("*.json")):
        for key, value in json.loads(path.read_text("utf-8")).items():
            if key in merged and merged[key] != value:
                raise ValueError(f"{path.name}: {key!r} translated twice")
            merged[key] = value
    return merged


def gettext(text: str, /, context: str = "", **values: object) -> str:
    """``text`` in the page's language, with ``{name}`` slots filled.

    ``context`` tells apart one English word that Ukrainian says two ways
    ("Name" of a tree is «Назва», of a person «Ім'я»); its catalog key is
    ``"<context>::<text>"``.
    """
    said = text
    if current() != DEFAULT:
        found = catalog(current()).get(
            f"{context}::{text}" if context else text
        )
        if isinstance(found, str):
            said = found
    return said.format(**values) if values else said


def ngettext(count: int, one: str, many: str, /, **values: object) -> str:
    """A phrase that agrees with ``count``, which fills its ``{n}`` slot.

    English has two forms. Ukrainian has three (одна тема, дві теми, п'ять
    тем), kept in the catalog as a list under the key ``"<one>|<many>"``.
    """
    form = one if count == 1 else many
    if current() != DEFAULT:
        found = catalog(current()).get(f"{one}|{many}")
        if isinstance(found, list) and len(found) == 3:
            form = found[_slavic(count)]
    return form.format(n=count, **values)


def _slavic(count: int) -> int:
    """Which of the three Ukrainian forms a count takes."""
    tens, ones = count % 100, count % 10
    if ones == 1 and tens != 11:
        return 0
    if 2 <= ones <= 4 and not 12 <= tens <= 14:
        return 1
    return 2


def chosen(cookie_header: str) -> str:
    """The language a Cookie header asks for, or the default."""
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(cookie_header)
    except Exception:  # noqa: BLE001 - a malformed cookie is no choice
        return DEFAULT
    picked = jar[COOKIE].value if COOKIE in jar else DEFAULT
    return picked if picked in LANGS else DEFAULT


class Language:
    """Set each request's language from its cookie, for everything under it.

    Plain ASGI rather than ``BaseHTTPMiddleware``, so the value is set in the
    same context the route, its threadpool work and a streamed body run in.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self, scope: Scope, receive: Receive, send: Send
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        header = next(
            (
                value.decode("latin-1")
                for name, value in scope.get("headers", [])
                if name == b"cookie"
            ),
            "",
        )
        token = _current.set(chosen(header))
        try:
            await self.app(scope, receive, send)
        finally:
            _current.reset(token)


# Ukrainian months as a date beside a time reads them: "09 жовт 16:50".
_MONTHS = (
    "січ", "лют", "бер", "квіт", "трав", "черв",
    "лип", "серп", "вер", "жовт", "лист", "груд",
)  # fmt: skip


def moment(at: datetime) -> str:
    """A day and a time, short: `09 Oct 16:50`, `09 жовт 16:50`."""
    if current() == "uk":
        return f"{at:%d} {_MONTHS[at.month - 1]} {at:%H:%M}"
    return at.strftime("%d %b %H:%M")
