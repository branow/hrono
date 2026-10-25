#!/bin/zsh
# A: hrono on hard2 at the full budget (30 turns), to set against code only's 0.77.
# B: hard2 + tasks1 with BOTH arms capped at 12 turns and told so, one try each.
H=/Users/orest/repos/hrono/docs/evaluations/2026-10-defines-uses/harness
cd $H
h2=($(python3 -c "import json;print(' '.join(q['qid'] for q in json.load(open('$HOME/hrono-deep/data/hard2.json'))))"))
t1=($(python3 -c "import json;print(' '.join(q['qid'] for q in json.load(open('$HOME/hrono-deep/data/tasks1.json'))))"))
for q in $h2; do echo "hard2 $q hrono-h2a@sonnet plugin 30 900"; done | xargs -P 4 -L 1 zsh -c 'SET=$0 MAP=$3 RECALL=1 TURNS=$4 WORDS=$5 EXPORT=export-bcreg-v9-L3 uv run --extra claude-code python agent_v2.py run $1 $2 > ~/hrono-eval/bt-$0-$2-$1.log 2>&1'
export NOTE="You have at most 12 tool calls in total. Stop exploring in time to write the answer: a partial answer with what you found beats no answer. Write it by your 10th tool call at the latest."
{ for q in $h2; do echo "hard2 $q hrono-c12a@sonnet plugin 12 900"; echo "hard2 $q code-c12a@sonnet none 12 900"; done
  for q in $t1; do echo "tasks1 $q hrono-c12a@sonnet plugin 12 2500"; echo "tasks1 $q code-c12a@sonnet none 12 2500"; done; } | xargs -P 4 -L 1 zsh -c 'SET=$0 MAP=$3 RECALL=1 TURNS=$4 WORDS=$5 EXPORT=export-bcreg-v9-L3 uv run --extra claude-code python agent_v2.py run $1 $2 > ~/hrono-eval/bt-$0-$2-$1.log 2>&1'
cd ~/hrono-deep
uv run --project /Users/orest/repos/hrono python harness/score.py hard2 hrono-h2a@sonnet hrono-c12a@sonnet code-c12a@sonnet > ~/hrono-eval/bt-score.log 2>&1
uv run --project /Users/orest/repos/hrono python harness/score_list.py tasks1 hrono-c12a@sonnet code-c12a@sonnet >> ~/hrono-eval/bt-score.log 2>&1
echo "TEST DONE $(date)" >> ~/hrono-eval/bt-score.log
