# export index entries name the file to open
From E018 review. On hrono's own repo the export still costs more than raw
(grep 382-434k vs 320k; walk 758k-1.09M vs 509k): a walk takes ~4 reads vs 1.5.
Idea: an index page's Children entries name the section files they lead to, so a
walk settles in 2 reads. Also: two sibling dirs share the slug
"hrono-is-a-hierarchical-incrementally-updated-knowledge-base" (-5/-15), not telling.
Re-measure with .e2e/eval/run.py; evidence/E018/ is the baseline.
