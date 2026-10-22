#!/usr/bin/env python3
# ruff: noqa: SIM115 - experiment harness
"""A stand-in `hrono` binary for the plugin's recall hook: replays the
recall reply `recall_cache.py` saved for the question it is asked."""

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
question = sys.argv[3]
for q in json.load(open(Path.home() / "hrono-deep/data/hard15.json")):
    if q["question"].strip() == question.strip():
        print((HERE / "recall" / f"{q['qid']}.json").read_text())
        sys.exit(0)
print('{"hits": []}')
