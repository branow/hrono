---
id: git-url-leading-dash
title: a git source URL that starts with "-" reaches git as an option
priority: low
---

`GitSource.url` (registry/collections/sources.py) accepts any string, and it is
passed positionally to `git ls-remote` (registry/validation/git_validation.py,
ingest/remote_head.py) and `git clone` (ingest/git_syncer.py) with no `--`
separator. A URL such as `--upload-pack=<cmd>` is read by git as an option.
Only an admin can register a source, so this is defence in depth, but since
E005 home runs `ls-remote` on every page load by any reader. Reject a leading
"-" in the model, or put `--` before the URL in every git call.

Found by qa while gating E005 (2026-10-03).
