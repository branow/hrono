"""The migration tests watch the runner build every schema itself."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.template_db import real_migrations


@pytest.fixture(scope="package", autouse=True)
def _real_migrations() -> Iterator[None]:
    with real_migrations():
        yield
