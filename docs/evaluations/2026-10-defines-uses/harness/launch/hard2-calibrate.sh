#!/bin/zsh
# Step 2 of the hard2 set: code only, 2 tries per question; keep the questions it fails.
H=/Users/orest/repos/hrono/docs/evaluations/2026-10-defines-uses/harness
cd $H
qs=($(python3 -c "import json;print(' '.join(q['qid'] for q in json.load(open('$HOME/hrono-deep/data/hard2.json'))))"))
for q in $qs; do for t in a b; do echo "$q code-h2$t@sonnet"; done; done | xargs -P 4 -L 1 zsh -c 'SET=hard2 MAP=none EXPORT=export-bcreg-v9-L3 uv run --extra claude-code python agent_v2.py run $0 $1 > ~/hrono-eval/h2-$1-$0.log 2>&1'
cd ~/hrono-deep && uv run --project /Users/orest/repos/hrono python harness/score.py hard2 code-h2a@sonnet code-h2b@sonnet > ~/hrono-eval/h2-score.log 2>&1
echo "TEST DONE $(date)" >> ~/hrono-eval/h2-score.log
