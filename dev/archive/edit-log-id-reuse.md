# edit_log ids are reused after the log is emptied

`edit_log.id` is a plain INTEGER PRIMARY KEY, so once `undo` (E034) or `release` (E036) deletes a topic's rows and the table is empty, the next edit gets id 1 again. A stale tab still showing "Undo rename" for edit 1 then undoes a later brief rewrite that reused id 1, after confirming a description of the rename. Pre-existing since E034, widened by E036's release path. Fix: rebuild `edit_log` with AUTOINCREMENT (or check kind + made_at as well as id in `undo`). src/hrono/edits.py `undo`/`_record`.
