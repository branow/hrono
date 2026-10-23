#!/bin/zsh
H=/Users/orest/repos/hrono/docs/evaluations/2026-10-defines-uses/harness
cd $H
qs=($(python3 -c "import json;print(' '.join(q['qid'] for q in json.load(open('$HOME/hrono-deep/data/hard15.json'))))"))
for q in $qs; do for t in a b; do echo "$q hrono-rec$t@sonnet"; done; done | xargs -P 4 -L 1 zsh -c 'MAP=plugin RECALL=1 EXPORT=export-bcreg-v9-L3 uv run --extra claude-code python agent_v2.py run $0 $1 > ~/hrono-eval/rec-$1-$0.log 2>&1'
cd ~/hrono-deep && uv run --project /Users/orest/repos/hrono python harness/score.py hard15 hrono-reca@sonnet hrono-recb@sonnet > ~/hrono-eval/rec-score.log 2>&1
echo "TEST DONE $(date)" >> ~/hrono-eval/rec-score.log
