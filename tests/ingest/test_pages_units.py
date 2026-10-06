"""Page sources: the materialized cache read back as ingest units."""

from pathlib import Path

from hrono.ingest.pages import Page, materialize, units


def test_an_empty_page_is_not_a_unit(tmp_path: Path) -> None:
    """The zero-byte rule git files already have (``filter.survey``).

    An empty unit splits to no sections, so ``stored_files`` never records it
    and every later diff reports it "new" again — a batch allocated, the pool
    aged and condense run on every sync of an unchanged corpus, for a page
    with nothing on it.
    """
    cache = tmp_path / "cache"
    materialize(
        cache,
        [
            Page("full.md", b"a page with words on it\n", "v1"),
            Page("hollow.md", b"", "v1"),
        ],
    )

    seen = {unit.path for unit in units({}, cache)}

    assert seen == {"full.md"}
