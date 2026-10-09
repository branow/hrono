-- A worker whose thread dies would leave its job `running` for ever, and
-- nothing could tell that leftover from a job a live worker is still executing.
-- `heartbeat` is stamped when the job is claimed and re-stamped while it runs,
-- so a sweep returns any job whose worker stopped touching it to the queue.
ALTER TABLE jobs ADD COLUMN heartbeat TEXT;
