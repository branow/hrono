---
id: 037
title: Store client config in the OS-correct directory on Windows
priority: low
size: small
depends_on: [036]
spec_refs: [implementation-notes.md, os-correct-config-dir]
---

## Context
Promoted from a stakeholder backlog request (spec gap found in review). The
client profile config resolves to `HRONO_HOME` else `~/.hrono/config.toml`. A
home dot-folder is the Unix/macOS convention, but on Windows per-user app config
belongs in `%APPDATA%\hrono`, not a dot-folder in the profile root. This only
concerns the CLIENT profile config location (the server DB stays project-local
at `./.hrono/hrono.db`). Depends on #036 because that rename moves
`context/store.py` -> `profile/store.py` and its `config_path()`; do this after,
on the renamed module, to avoid conflicting on the same function.

Settled by PO (open question from the request):
- macOS and Linux KEEP the Unix dotfolder `~/.hrono` (CLI-tool convention -
  kubectl/aws/gh style, and what the spec chose); only Windows is special-cased.
  So this is a Windows-correctness fix, not a broad relocation.

## Description
Change the profile `config_path()` resolution to:
1. `HRONO_HOME` if set (highest priority, unchanged - the escape hatch).
2. Else on **Windows**: the OS user-config dir (`%APPDATA%\hrono\config.toml`),
   resolved via `platformdirs` (add the dep) rather than hand-rolling env
   lookups.
3. Else (macOS/Linux): `~/.hrono/config.toml` exactly as today (unchanged).

Preserve the owner-only permission posture where the OS supports it: the `0700`
dir / `0600` file handling stays on POSIX; on Windows, POSIX mode bits do not
apply the same way - do not crash, and document the platform difference (the
file lands in the per-user AppData dir which is already user-scoped). Keep the
write path and format identical; only the default location changes, and only on
Windows.

## Acceptance criteria
- [ ] With `HRONO_HOME` unset on Windows, the config resolves under
      `%APPDATA%\hrono` (via platformdirs), not a home dot-folder.
- [ ] On macOS/Linux the location is unchanged (`~/.hrono/config.toml`), and
      `HRONO_HOME` still overrides everywhere.
- [ ] Owner-only permissions are preserved on POSIX (0600 file / 0700 dir); on
      Windows the write does not crash and the file lands in the user-scoped
      AppData dir (document the perms difference).
- [ ] Regression-grade tests: the resolver returns the AppData path when the
      platform is Windows (mock the platform/`platformdirs`) and the `~/.hrono`
      path otherwise, with `HRONO_HOME` winning in both; the POSIX perms test
      still passes.
- [ ] `ruff format`, `ruff check --fix`, `pytest` all clean; work committed.

## Out of scope
- Relocating the server database (it is intentionally project-local
  `./.hrono/hrono.db`, not the user config dir).
- Changing macOS/Linux locations (deliberately kept as `~/.hrono`).
- XDG `~/.config` migration on Linux (kept as `~/.hrono` to match the spec).

## Review log
- 2026-08-16 PO: triaged from the stakeholder `os-correct-config-dir` request.
  Low priority (platform polish; Unix - the primary platform - is fine today;
  Windows support plausible but not blocking). Settled: Windows-only special-case
  via platformdirs, Unix keeps `~/.hrono`, HRONO_HOME wins. Depends on #036 (the
  rename moves the module it edits). Scope is the client config path only, not
  the server DB.

## dev — 2026-08-16

Changed `profile.store.config_path()` (renamed module from #036) to resolve
per-OS: `HRONO_HOME` wins everywhere; else on Windows the per-user config dir
`%APPDATA%\hrono\config.toml` via `platformdirs.user_config_dir("hrono",
roaming=True)`; else (macOS/Linux) `~/.hrono/config.toml` unchanged. Added the
`platformdirs>=4.2,<5` dep (lockfile committed) rather than hand-rolling env
lookups.

Permissions: `_write` keeps 0700 dir / 0600 file on POSIX, now guarded by
`os.name == "posix"` so Windows skips POSIX mode bits cleanly (the file lands in
the user-scoped AppData dir) — documented in the function docstring. Write path
and format are otherwise identical; only the default location changes, only on
Windows.

Verified: real CLI on macOS still writes to HRONO_HOME/`~/.hrono` at 0600
(unchanged); `config_path()` on the real platform returns `~/.hrono/config.toml`.
Tests (platform mocked via `store.sys.platform` + a fake `user_config_dir`):
HRONO_HOME wins on darwin/linux/win32; darwin/linux -> `~/.hrono`; win32 ->
AppData path with `roaming=True` and appname "hrono"; the existing POSIX 0600/0700
perms test still passes. Gate clean: ruff, pytest 359.

## qa — 2026-08-16 — PASS -> po-review

Re-ran the gate MYSELF: `ruff format --check` + `ruff check` clean, `pytest` 359
passed; the ticket's `tests/profile/test_config_path.py` = 3 passed. Then drove
every `config_path()` branch directly, not on dev's word:

- `HRONO_HOME` set -> `<HOME>/config.toml` on darwin, linux, AND win32 (escape
  hatch wins everywhere).
- No HRONO_HOME on darwin and linux -> `~/.hrono/config.toml` exactly as before
  (unchanged).
- No HRONO_HOME on win32 (platform + `user_config_dir` faked) -> the roaming
  AppData dir with appname "hrono", ending in config.toml.
- Perms: writing a profile on POSIX yields file 0600 / dir 0700 and round-trips
  (add/current/token). With `os.name` forced to "nt", `_write` skips the POSIX
  chmods cleanly, does NOT crash, and still writes the file — the Windows-perms
  difference is documented in both docstrings.

Code review: `config_path` keys on `sys.platform == "win32"`, `_write` guards
chmod on `os.name == "posix"` — both correctly separate Windows from POSIX; only
the default location changes, only on Windows; write path/format identical. The
server DB is untouched (client config path only). `platformdirs>=4.2,<5` added
with the lockfile committed (well-known maintained lib). One atomic Conventional
Commit (bcc1331). All ACs met — no flags.
- 2026-08-16 PO: PASS -> done. Verified `config_path()` on the real platform:
  darwin default -> ~/.hrono/config.toml (unchanged), HRONO_HOME wins, and the
  win32 branch (user_config_dir(roaming=True)) is present (qa drove it via
  platform mocks + confirmed the POSIX 0600/0700 perms hold while os.name=="nt"
  skips chmod cleanly without crashing). Matches exactly what PO settled: Windows
  -> %APPDATA%\hrono via platformdirs, macOS/Linux keep ~/.hrono, HRONO_HOME the
  escape hatch; client config path only, server DB untouched. config_path tests
  3 passed; gate 359. Clean low-priority platform fix. Closed at bcc1331.
