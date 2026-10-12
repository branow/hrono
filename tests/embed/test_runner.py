import os
import threading
import time

import pytest

from hrono.embed import runner
from hrono.embed.runner import EmbedError, batch_size, embed_texts


def _fixed(dims: int):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[float(len(t))] * dims for t in texts]

    return encode


def test_embed_texts_returns_one_vector_per_text() -> None:
    vectors = embed_texts(["a", "bb", "ccc"], batch_size=2, encode=_fixed(4))
    assert len(vectors) == 3
    assert all(len(v) == 4 for v in vectors)
    assert vectors[1] == [2.0, 2.0, 2.0, 2.0]


def test_oom_halves_the_batch_and_still_completes() -> None:
    seen: list[int] = []

    def encode(texts: list[str]) -> list[list[float]]:
        seen.append(len(texts))
        if len(texts) > 2:
            raise MemoryError("boom")
        return [[1.0, 2.0] for _ in texts]

    vectors = embed_texts(["a", "b", "c", "d", "e"], 4, encode)
    assert len(vectors) == 5
    assert max(seen) > 2  # the first oversize batch was attempted
    assert min(seen) <= 2  # then it degraded to a smaller batch


def test_oom_on_a_single_item_fails_cleanly() -> None:
    def encode(texts: list[str]) -> list[list[float]]:
        raise MemoryError("boom")

    with pytest.raises(EmbedError):
        embed_texts(["only"], 4, encode)


def test_a_non_oom_error_is_not_swallowed() -> None:
    def encode(texts: list[str]) -> list[list[float]]:
        raise ValueError("bad input")

    with pytest.raises(ValueError, match="bad input"):
        embed_texts(["a"], 4, encode)


def test_batch_size_defaults_when_unset() -> None:
    assert batch_size({}) == 32
    assert batch_size({"batch_size": 8}) == 8


def test_missing_backend_reports_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import builtins

    real_import = builtins.__import__

    def blocked(name: str, *args: object, **kwargs: object) -> object:
        if name == "sentence_transformers":
            raise ImportError("no backend")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(builtins, "__import__", blocked)
    from hrono.embed.runner import encoder_for

    with pytest.raises(EmbedError, match="not installed") as caught:
        encoder_for("any/model")
    assert 'uv pip install "hrono[embed]"' in str(caught.value)


def test_a_cached_encoder_loads_its_model_once() -> None:
    # the measured cost: 13.3s for the first recall and 14ms for every later
    # one, all of it the weights.
    loads: list[str] = []

    def build(model_id: str):
        loads.append(model_id)
        return lambda texts: [[0.0] for _ in texts]

    runner._CACHE.clear()
    first = runner.cached_encoder_for("a-model", build=build)
    second = runner.cached_encoder_for("a-model", build=build)

    assert loads == ["a-model"]
    assert first is second


def test_a_cached_encoder_is_per_model_id() -> None:
    loads: list[str] = []

    def build(model_id: str):
        loads.append(model_id)
        return lambda texts: [[0.0] for _ in texts]

    runner._CACHE.clear()
    runner.cached_encoder_for("one", build=build)
    runner.cached_encoder_for("two", build=build)
    runner.cached_encoder_for("one", build=build)

    assert loads == ["one", "two"]


def test_a_failed_load_is_not_cached() -> None:
    # an id that failed once may load on the next attempt; caching the failure
    # would make the server need a restart to notice the fix.
    attempts: list[str] = []

    def failing(model_id: str):
        attempts.append(model_id)
        raise EmbedError("nope")

    runner._CACHE.clear()
    for _ in range(2):
        with pytest.raises(EmbedError):
            runner.cached_encoder_for("broken", build=failing)

    assert attempts == ["broken", "broken"]


@pytest.mark.skipif(
    not os.environ.get("HRONO_TEST_REAL_MODEL"),
    reason="set HRONO_TEST_REAL_MODEL=<id> to load real weights",
)
def test_the_cache_holds_a_REAL_encoder() -> None:
    """The seam proves the memo; only the real backend proves the contract.

    Guarded by an env var rather than skipped outright, because the thing worth
    knowing here is that `encoder_for`'s actual return value survives being
    cached and still encodes -- and that costs a weights load, which the lean
    install and an offline CI cannot pay.
    """
    model_id = os.environ["HRONO_TEST_REAL_MODEL"]
    runner._CACHE.clear()

    first = runner.cached_encoder_for(model_id)
    second = runner.cached_encoder_for(model_id)

    assert first is second
    vectors = second(["a question about bearer tokens"])
    assert len(vectors) == 1
    assert len(vectors[0]) > 1


def test_a_ready_encoder_is_returned_without_waiting() -> None:
    runner._CACHE.clear()
    runner._INFLIGHT.clear()
    encoder = runner.cached_encoder_for(
        "warm", build=lambda _id: lambda texts: [[0.0] for _ in texts]
    )

    assert runner.ready_encoder_for("warm") is encoder


def test_a_cold_encoder_reports_a_miss_and_starts_loading() -> None:
    # never a dead end: the miss is what makes "shortly" true rather than
    # hopeful, so a retry finds it.
    started = threading.Event()
    runner._CACHE.clear()
    runner._INFLIGHT.clear()

    def build(model_id: str):
        started.set()
        return lambda texts: [[0.0] for _ in texts]

    assert runner.ready_encoder_for("cold", build=build) is None
    assert started.wait(timeout=5)

    deadline = time.monotonic() + 5
    while "cold" not in runner._CACHE and time.monotonic() < deadline:
        time.sleep(0.01)
    assert runner.ready_encoder_for("cold", build=build) is not None


def test_a_second_caller_does_not_start_a_second_load() -> None:
    # `_CACHE_LOCK` is held across a load, so the in-flight set needs its own
    # short-lived lock -- asking the big one would be the blocking this avoids.
    runner._CACHE.clear()
    runner._INFLIGHT.clear()
    runner._INFLIGHT.add("busy")
    try:
        before = threading.active_count()
        assert runner.ready_encoder_for("busy") is None
        assert threading.active_count() == before
    finally:
        runner._INFLIGHT.clear()


def test_a_remembered_failure_is_raised_not_hidden_behind_loading() -> None:
    # "still loading" is the one message an operator waits on rather than acts
    # on, so it must never be said about a model that can never load.
    runner._CACHE.clear()
    runner._INFLIGHT.clear()
    runner._FAILED.clear()

    def failing(model_id: str):
        raise EmbedError(f"embedding model failed to load: {model_id}")

    assert runner.ready_encoder_for("bad", build=failing) is None  # first try
    deadline = time.monotonic() + 5
    while "bad" not in runner._FAILED and time.monotonic() < deadline:
        time.sleep(0.01)

    with pytest.raises(EmbedError, match="failed to load"):
        runner.ready_encoder_for("bad", build=failing)
    runner._FAILED.clear()


def test_a_failure_does_not_stop_the_retry() -> None:
    # a model can start working once whatever was wrong is fixed, so the
    # memory stops the lie and not the loading.
    runner._CACHE.clear()
    runner._INFLIGHT.clear()
    runner._FAILED["flaky"] = "it was broken"

    def working(model_id: str):
        return lambda texts: [[0.0] for _ in texts]

    with pytest.raises(EmbedError):
        runner.ready_encoder_for("flaky", build=working)  # reports the old one

    deadline = time.monotonic() + 5
    while "flaky" not in runner._CACHE and time.monotonic() < deadline:
        time.sleep(0.01)
    assert runner.ready_encoder_for("flaky", build=working) is not None
    assert "flaky" not in runner._FAILED  # and the memory is cleared


def test_vectors_come_back_in_input_order_whatever_the_lengths() -> None:
    texts = ["a much longer text here", "b", "ccc", "dd"]
    seen: list[list[str]] = []

    def encode(batch: list[str]) -> list[list[float]]:
        seen.append(list(batch))
        return [[float(len(t))] for t in batch]

    vectors = embed_texts(texts, 2, encode)

    assert vectors == [[23.0], [1.0], [3.0], [2.0]]
    assert seen == [["b", "dd"], ["ccc", "a much longer text here"]]
