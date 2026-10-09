#!/bin/sh
# Wake the PO: exits when po-review/ holds a ticket, backlog/ changed, or the
# board is drained. Run in the background by the orchestrator.
here="$(cd "$(dirname "$0")" && pwd)"
board="$here/../board"
base="$(ls "$board/backlog")"
while :; do
    "$here/wait-for-board.sh" 280
    [ $? -eq 3 ] && { echo drained; exit 0; }
    if [ -n "$(ls "$board/po-review")" ] || [ "$(ls "$board/backlog")" != "$base" ]; then
        echo "po-review: $(ls "$board/po-review" | tr '\n' ' ')"
        echo "backlog: $(ls "$board/backlog" | tr '\n' ' ')"
        exit 0
    fi
done
