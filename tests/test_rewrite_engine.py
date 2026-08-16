"""Tagurit — rewrite_engine tests. Run: py -m unittest discover -s R:\\MD-Convert\\tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rewrite_engine import NoSliceGuard, rewrite, tokenize


class RewriteEngineTests(unittest.TestCase):
    CASES = {
        "empty": "",
        "single_word": "hello",
        "plain_sentence": "The quick brown fox jumps over the lazy dog.",
        "heading_and_list": "# Title\n\n- one\n- two\n- three\n",
        "code_fence": "```python\ndef f(x):\n    return x + 1\n```\n",
        "unicode": "café — naïve — 日本語 — emoji: 🔥🛡️ — ñ",
        "crlf": "line one\r\nline two\r\nline three\r\n",
        "tabs": "\tindented\twith\ttabs\n",
        "no_trailing_newline": "no newline at the end",
        "consecutive_blank_lines": "para one\n\n\n\npara two\n",
        "bom_prefix": "\ufeff# Title\ntext\n",
        "leading_trailing_ws": "   spaced out   \n",
        "long_word": "x" * 5000,
        "mixed_whitespace_runs": "a  \t \t b\n\n c",
        "emphasis_markers": "**bold** and *italic* and `code` and [link](http://example.com)",
    }

    def test_content_identical_for_all_cases(self):
        for name, text in self.CASES.items():
            with self.subTest(case=name):
                self.assertEqual(rewrite(text), text)

    def test_object_identity_differs(self):
        for name, text in self.CASES.items():
            if text == "":
                continue  # CPython interns "" — identity distinction is meaningless here
            with self.subTest(case=name):
                result = rewrite(text)
                self.assertIsNot(result, text)

    def test_no_slicing_occurs(self):
        # Runtime proof, not a code-review claim: if tokenize() ever slices
        # its input, NoSliceGuard.__getitem__ raises immediately.
        for name, text in self.CASES.items():
            with self.subTest(case=name):
                guarded = NoSliceGuard(text)
                tokens = tokenize(guarded)
                self.assertEqual("".join(tokens), text)

    def test_empty_string(self):
        self.assertEqual(rewrite(""), "")

    def test_tokenize_reconstructs_exactly(self):
        for name, text in self.CASES.items():
            with self.subTest(case=name):
                self.assertEqual("".join(tokenize(text)), text)

    def test_idempotent(self):
        for name, text in self.CASES.items():
            with self.subTest(case=name):
                once = rewrite(text)
                twice = rewrite(once)
                self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
