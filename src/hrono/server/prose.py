"""Model-written text, rendered as the markdown it actually is.

Every brief and every condensation comes back as markdown — the prompts ask for
headings, for bullet groupings, for a `Caution:` section, for identifiers in
backticks. Printed raw into a `<blockquote>`, markdown's blank lines collapse
and a four-paragraph brief with three bullet lists reads as one unbroken line,
throwing away at the last step the structure the model was asked to produce.

**The text is untrusted.** It is whatever a language model wrote about whatever
was in somebody's repository, so `html=False` is the load-bearing setting here:
raw HTML inside it is escaped rather than passed through, and there is no path
by which a summary becomes a script tag. That is also why this is a library
call and not forty lines of regular expressions — the escaping is the part that
has to be right, and markdown-it-py is CommonMark's reference implementation
for Python.

`commonmark` rather than the `gfm`-ish presets: no tables, no autolinking, no
HTML. A brief is prose with lists in it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from markdown_it import MarkdownIt
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict

# Built once. The parser is stateless between `render` calls and building one
# per brief on a page of thirty is thirty times the setup for one answer.
_RENDER = MarkdownIt("commonmark", {"html": False, "linkify": False})


def markdown(text: str | None) -> str:
    """One piece of model-written text as safe HTML.

    Returns "" for nothing at all, so a template can ask without guarding.
    """
    if not text:
        return ""
    return _RENDER.render(text)


def linked(text: str, resolve: Callable[[str], str]) -> str:
    """``markdown``, with every link's target passed through ``resolve``.

    For a page that shows a set of linked files in place: the files link
    to each other by relative path, and in the panel each of those has to
    become a link to the panel's own view of that file.
    """
    return _LINKED.render(text, {"resolve": resolve})


def _relinked(
    renderer: RendererHTML,
    tokens: Sequence[Token],
    idx: int,
    options: OptionsDict,
    env: EnvType,
) -> str:
    token = tokens[idx]
    target = token.attrGet("href")
    if isinstance(target, str):
        token.attrSet("href", env["resolve"](target))
    return renderer.renderToken(tokens, idx, options, env)


_LINKED = MarkdownIt("commonmark", {"html": False, "linkify": False})
_LINKED.add_render_rule("link_open", _relinked)
