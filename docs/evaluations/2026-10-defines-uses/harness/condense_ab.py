"""Condense the same chunks with haiku and sonnet: time, cost, text."""

import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Users/orest/repos/hrono/src")
from hrono.registry.collections.prompts import _CONDENSE  # noqa: E402

CORPUS = Path.home() / "hrono-deep" / "corpus"
OUT = Path(__file__).parent / "condense_ab"
OUT.mkdir(exist_ok=True)
CHUNKS = [
    (
        "lear",
        "queue_services/business-pay/src/business_pay/resources/pay_filer.py",
        0,
        10054,
    ),
    (
        "lear",
        "queue_services/entity-emailer/src/entity_emailer/message_tracker/tracker.py",
        0,
        10228,
    ),
    ("lear", "queue_services/entity-pay/src/entity_pay/worker.py", 0, 8102),
]
tag = sys.argv[1]  # names the prompt version
models = sys.argv[2:] or ["haiku", "sonnet"]
for source, path, a, b in CHUNKS:
    body = (CORPUS / source / path).read_bytes()[a:b].decode("utf-8", "replace")
    prompt = _CONDENSE.replace("{content}", f"File: {source}/{path}\n\n{body}")
    for model in models:
        t = time.time()
        out = subprocess.run(
            [
                "claude",
                "-p",
                "--model",
                model,
                "--output-format",
                "json",
                "--tools",
                "",
            ],
            input=prompt,
            capture_output=True,
            text=True,
        )
        r = json.loads(out.stdout)
        name = f"{tag}-{model}-{Path(path).stem}"
        (OUT / f"{name}.md").write_text(r["result"])
        u = r.get("usage", {})
        print(
            json.dumps(
                {
                    "run": name,
                    "secs": round(time.time() - t, 1),
                    "cost": r.get("total_cost_usd"),
                    "out_tokens": u.get("output_tokens"),
                }
            ),
            flush=True,
        )
