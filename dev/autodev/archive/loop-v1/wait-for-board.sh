#!/bin/sh
# Block until the board changes, so an idle agent waits instead of returning.
#
#   wait-for-board.sh [seconds]     default 280
#
# exit 0  a ticket moved (some folder's listing changed) — look at the board
# exit 2  nothing moved within the time — look anyway, then wait again
# exit 3  the board is drained: todo, in-progress, verifying and po-review are
#         all empty. There is nothing left for anyone; report and return.
board="$(cd "$(dirname "$0")/../board" && pwd)"
limit="${1:-280}"

listing() {
    for stage in backlog todo in-progress verifying po-review done; do
        ls "$board/$stage" 2>/dev/null | sed "s|^|$stage/|"
    done
}

drained() {
    for stage in todo in-progress verifying po-review; do
        ls "$board/$stage"/*.md >/dev/null 2>&1 && return 1
    done
    return 0
}

drained && exit 3
before="$(listing)"
waited=0
while [ "$waited" -lt "$limit" ]; do
    sleep 10
    waited=$((waited + 10))
    drained && exit 3
    [ "$(listing)" != "$before" ] && exit 0
done
exit 2
