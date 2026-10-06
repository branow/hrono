-- A requeued job counts its tries. The reclaimer put every stranded job
-- back to 'pending' without limit, so a job that crashes the process (OOM,
-- a native crash) was retried after every restart, forever — a poison-pill
-- crash loop nobody saw. `attempts` is the number of requeues; the sweep
-- fails a job that reaches the cap instead of queueing it again.
ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;

-- Fan-out parents were written 'pending' and nothing ever wrote them again:
-- their status was derived from their children on read, so every finished
-- run's parent sat in the 'pending' set the claim scan and the status
-- filters walk, forever. Give each one whose children have all finished its
-- derived terminal status; the worker finalizes new ones as they finish.
UPDATE jobs SET status = (
    SELECT CASE
        WHEN SUM(c.status = 'failed') > 0 THEN 'failed'
        WHEN SUM(c.status = 'canceled') > 0 THEN 'canceled'
        ELSE 'succeeded'
    END FROM jobs c WHERE c.parent_id = jobs.id
)
WHERE status = 'pending'
  AND EXISTS (SELECT 1 FROM jobs c WHERE c.parent_id = jobs.id)
  AND NOT EXISTS (
      SELECT 1 FROM jobs c WHERE c.parent_id = jobs.id
        AND c.status IN ('pending', 'running'));
