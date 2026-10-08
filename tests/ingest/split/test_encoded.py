"""Encoded data — base64, minified bundles — is never stored as a section."""

import base64
import random
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest import store
from hrono.ingest.split.encoded import RUN, encoded
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync
from tests.context import job_context
from tests.ingest.test_split_op import job, make_repo, register

_BLOB = base64.b64encode(random.Random(7).randbytes(30_000)).decode()
_CODE = "".join(
    f"def handler_{i}(request):\n    return respond(request, {i})\n\n"
    for i in range(120)
)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        pytest.param(_BLOB.encode(), True, id="base64"),
        pytest.param(_CODE.encode(), False, id="code"),
        pytest.param(b"", False, id="empty"),
        pytest.param(
            ("see https://example.com/" + "a" * 120 + " for more\n").encode()
            * 20,
            False,
            id="long-urls",
        ),
        pytest.param(
            b"x" * (RUN - 1) + b" " + b"y" * (RUN - 1), False, id="under-run"
        ),
        pytest.param(b"x" * RUN + b" " * (RUN - 1), True, id="just-over"),
        pytest.param(b"x" * RUN + b" " * RUN, False, id="exactly-half"),
    ],
)
def test_encoded_is_long_whitespace_free_runs_over_half(
    body: bytes, expected: bool
) -> None:
    assert encoded(body) is expected


def test_a_split_stores_the_code_and_drops_the_inlined_blob(
    tmp_path: Path,
) -> None:
    # the BC Registries shape: an HTML template whose image is inlined
    # base64, next to a plain module
    page = (
        "<html><body>\n<h1>Certificate</h1>\n"
        f'<img src="data:image/png;base64,{_BLOB}">\n</body></html>\n'
    )
    url = make_repo(
        tmp_path / "remote", {"seal.html": page, "handlers.py": _CODE}
    )
    db = Database.at(tmp_path / "hrono.db")
    with db.connect() as conn:
        register(conn, "repo", url)
    context = job_context(db, tmp_path)
    sync(job("sync", "repo"), context)

    split_source(job("split", "repo"), context)

    with db.connect() as conn:
        sections = store.list_sections(conn, "repo")
        stored = [
            (s["path"], store.get_content(conn, s["content_hash"]) or b"")
            for s in sections
        ]
    assert "handlers.py" in {path for path, _ in stored}
    assert not [path for path, body in stored if encoded(body)]
    seal = b"".join(body for path, body in stored if path == "seal.html")
    assert len(seal) < RUN  # the heading may stay; the 40 KB image may not
    db.close()
