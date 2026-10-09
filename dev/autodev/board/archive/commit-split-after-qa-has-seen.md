# qa's one-commit-per-ticket bar cannot be met once qa has seen the commit

qa.md bars two tickets in one commit; dev.md bars rewriting a commit qa has
seen. When qa finds two tickets in one commit (E009 b1f1e00, tickets 1 and 3),
dev cannot fix it and the round loops. The PO or orchestrator should rule: let
dev split a seen commit before merge, or let the merge step accept it.
