import stat
from pathlib import Path

import pytest

from hrono.profile.store import (
    DuplicateProfile,
    Profile,
    Store,
    UnknownProfile,
)


def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "config.toml")


def test_add_persists_and_first_becomes_current(tmp_path: Path) -> None:
    box = store(tmp_path)
    box.add(Profile("prod", "https://prod", "tok-prod", "root"))
    box.add(Profile("dev", "https://dev", "tok-dev"))
    assert list(box.profiles()) == [
        Profile("prod", "https://prod", "tok-prod", "root"),
        Profile("dev", "https://dev", "tok-dev"),
    ]
    assert box.current() is not None
    assert box.current().name == "prod"


def test_add_duplicate_name_raises_without_overwriting(tmp_path: Path) -> None:
    box = store(tmp_path)
    box.add(Profile("prod", "https://prod", "tok-1"))
    with pytest.raises(DuplicateProfile):
        box.add(Profile("prod", "https://other", "tok-2"))
    assert box.profiles()[0].server_url == "https://prod"


def test_use_switches_current_and_persists(tmp_path: Path) -> None:
    box = store(tmp_path)
    box.add(Profile("prod", "https://prod", "t1"))
    box.add(Profile("dev", "https://dev", "t2"))
    box.use("dev")
    assert Store(tmp_path / "config.toml").current().name == "dev"


def test_use_unknown_raises(tmp_path: Path) -> None:
    with pytest.raises(UnknownProfile):
        store(tmp_path).use("ghost")


def test_remove_unknown_raises(tmp_path: Path) -> None:
    with pytest.raises(UnknownProfile):
        store(tmp_path).remove("ghost")


def test_remove_current_clears_the_pointer(tmp_path: Path) -> None:
    box = store(tmp_path)
    box.add(Profile("prod", "https://prod", "t1"))
    assert box.remove("prod") is True
    assert box.current() is None


def test_remove_non_current_keeps_the_pointer(tmp_path: Path) -> None:
    box = store(tmp_path)
    box.add(Profile("prod", "https://prod", "t1"))
    box.add(Profile("dev", "https://dev", "t2"))
    assert box.remove("dev") is False
    assert box.current().name == "prod"


def test_config_file_is_owner_only(tmp_path: Path) -> None:
    box = store(tmp_path)
    box.add(Profile("prod", "https://prod", "t1"))
    mode = stat.S_IMODE((tmp_path / "config.toml").stat().st_mode)
    assert mode == 0o600
    dir_mode = stat.S_IMODE(tmp_path.stat().st_mode)
    assert dir_mode == 0o700


def test_empty_store_reads_as_no_profiles(tmp_path: Path) -> None:
    box = store(tmp_path)
    assert box.profiles() == ()
    assert box.current() is None
