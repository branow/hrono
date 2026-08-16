from hrono.registry.git_auth import git_auth


def test_token_url_stays_clean_and_secret_goes_to_env() -> None:
    secret = "zzz-secret-value"
    with git_auth(
        "https://github.com/a/b", {"method": "token", "token": secret}
    ) as (url, env, config):
        assert url == "https://github.com/a/b"
        assert secret not in url
        assert env["HRONO_GIT_TOKEN"] == secret
        assert any("x-access-token" in arg for arg in config)
        assert all(secret not in arg for arg in config)


def test_bitbucket_uses_its_token_user() -> None:
    with git_auth(
        "https://bitbucket.org/w/r", {"method": "token", "token": "T"}
    ) as (_, _env, config):
        assert any("x-token-auth" in arg for arg in config)


def test_none_auth_has_no_config_args() -> None:
    with git_auth("file:///x", {"method": "none"}) as (url, _env, config):
        assert url == "file:///x"
        assert config == []


def test_ssh_sets_a_batchmode_command() -> None:
    with git_auth("git@h:r", {"method": "ssh", "key": "K"}) as (_, env, config):
        assert "GIT_SSH_COMMAND" in env
        assert "BatchMode=yes" in env["GIT_SSH_COMMAND"]
        assert config == []
