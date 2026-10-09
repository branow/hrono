# run page "Stages N" header undercounts a failed run
Seen in evidence/E002/failed-first-build.png: header reads "Stages 3" over a
list of 4 (the failed condense stage is listed but not counted). The count
should match the rows shown, or say "3 of 4 done".
Look at: src/hrono/server/templates/run.html stages header.
