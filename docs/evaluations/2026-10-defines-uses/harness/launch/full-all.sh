#!/bin/zsh
~/hrono-eval/full-rebuild.sh
tail -1 ~/hrono-eval/full-rebuild.log | grep -q DONE && ~/hrono-eval/full-test.sh
