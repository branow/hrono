# Home's recent runs read every job and show the stored, not the derived, status

What: `server/ui/overview.py` `_recent` calls `job_store.list_jobs(conn)` (every
job of every tree), filters in Python, keeps the last few, and prints
`row["status"]` — for a fan-out parent that is the stored `pending`, never the
status `aggregate.rollup` derives from its children.
Where: src/hrono/server/ui/overview.py `_recent`.
Why it matters: same scale problem E002 fixed for the runs list, and a
fanned-out run reads "pending" on Home after it finished. `jobs.store.page_roots`
(E002) already pages roots per tree in SQL; reusing it is a few lines.
