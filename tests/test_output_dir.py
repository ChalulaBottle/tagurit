"""Tagurit output folder tests (backlog 221a).

Pins the new output_dir setting: its default path, the first run step that
asks once and stores the answer, the Open Output launcher, and the dedupe
behaviour inside the output folder. No Tk display needed: every function
under test is module level or a @staticmethod, and the dialog and the
config writer are injected as plain callables.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import md_convert
from md_convert import (
    DEFAULT_OUTPUT_DIR,
    OUTPUT_DIR_KEY,
    MDConvertApp,
    ensure_output_dir,
    get_output_dir,
    open_in_file_manager,
    output_dir_is_set,
    plan_output_path,
    resolve_output_dir,
)


class FakeSave:
    """Stands in for save_config so tests never touch the real scan_config.json."""

    def __init__(self):
        self.calls = []

    def __call__(self, cfg):
        self.calls.append(dict(cfg))


class DefaultPathTests(unittest.TestCase):
    def test_default_is_downloads_my_pdfs_under_home(self):
        self.assertEqual(DEFAULT_OUTPUT_DIR, Path.home() / "Downloads" / "My PDFs")
        self.assertEqual(DEFAULT_OUTPUT_DIR.name, "My PDFs")
        self.assertEqual(DEFAULT_OUTPUT_DIR.parent.name, "Downloads")

    def test_config_key_name(self):
        self.assertEqual(OUTPUT_DIR_KEY, "output_dir")

    def test_get_output_dir_falls_back_to_default_when_unset(self):
        self.assertEqual(get_output_dir({"roots": []}), DEFAULT_OUTPUT_DIR)
        self.assertEqual(get_output_dir({"roots": [], "output_dir": ""}), DEFAULT_OUTPUT_DIR)
        self.assertFalse(output_dir_is_set({"roots": []}))

    def test_get_output_dir_returns_stored_value(self):
        cfg = {"roots": [], "output_dir": "/some/where"}
        self.assertEqual(get_output_dir(cfg), Path("/some/where"))
        self.assertTrue(output_dir_is_set(cfg))

    def test_ensure_output_dir_creates_missing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Downloads" / "My PDFs"
            self.assertFalse(target.exists())
            result = ensure_output_dir(target)
            self.assertTrue(target.is_dir())
            self.assertEqual(result, target)
            # second call is a no op, never an error
            ensure_output_dir(target)
            self.assertTrue(target.is_dir())


class FirstRunStepTests(unittest.TestCase):
    def test_asks_once_offers_default_and_stores_answer(self):
        cfg = {"roots": []}
        save = FakeSave()
        asked_with = []

        def ask(default):
            asked_with.append(default)
            return default

        chosen = resolve_output_dir(cfg, ask=ask, save=save)

        self.assertEqual(asked_with, [str(DEFAULT_OUTPUT_DIR)])
        self.assertEqual(chosen, DEFAULT_OUTPUT_DIR)
        self.assertEqual(cfg[OUTPUT_DIR_KEY], str(DEFAULT_OUTPUT_DIR))
        self.assertEqual(len(save.calls), 1)
        self.assertEqual(save.calls[0][OUTPUT_DIR_KEY], str(DEFAULT_OUTPUT_DIR))

    def test_user_picked_folder_is_stored(self):
        cfg = {"roots": []}
        save = FakeSave()
        chosen = resolve_output_dir(cfg, ask=lambda _default: "/custom/out", save=save)
        self.assertEqual(chosen, Path("/custom/out"))
        self.assertEqual(cfg[OUTPUT_DIR_KEY], str(Path("/custom/out")))
        self.assertEqual(len(save.calls), 1)

    def test_dismissed_dialog_falls_back_to_default(self):
        cfg = {"roots": []}
        save = FakeSave()
        chosen = resolve_output_dir(cfg, ask=lambda _default: None, save=save)
        self.assertEqual(chosen, DEFAULT_OUTPUT_DIR)
        self.assertEqual(cfg[OUTPUT_DIR_KEY], str(DEFAULT_OUTPUT_DIR))
        self.assertEqual(len(save.calls), 1)

    def test_not_asked_again_once_set(self):
        cfg = {"roots": [], "output_dir": "/already/chosen"}
        save = FakeSave()

        def ask(_default):
            self.fail("dialog must not be shown when output_dir is already set")

        chosen = resolve_output_dir(cfg, ask=ask, save=save)
        self.assertEqual(chosen, Path("/already/chosen"))
        self.assertEqual(save.calls, [])

    def test_change_later_reuses_same_dialog(self):
        cfg = {"roots": [], "output_dir": "/already/chosen"}
        save = FakeSave()
        asked_with = []

        def ask(default):
            asked_with.append(default)
            return "/new/place"

        chosen = resolve_output_dir(cfg, ask=ask, save=save, force=True)
        self.assertEqual(asked_with, [str(DEFAULT_OUTPUT_DIR)])
        self.assertEqual(chosen, Path("/new/place"))
        self.assertEqual(cfg[OUTPUT_DIR_KEY], str(Path("/new/place")))
        self.assertEqual(len(save.calls), 1)

    def test_stored_value_round_trips_through_real_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "scan_config.json"
            original = md_convert.CONFIG_PATH
            md_convert.CONFIG_PATH = config_path
            try:
                cfg = md_convert.load_config()
                self.assertFalse(output_dir_is_set(cfg))
                resolve_output_dir(cfg, ask=lambda d: d)
                reloaded = md_convert.load_config()
                self.assertEqual(reloaded[OUTPUT_DIR_KEY], str(DEFAULT_OUTPUT_DIR))
                self.assertEqual(reloaded["roots"], cfg["roots"])
            finally:
                md_convert.CONFIG_PATH = original


class DedupeInsideOutputFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        base = Path(self.tmpdir.name)
        self.out_dir = base / "out"
        self.src_a = base / "a" / "notes.md"
        self.src_b = base / "b" / "notes.md"
        for src in (self.src_a, self.src_b):
            src.parent.mkdir(parents=True)
            src.write_text("# notes\n", encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_output_lands_in_output_dir_not_beside_source(self):
        out = Path(plan_output_path(str(self.src_a), ".pdf", self.out_dir))
        self.assertEqual(out, self.out_dir / "notes.pdf")
        self.assertNotEqual(out.parent, self.src_a.parent)
        self.assertTrue(self.out_dir.is_dir(), "output folder is created on first use")

    def test_same_name_sources_dedupe_inside_output_dir(self):
        first = Path(plan_output_path(str(self.src_a), ".pdf", self.out_dir))
        first.write_bytes(b"AAA111")
        second = Path(plan_output_path(str(self.src_b), ".pdf", self.out_dir))
        self.assertEqual(first, self.out_dir / "notes.pdf")
        self.assertEqual(second, self.out_dir / "notes (2).pdf")
        second.write_bytes(b"BBB222")
        self.assertEqual(first.read_bytes(), b"AAA111")
        self.assertEqual(second.read_bytes(), b"BBB222")

    def test_dedupe_counter_keeps_incrementing(self):
        self.out_dir.mkdir()
        for name in ["notes.html", "notes (2).html", "notes (3).html"]:
            (self.out_dir / name).write_bytes(b"x")
        out = plan_output_path(str(self.src_a), ".html", self.out_dir)
        self.assertEqual(Path(out), self.out_dir / "notes (4).html")

    def test_uses_the_existing_dedupe_path_convention(self):
        self.out_dir.mkdir()
        (self.out_dir / "notes.pdf").write_bytes(b"x")
        expected = MDConvertApp._dedupe_path(str(self.out_dir / "notes.pdf"))
        actual = plan_output_path(str(self.src_a), ".pdf", self.out_dir)
        self.assertEqual(actual, expected)

    def test_real_html_conversion_writes_into_output_dir(self):
        out = plan_output_path(str(self.src_a), ".html", self.out_dir)
        md_convert.convert_to_html(str(self.src_a), out)
        self.assertTrue(Path(out).exists())
        self.assertIn("<h1>notes</h1>", Path(out).read_text(encoding="utf-8"))
        self.assertFalse((self.src_a.parent / "notes.html").exists())


class OpenOutputTests(unittest.TestCase):
    def test_opens_configured_folder_and_creates_it_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "My PDFs"
            launched = []
            opened = open_in_file_manager(target, run=launched.append)
            self.assertEqual(launched, [str(target)])
            self.assertEqual(opened, str(target))
            self.assertTrue(target.is_dir())

    @unittest.skipUnless(hasattr(md_convert.os, "startfile"), "os.startfile is Windows only")
    def test_windows_uses_startfile(self):
        self.assertIs(md_convert._default_folder_opener("Windows"), md_convert.os.startfile)

    def test_mac_and_linux_use_their_openers(self):
        for system, expected in [("Darwin", "open"), ("Linux", "xdg-open")]:
            seen = []
            original = md_convert.subprocess.Popen
            md_convert.subprocess.Popen = lambda argv: seen.append(argv)
            try:
                md_convert._default_folder_opener(system)("/some/folder")
            finally:
                md_convert.subprocess.Popen = original
            self.assertEqual(seen, [[expected, "/some/folder"]])


if __name__ == "__main__":
    unittest.main()
