# Health summary promises a sync fixes a settled echo

src/hrono/server/triage.py:122 says "Recall cannot answer from them until a
sync rewrites them." for every brief `triage.unanswerable` lists. Since E019 a
settled echoes-the-prompt brief is listed but no sync rewrites it (E009 now
says so on its own row). The summary line should not promise a sync for it.
Found by qa while gating E009 round 2.
