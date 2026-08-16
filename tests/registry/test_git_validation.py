import pytest

from hrono.registry.descriptor import ValidationFailed
from hrono.registry.git_validation import validate_git

TOKEN = "gh-token-donotleak"


def body(**auth: object) -> dict[str, object]:
    return {
        "name": "r",
        "type": "git",
        "url": "https://github.com/acme/repo",
        "auth": auth,
    }


def ok_runner(seen: list) -> object:
    def run(url: str, env: dict, config: list, t: float) -> tuple[int, str]:
        seen.append((url, env, config))
        return 0, ""

    return run


def test_none_auth_passes_when_reachable() -> None:
    validate_git(body(method="none"), run=lambda url, env, cfg, t: (0, ""))


def test_subprocess_env_excludes_the_master_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRONO_MASTER_KEY", "crown-jewel-secret")
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    seen: list = []
    validate_git(body(method="token", token=TOKEN), run=ok_runner(seen))
    _, env, _ = seen[0]
    # the crown-jewel secret is never handed to the git subprocess
    assert "HRONO_MASTER_KEY" not in env
    assert "crown-jewel-secret" not in env.values()
    # git still gets what it legitimately needs, and validation succeeded
    assert env["PATH"] == "/usr/bin:/bin"
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_token_stays_out_of_the_url_and_goes_to_env() -> None:
    seen: list = []
    validate_git(body(method="token", token=TOKEN), run=ok_runner(seen))
    url, env, config = seen[0]
    assert TOKEN not in url
    assert url == "https://github.com/acme/repo"
    assert env["HRONO_GIT_TOKEN"] == TOKEN
    assert any("x-access-token" in arg for arg in config)
    assert all(TOKEN not in arg for arg in config)


def test_ssh_auth_sets_ssh_command_with_key() -> None:
    seen: list = []
    validate_git(
        body(method="ssh", key="PRIVATE-KEY-BODY"), run=ok_runner(seen)
    )
    _, env, _ = seen[0]
    assert "GIT_SSH_COMMAND" in env
    assert "-i " in env["GIT_SSH_COMMAND"]


def test_unreachable_is_rejected() -> None:
    def run(url: str, env: dict, cfg: list, t: float) -> tuple[int, str]:
        return 128, "fatal: unable to access: Could not resolve host"

    with pytest.raises(ValidationFailed) as caught:
        validate_git(body(method="none"), run=run)
    assert "reach" in str(caught.value)


def test_bad_auth_is_rejected() -> None:
    def run(url: str, env: dict, cfg: list, t: float) -> tuple[int, str]:
        return (
            128,
            "remote: Invalid username or password.\nAuthentication failed",
        )

    with pytest.raises(ValidationFailed) as caught:
        validate_git(body(method="token", token=TOKEN), run=run)
    assert "auth" in str(caught.value).lower()


def test_token_never_appears_in_the_rejection_reason() -> None:
    def run(url: str, env: dict, cfg: list, t: float) -> tuple[int, str]:
        return 128, f"fatal: could not read from {url}"

    with pytest.raises(ValidationFailed) as caught:
        validate_git(body(method="token", token=TOKEN), run=run)
    assert TOKEN not in str(caught.value)


def test_timeout_is_treated_as_unreachable() -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_git(
            body(method="none"), run=lambda u, e, c, t: (124, "timed out")
        )
    assert "reach" in str(caught.value)
