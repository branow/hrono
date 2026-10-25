#!/bin/zsh
# List tasks, code only, one try each, told its turn budget: 4 of 5 tries without the note ran out of turns with no answer.
H=/Users/orest/repos/hrono/docs/evaluations/2026-10-defines-uses/harness
cd $H
export NOTE="You have at most 30 tool calls in total. Stop exploring in time to write the list: a partial list with what you found beats no answer. Write the answer by your 22nd tool call at the latest."
qs=($(python3 -c "import json;print(' '.join(q['qid'] for q in json.load(open('$HOME/hrono-deep/data/tasks1.json'))))"))
for q in $qs; do echo "$q code-t1b@sonnet"; done | xargs -P 5 -L 1 zsh -c 'SET=tasks1 WORDS=2500 MAP=none EXPORT=export-bcreg-v9-L3 uv run --extra claude-code python agent_v2.py run $0 $1 > ~/hrono-eval/t1-$1-$0.log 2>&1'
cd ~/hrono-deep && uv run --project /Users/orest/repos/hrono python harness/score_list.py tasks1 code-t1b@sonnet > ~/hrono-eval/t1b-score.log 2>&1
echo "TEST DONE $(date)" >> ~/hrono-eval/t1b-score.log
