<!-- level 1, node 501, children [75, 126, 153, 154, 314, 328, 329] -->

**Parent brief: shell env loading and Python logging setup snippets**

This group holds condensed notes on two kinds of small items: a shell snippet that loads `.env` and activates a venv, and Python logging configuration. Within each kind the entries are mostly repeats.

## 1. Shell snippet: load `.env` and activate venv
- **Variant 1 (the commands as written):**
  - `while read -r line; do export $line; echo $line; done < .env` exports each line and echoes it.
  - `source venv/bin/activate` activates the venv.
  - `source .env` loads the same file again.
  - The first line of the snippet is commented out.
- **Variant 2 (one-line summary):** It adds comment-skipping (`^#.*$`).
- **Gotchas:**
  - `.env` is loaded twice, which can conflict. A line like `export FOO=bar` becomes `export export FOO=bar`.
  - A missing `.env` produces no error.
  - `export $line` treats whitespace and quotes literally, so `KEY="value with spaces"` is exported malformed.
  - `source` runs in the current shell, so the venv activation persists.
  - Without `set -e`, a broken venv path won't halt the script.

## 2. Python `logging` INI configs
**Shared base:**
- A console `StreamHandler` writes to `sys.stdout`, normally at DEBUG.
- The format string is `%(asctime)s - %(name)s - %(levelname)s in %(module)s:%(filename)s:%(lineno)d - %(funcName)s: %(message)s`. `datefmt` is empty, so the default timestamp format applies.
- Child loggers set `propagate=0`, so their records go only to their own handler and not to root.

**Variants by logger set and level:**
- **DEBUG `api` stacks (most common):**
  - Root plus `api` (`qualname=api`), non-propagating.
  - Some add `asyncio`, `errorhandlers`, `invoke_jobs` or `sqlalchemy.engine.Engine`.
- **INFO `api` stack:** Root, `api`, `asyncio` (ERROR) and `aiohttp` (ERROR).
- **`bcol_api` variant:** Root and `api` at INFO, with `qualname=bcol_api` and a "detailed" formatter.
- **`tracing` variant:** `tracing` at ERROR, `qualname=jaeger_tracing`, to suppress verbose Jaeger output.
- **Payment-service (`pay_api`) stacks:**
  - Mixed levels: root and `pay_api` at INFO, `tracing` at ERROR, `sqlalchemy.engine.Engine` at DEBUG.
  - All-DEBUG: root, `pay_api`, `api-exceptions` and `sqlalchemy.engine.Engine`.

**Gotchas:**
- Logger levels such as INFO and ERROR override the DEBUG handler level, so they set the effective floor.
- `propagate=0` isolates each child logger from root. Confirm this is intended, especially if `api` is meant to be a child logger or if root's handler changes.
- Each child logger here has its own console handler, so logs are not lost. They would be lost only if the handler wiring changed.
- ERROR-level `tracing` drops lower-level tracing output.

## 3. `setup_logging(conf)` helper
This is Apache 2.0 code from the Province of British Columbia, with the licence year shown as 2019 or 2021.
- **Behavior:**
  - If `conf` exists, it calls `logging.config.fileConfig(conf)`. It then prints `Configure logging, from conf:{}` to stdout.
  - Otherwise it prints `Unable to configure logging, attempted conf:{}` to stderr.
- **Path handling:**
  - Some versions build the path from `Config.PROJECT_ROOT` and write status messages to stderr.
  - Most versions leave a commented-out `path.join(abspath(dirname(__file__)), conf)` line. They no longer resolve module-relative, so callers must pass a full path.
  - One version has a TODO to rework it to load the proper loggers and remove others.
- **Tests (`legal_api.utils.logging.setup_logging()`):**
  - `test_logging_with_file` loads `logging.conf` and asserts stdout starts with `Configure logging, from conf`.
  - `test_logging_with_missing_file` passes `None` and asserts stderr starts with `Unable to configure logging`.
  - Both use `capsys`. `setup_logging()` must run before `capsys.readouterr()`.
- **Gotchas:**
  - It never raises on a missing or invalid conf, so logging may stay unconfigured without the caller knowing.
  - It uses `print()` rather than the logger it is configuring.
  - The tests check only console output, and `startswith` is a weak assertion.

## 4. Unrelated: LaunchDarkly-style feature flags
- A deprecated `FileDataSource` factory returns a `_FileDataSource` lambda configured with `paths=['flags.json']`, `auto_update`, `poll_interval=1` and `force_polling=False`.
- The `Flags.init_app` wrapper reads `sdk_key` from the `LD_SDK_KEY` config and stores the client in `app.extensions['featureflags']`.
- Non-production uses the local file fallback. Production uses the remote SDK.
- **Gotcha:** In production, a missing `sdk_key` silently skips initialization, so there are no flags and no error. Non-production needs a local `flags.json` if `LD_SDK_KEY` is absent.
