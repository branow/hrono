-- Every model call, recorded against the run that made it.
--
-- Tokens on what a call PRODUCED — a condensation, a brief — leave no trace
-- of a call that failed, was retried, or was a judge vote, so a run could not
-- say what it had spent. One row per call is the record every roll-up reads:
-- store per call, show any sum.
--
-- `run_id` and `started_by` are resolved when the row is written, from the
-- job's ROOT, so a fan-out leaf's calls add up under the run a person started.
-- Token columns are nullable: an embedding pass through a local model has no
-- token count, and an unknown is not a zero. `upstream_model` is what the
-- provider says it ran, which is not always the name the config asked for.
CREATE TABLE llm_calls (
    id                    INTEGER PRIMARY KEY,
    job_id                TEXT,
    run_id                TEXT,
    started_by            TEXT,
    model                 TEXT NOT NULL,
    role                  TEXT NOT NULL,
    provider              TEXT NOT NULL,
    upstream_model        TEXT,
    input_tokens          INTEGER,
    output_tokens         INTEGER,
    cache_read_tokens     INTEGER,
    cache_creation_tokens INTEGER,
    duration_ms           INTEGER NOT NULL,
    ok                    INTEGER NOT NULL CHECK (ok IN (0, 1)),
    created_at            TEXT NOT NULL
);

CREATE INDEX llm_calls_run_id ON llm_calls (run_id);
CREATE INDEX llm_calls_created_at ON llm_calls (created_at);

-- Who started a job. Null on every job made before this column existed, which
-- a reader shows as unknown, never as anyone in particular.
ALTER TABLE jobs ADD COLUMN started_by TEXT;
