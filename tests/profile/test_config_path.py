from pathlib import Path

import pytest

from hrono.profile import store
from hrono.profile.store import config_path


def test_hrono_home_wins_on_any_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HRONO_HOME", str(tmp_path))
    for platform in ("darwin", "linux", "win32"):
        monkeypatch.setattr(store.sys, "platform", platform)
        assert config_path() == tmp_path / "config.toml"


def test_unix_uses_the_home_dotfolder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HRONO_HOME", raising=False)
    for platform in ("darwin", "linux"):
        monkeypatch.setattr(store.sys, "platform", platform)
        assert config_path() == Path.home() / ".hrono" / "config.toml"


def test_windows_uses_the_appdata_config_dir(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HRONO_HOME", raising=False)
    monkeypatch.setattr(store.sys, "platform", "win32")
    seen: dict[str, object] = {}

    def fake_user_config_dir(appname: str, *, roaming: bool = False) -> str:
        seen["appname"] = appname
        seen["roaming"] = roaming
        return "C:\\Users\\me\\AppData\\Roaming\\" + appname

    monkeypatch.setattr(store, "user_config_dir", fake_user_config_dir)
    result = config_path()
    assert seen == {"appname": "hrono", "roaming": True}
    assert result == (
        Path("C:\\Users\\me\\AppData\\Roaming\\hrono") / "config.toml"
    )
