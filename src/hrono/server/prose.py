"""Model-written text, rendered as the markdown it actually is (#200).

Every brief and every condensation comes back as markdown — the prompts ask for
headings, for bullet groupings, for a `Caution:` section, for identifiers in
backticks — and the dashboard printed all of it into a `<blockquote>`, where
markdown's blank lines collapse and a four-paragraph brief with three bullet
lists reads as one unbroken line. The structure the model was asked to produce
was being thrown away at the last step.

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

from markdown_it import MarkdownIt

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
