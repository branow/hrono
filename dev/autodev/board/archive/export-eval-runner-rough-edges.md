# export eval runner: two rough edges (from E004 qa round 2, non-blocking)

- `--only` silently drops unknown question ids; it should stop and name them,
  as `--rerender` does for unrecorded pairs.
- a non-timeout exception in one session still discards sessions finishing
  after it; record it as an error Run like a timeout.
Look at: .e2e/eval/run.py
