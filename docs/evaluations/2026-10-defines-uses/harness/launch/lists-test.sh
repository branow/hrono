#!/bin/zsh
# Lists: hrono at 30 turns (1 try, against code-t1b 0.69) and two more tries per arm at 12 turns.
H=/Users/orest/repos/hrono/docs/evaluations/2026-10-defines-uses/harness
cd $H
t1=($(python3 -c "import json;print(' '.join(q['qid'] for q in json.load(open('$HOME/hrono-deep/data/tasks1.json'))))"))
export NOTE="You have at most 30 tool calls in total. Stop exploring in time to write the list: a partial list with what you found beats no answer. Write the answer by your 22nd tool call at the latest."
for q in $t1; do echo "$q hrono-t1b@sonnet 30"; done | xargs -P 5 -L 1 zsh -c 'SET=tasks1 MAP=plugin RECALL=1 TURNS=$2 WORDS=2500 EXPORT=export-bcreg-v9-L3 uv run --extra claude-code python agent_v2.py run $0 $1 > ~/hrono-eval/lt-$1-$0.log 2>&1'
export NOTE="You have at most 12 tool calls in total. Stop exploring in time to write the answer: a partial answer with what you found beats no answer. Write it by your 10th tool call at the latest."
{ for t in b c; do for q in $t1; do echo "$q hrono-c12$t@sonnet plugin"; echo "$q code-c12$t@sonnet none"; done; done; } | xargs -P 4 -L 1 zsh -c 'SET=tasks1 MAP=$2 RECALL=1 TURNS=12 WORDS=2500 EXPORT=export-bcreg-v9-L3 uv run --extra claude-code python agent_v2.py run $0 $1 > ~/hrono-eval/lt-$1-$0.log 2>&1'
cd ~/hrono-deep && uv run --project /Users/orest/repos/hrono python harness/score_list.py tasks1 hrono-t1b@sonnet hrono-c12b@sonnet code-c12b@sonnet hrono-c12c@sonnet code-c12c@sonnet > ~/hrono-eval/lt-score.log 2>&1
echo "TEST DONE $(date)" >> ~/hrono-eval/lt-score.log
