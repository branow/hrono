# Task: credit control

You are the developer who owns this feature in webERP, from request to a
change you would ship. The business wrote what it wants in `task/brd.md`,
in its own words; it does not know how webERP works inside.

Work out what this feature really needs in webERP to make sense and to
work: what it depends on, what else in the system has to change with it,
what the business did not think to ask for. Decide the open questions the
way a good engineer on this project would. Then build the whole feature,
following how this project does things.

When done, write `NOTES.md` at the repository root: what you built and
where, what else you changed and why, and the decisions you made.


The webERP repository is in the current directory; the task is task/task.md. There is nothing to run against: deliver the change as files. The repository's GitHub issues, pull requests and discussions up to the base date are in github/, one markdown file per thread.

This project has a map in /Users/orest/hrono-weberp/exports/4cb937f79e8b57063bd47132413abdac8abbcbdc-threads: briefs that describe what each part of the codebase does, its rules and how its flows work. Read root.md first, then only the briefs of the parts your feature touches, including the existing flows your new code does the same work as. Where a brief tells you what a module does or how a flow works, take it from the brief and do not open that code. Open source code only for the files you will change, and only the parts of them you change.