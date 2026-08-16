"""Tagurit — collision-guard tests. Run: py -m unittest discover -s R:\\MD-Convert\\tests

Found via adversarial testing: two different source files converting to the
same output name silently overwrote each other with no warning. MDConvertApp
._dedupe_path fixes it; these tests pin that behavior directly (no Tk display
needed — it's a @staticmethod, real filesystem, no mocking).
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from md_convert import MDConvertApp


class DedupePathTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_no_collision_returns_original(self):
        target = str(Path(self.tmpdir.name) / "notes.pdf")
        self.assertEqual(MDConvertApp._dedupe_path(target), target)

    def test_single_collision_appends_2(self):
        existing = Path(self.tmpdir.name) / "notes.pdf"
        existing.write_bytes(b"AAA111")
        target = str(existing)
        result = MDConvertApp._dedupe_path(target)
        self.assertEqual(result, str(Path(self.tmpdir.name) / "notes (2).pdf"))

    def test_multiple_collisions_increment(self):
        for name in ["notes.pdf", "notes (2).pdf", "notes (3).pdf"]:
            (Path(self.tmpdir.name) / name).write_bytes(b"x")
        target = str(Path(self.tmpdir.name) / "notes.pdf")
        result = MDConvertApp._dedupe_path(target)
        self.assertEqual(result, str(Path(self.tmpdir.name) / "notes (4).pdf"))

    def test_original_content_never_overwritten(self):
        first = Path(self.tmpdir.name) / "notes.pdf"
        first.write_bytes(b"AAA111")
        second_path = MDConvertApp._dedupe_path(str(first))
        Path(second_path).write_bytes(b"BBB222")
        self.assertEqual(first.read_bytes(), b"AAA111")
        self.assertEqual(Path(second_path).read_bytes(), b"BBB222")


if __name__ == "__main__":
    unittest.main()
