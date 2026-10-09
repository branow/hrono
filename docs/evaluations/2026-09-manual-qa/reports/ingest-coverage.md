# ingest coverage per source

## itsdangerous: 50 files in cache, 34 ingested, 39 sections, 454 passages

skipped:
  - .github/ISSUE_TEMPLATE/bug-report.md
  - .github/ISSUE_TEMPLATE/config.yml
  - .github/ISSUE_TEMPLATE/feature-request.md
  - .github/pull_request_template.md
  - .github/workflows/lock.yaml
  - .github/workflows/pre-commit.yaml
  - .github/workflows/publish.yaml
  - .github/workflows/tests.yaml
  - src/itsdangerous/py.typed
  - tests/test_itsdangerous/__init__.py
  - tests/test_itsdangerous/test_encoding.py
  - tests/test_itsdangerous/test_serializer.py
  - tests/test_itsdangerous/test_signer.py
  - tests/test_itsdangerous/test_timed.py
  - tests/test_itsdangerous/test_url_safe.py
  - uv.lock

files split into >1 section: 3
  - src/itsdangerous/serializer.py: 3 sections
  - pyproject.toml: 3 sections
  - docs/_static/itsdangerous-name.svg: 2 sections

## chalk: 35 files in cache, 22 ingested, 30 sections, 820 passages

skipped:
  - .github/funding.yml
  - .github/security.md
  - .github/workflows/main.yml
  - media/logo.png
  - media/screenshot.png
  - test/_fixture.js
  - test/_force-color-fixture.js
  - test/chalk.js
  - test/force-color.js
  - test/instance.js
  - test/level.js
  - test/no-color-support.js
  - test/visible.js

files split into >1 section: 2
  - media/logo.svg: 8 sections
  - readme.md: 2 sections

## uuid: 33 files in cache, 22 ingested, 23 sections, 240 passages

skipped:
  - .github/CODEOWNERS
  - .github/release-please.yml
  - .github/workflows/apidiff.yaml
  - .github/workflows/tests.yaml
  - json_test.go
  - null_test.go
  - seq_test.go
  - sql_test.go
  - time_test.go
  - uuid_test.go
  - version6_test.go

files split into >1 section: 1
  - uuid.go: 2 sections

## section bytes: n=92 min=19 median=1486 max=10239 mean=3015
## passage bytes: n=1514 min=9 median=135 max=800 mean=183
## passages over 800B budget: 0
## sections over 10KB budget: 0

## passages under 64 bytes: 7 of 1514 (0.5%)
  - 9B source/vendor/ansi-styles/index.d.ts :: b'tColor = '
  - 19B .gitattributes :: b'* text=auto eol=lf\n'
  - 19B .npmrc :: b'package-lock=false\n'
  - 30B go.mod :: b'module github.com/google/uuid\n'
  - 36B source/vendor/supports-color/browser.d.ts :: b"export {default} from './index.js';\n"
  - 44B .gitignore :: b'node_modules\nyarn.lock\ncoverage\n.nyc_output\n'
  - 45B docs/changes.rst :: b'Changes\n=======\n\n.. include:: ../CHANGES.rst\n'

## passage size histogram
  - <64: 7
  - 64-200: 1151
  - 200-400: 241
  - 400-800: 112
  - 800+: 3

## smallest sections
  - 19B .gitattributes
  - 19B .npmrc
  - 30B go.mod
  - 36B source/vendor/supports-color/browser.d.ts
  - 44B .gitignore
  - 45B docs/changes.rst
  - 74B .gitignore
  - 98B docs/license.rst

## svg / non-prose files ingested
  - docs/_static/itsdangerous-icon.svg: 1 sections
  - docs/_static/itsdangerous-logo.svg: 1 sections
  - docs/_static/itsdangerous-name.svg: 2 sections
  - media/logo.svg: 8 sections
