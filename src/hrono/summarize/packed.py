"""Condense several sections in ONE call, and split the reply back apart.

Through ``claude-code`` every call carries the CLI's own harness prompt, about
19k cached tokens and several seconds that no prompt can remove (#107). One
section per call paid that overhead 421 times on a 421-section build; a pack of
``PACK_ITEMS`` pays it once per pack, and the pool still runs packs side by
side.

The template is a role's stored prompt and stays untouched: each section is
rendered through it exactly as a single call would render it, and the pack is a
wrapper of numbered tasks around those renderings. The tags carry a per-pack
NONCE, so a section that itself contains ``</result>`` (an XML file, a doc
about this very format) cannot close a result early.

A section whose result is missing, or talks back to the caller, is condensed
again ALONE through ``shape.answer`` — the path every section took before
packing — so a pack can only ever save calls, never lose a condensation or
change what a refusal means (E015).
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Callable, Sequence

from hrono.llm.client import (
    Completion,
    CompletionRequest,
    CompletionResult,
    Usage,
)
from hrono.summarize.shape import answer

PACK_ITEMS = 8
PACK_BYTES = 32_000

Item = tuple[str, bytes]  # (content hash, section body)
Made = tuple[CompletionResult, str]  # (reply, refusal reason or "")


def packs(items: Sequence[Item]) -> list[tuple[Item, ...]]:
    """Group ``items`` greedily, in order, under both pack limits."""
    grouped: list[tuple[Item, ...]] = []
    current: list[Item] = []
    size = 0
    for item in items:
        full = len(current) == PACK_ITEMS or size + len(item[1]) > PACK_BYTES
        if current and full:
            grouped.append(tuple(current))
            current, size = [], 0
        current.append(item)
        size += len(item[1])
    if current:
        grouped.append(tuple(current))
    return grouped


def condense_pack(
    completion: Completion,
    model: dict[str, object],
    render: Callable[[Item], str],
    pack: Sequence[Item],
    gate: Callable[[str], str],
) -> list[Made]:
    """One reply per item of ``pack``, in order."""
    alone = [render(item) for item in pack]
    if len(pack) == 1:
        return [_single(completion, model, alone[0], gate)]
    nonce = secrets.token_hex(4)
    reply = completion.complete(
        CompletionRequest(model=model, system="", content=_wrap(alone, nonce))
    )
    found = _results(reply.text, nonce)
    shares = _apportion(reply.usage, alone, found, len(pack))
    made: list[Made] = []
    for index, rendered in enumerate(alone):
        text = found.get(index + 1, "")
        if not gate(text):
            made.append((CompletionResult(text, shares[index]), ""))
        else:
            made.append(_single(completion, model, rendered, gate))
    return made


def _single(
    completion: Completion,
    model: dict[str, object],
    rendered: str,
    gate: Callable[[str], str],
) -> Made:
    request = CompletionRequest(model=model, system="", content=rendered)
    return answer(completion, request, gate)


def _wrap(rendered: Sequence[str], nonce: str) -> str:
    tasks = "\n\n".join(
        f'<task-{nonce} id="{index}">\n{text}\n</task-{nonce}>'
        for index, text in enumerate(rendered, start=1)
    )
    return (
        f"Below are {len(rendered)} independent tasks, each inside "
        f'<task-{nonce} id="N"> tags. Do each task on its own, exactly as if '
        f"it were the only one. Write each task's result inside "
        f'<result-{nonce} id="N"></result-{nonce}> with the same id, one '
        f"result per task, in order, and nothing outside the result tags."
        f"\n\n{tasks}"
    )


def _results(text: str, nonce: str) -> dict[int, str]:
    pattern = re.compile(
        rf'<result-{nonce} id="(\d+)">(.*?)</result-{nonce}>', re.DOTALL
    )
    return {
        int(match.group(1)): match.group(2).strip()
        for match in pattern.finditer(text)
    }


def _apportion(
    usage: Usage, rendered: Sequence[str], found: dict[int, str], count: int
) -> list[Usage]:
    """Split one call's tokens across its items, so each section's stored
    cost sums back to what the pack was billed: input by what each task sent,
    output by what each result wrote, cache by input."""
    sent = [len(text) for text in rendered]
    wrote = [len(found.get(index + 1, "")) for index in range(count)]
    inputs = _split(usage.input_tokens, sent)
    outputs = _split(usage.output_tokens, wrote if sum(wrote) else sent)
    reads = _split_optional(usage.cache_read, sent)
    writes = _split_optional(usage.cache_creation, sent)
    return [
        Usage(inputs[i], outputs[i], reads[i], writes[i], usage.model)
        for i in range(count)
    ]


def _split(total: int, weights: Sequence[int]) -> list[int]:
    whole = sum(weights) or len(weights)
    parts = [
        total * (weight if sum(weights) else 1) // whole for weight in weights
    ]
    parts[-1] += total - sum(parts)
    return parts


def _split_optional(
    total: int | None, weights: Sequence[int]
) -> list[int | None]:
    if total is None:
        return [None] * len(weights)
    return list(_split(total, weights))
