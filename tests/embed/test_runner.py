import importlib.util

import pytest

from hrono.embed.runner import EmbedError, batch_size, embed_texts

_HAS_BACKEND = importlib.util.find_spec("sentence_transformers") is not None


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

    with pytest.raises(EmbedError, match="not installed"):
        encoder_for("any/model")


@pytest.mark.skipif(
    not _HAS_BACKEND,
    reason="embed extra not installed (uv pip install hrono[embed])",
)
def test_backend_is_importable_when_the_embed_extra_is_installed() -> None:
    # With the `embed` optional-extra the in-process backend is present, so the
    # runner can build a real encoder (weights are not loaded here to keep CI
    # offline). Skipped on the lean default install.
    import sentence_transformers  # noqa: F401
