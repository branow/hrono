from pathlib import Path

import pytest

from hrono.db.lock import exclusive
from hrono.errors import Conflict


def test_a_second_holder_is_refused_with_a_clear_message(
    tmp_path: Path,
) -> None:
    db = tmp_path / ".hrono" / "hrono.db"
    with exclusive(db), pytest.raises(Conflict) as raised, exclusive(db):
        pass
    assert "already using" in raised.value.message
    assert str(db) in raised.value.message


def test_the_lock_is_released_when_the_block_ends(tmp_path: Path) -> None:
    db = tmp_path / ".hrono" / "hrono.db"
    with exclusive(db):
        pass
    with exclusive(db):
        pass


def test_a_different_database_locks_independently(tmp_path: Path) -> None:
    with exclusive(tmp_path / "one.db"), exclusive(tmp_path / "two.db"):
        pass


def test_the_lockfile_sits_next_to_the_database(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "hrono.db"
    with exclusive(db):
        assert (tmp_path / "nested" / "hrono.db.lock").exists()
