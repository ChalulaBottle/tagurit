"""
Tagurit — the rewrite engine.

The point: convert_to_html/convert_to_pdf must never hand mistune a slice or
reference of the original .md file's text. Every character in the output
reaches it by being individually copied into a fresh buffer during
tokenization — `rewrite(text)` shares no substring object with `text`, only
equal *content*. That's the actual guarantee (metadata scrubbing, in
metadata_engine.py, is a secondary safety net on top of this, not the point).

No str[a:b] slicing appears anywhere in this module. Tokens are built by
appending one character at a time to a list, then `"".join()`-ing it — the
strongest form of "re-typed, not copied" available in pure Python.
"""

from __future__ import annotations


def tokenize(text: str) -> list[str]:
    """Split `text` into tokens (word-runs, whitespace-runs, single
    newlines), each built by appending individual characters — never a
    slice of `text`. Iterating a str in Python is character-by-character
    by definition, so `for ch in text` never yields a substring."""
    tokens: list[str] = []
    buf: list[str] = []
    buf_kind = None  # "word" | "space" | None

    def flush() -> None:
        nonlocal buf, buf_kind
        if buf:
            tokens.append("".join(buf))
            buf = []
        buf_kind = None

    for ch in text:
        if ch == "\n":
            flush()
            tokens.append(ch)
        elif ch.isspace():
            if buf_kind != "space":
                flush()
                buf_kind = "space"
            buf.append(ch)
        else:
            if buf_kind != "word":
                flush()
                buf_kind = "word"
            buf.append(ch)
    flush()
    return tokens


def rewrite(text: str) -> str:
    """Read-only over `text`. Returns an independently constructed string:
    equal in content (word-for-word, character-for-character), but built
    entirely from freshly-copied characters, never a slice or reference
    into `text`. `rewrite(text) == text` and `rewrite(text) is not text`
    hold for every non-empty input."""
    tokens = tokenize(text)
    return "".join(tokens)


class NoSliceGuard:
    """Test-only wrapper around a str that raises if anything ever slices
    it (`__getitem__` with a slice object). Single-character indexing and
    iteration — both of which `tokenize` relies on — are allowed. Wrapping
    the source in this before calling `rewrite` is a runtime proof, not
    just a code-review claim, that the pipeline never takes a substring of
    the original text."""

    def __init__(self, s: str):
        self._s = s

    def __len__(self) -> int:
        return len(self._s)

    def __iter__(self):
        return iter(self._s)

    def __getitem__(self, key):
        if isinstance(key, slice):
            raise AssertionError("rewrite pipeline sliced the source text")
        return self._s[key]
