# Tagurit — build log

An open-source markdown converter for digital privacy text formatting. Core
guarantee: the source `.md` file is never copied into the output — it's
re-typed character-by-character by `rewrite_engine.py` (the "mirroring
engine") before mistune/xhtml2pdf ever see it, and `metadata_engine.py`
controls the renderer's own fresh `/Info` dict as a secondary safety net.

## 2026-08-16 — initial build + adversarial test pass

### Built
- `rewrite_engine.py` — char-by-char tokenizer + rebuild. No `str[a:b]`
  slicing anywhere; every character reaches the output via individual
  append. `NoSliceGuard` proves this at runtime, not just by code review.
- `metadata_engine.py` — pypdf-based scrub. Only `/Title` (filename stem,
  never full path), `/Author` (blank), `/Producer`/`/Creator` (`"Tagurit"`),
  `/CreationDate` (conversion time, never source mtime) survive in `/Info`;
  XMP stream stripped.
- Wired into `md_convert.py`'s `convert_to_html`/`convert_to_pdf`: source
  text now passes through `rewrite_engine.rewrite()` before reaching
  mistune; `convert_to_pdf` calls `metadata_engine.clean_pdf_metadata()`
  after xhtml2pdf writes the file.
- Test suite: `tests/test_rewrite_engine.py`, `tests/test_metadata_engine.py`,
  `tests/test_dedupe_path.py` — 17 tests, stdlib `unittest`, no extra deps.

### Own test suite — round 1: 11/11 pass, first try
No failures on the initial 11 tests (unicode, CRLF, BOM, empty, code fences,
emphasis markers, idempotence, no-slicing proof). Not treated as sufficient
proof by itself — self-written tests passing isn't evidence of robustness,
so an independent adversarial pass followed.

### Adversarial hunt (4 parallel breaker agents, real execution not
reasoning — each wrote and ran real Python against the actual source)

**encoding** — 40/40 pass. Surrogate pairs, combining diacritics (up to
2000-mark stacks), RTL text (Arabic/Hebrew), ZWJ sequences and emoji with
skin-tone modifiers, all 32 control characters, mixed line-ending styles,
whitespace-only strings, BOM. No failures.

**markdown-fidelity** — pass. `mistune.html(rewrite(text)) ==
mistune.html(text)` byte-for-byte across nested code fences, tables,
footnotes, embedded raw HTML, tab-indented code, tricky link syntax,
heading/hr edge cases, empty/whitespace-only files. Integration-level test
against the real on-disk `convert_to_html()` also matched exactly.

**metadata-pdf** — 29/29 checks pass, but surfaced two real findings:
1. **Bug, fixed**: `/CreationDate` was listed in `ALLOWED_INFO_KEYS` but
   `clean_pdf_metadata()` never actually wrote it — whitelist and actual
   output had drifted apart. Fixed: `_pdf_creation_date()` added, now
   genuinely written on every scrub. Pinned by
   `test_creation_date_is_actually_written`.
2. **Coverage gap, fixed**: the `has_xmp is False` post-scrub check was
   vacuous — xhtml2pdf's own output never contains XMP to begin with, so
   the strip path (`writer.xmp_metadata = None`) was never genuinely
   exercised. Fixed: `test_xmp_strip_path_actually_exercised` now injects a
   real, valid XMP stream (RDF-wrapped, containing a fake leaked path
   string) before scrubbing, confirms the injection took, then confirms the
   scrub actually removes it.

**scale-and-fs** — 3 real findings, all fixed except one flagged as
out-of-scope:
1. **Bug, fixed**: `convert_to_pdf()` measured at 52–55s on a 3.55MB
   markdown file (67-page real document), ~90% of it inside
   `xhtml2pdf.pisa.CreatePDF` itself (48.1s of the total) — confirmed
   non-linear scaling (0.5MB→3.1s, 1MB→12.0s, 2MB→22.0s, 3.5MB→39.4s). The
   GUI ran this on the main thread with zero progress indicator, so a large
   conversion looked like a frozen app. Fixed: `on_convert()` now runs the
   conversion on a worker thread (`threading.Thread`), status line shows
   "Converting…" immediately, UI updates marshaled back via `root.after()`
   since Tkinter isn't thread-safe. `rewrite_engine.rewrite()` itself was
   confirmed NOT the bottleneck (0.7–4.0s on the same file, proportional
   memory use, no pathological behavior).
2. **Bug, fixed**: two different source files converting to the same output
   filename (e.g. two different `notes.md` in different folders) silently
   overwrote each other — no crash, no warning, the first file's converted
   output just vanished. Fixed: `MDConvertApp._dedupe_path()` — same
   convention as Windows' own "Copy (2)", disambiguates instead of
   overwriting. Pinned by `tests/test_dedupe_path.py` (4 tests, including
   one that proves the original file's bytes survive untouched).
3. **Confirmed clean**: unicode + spaces in source filenames (a real file
   on disk: `ünïcödé dir 日本語\my notes café 北京 emoji🔥 file.md`) — both
   converters handled it with no exceptions, no path-handling bug found.

Also flagged (real, but genuinely out of scope for this pass — a pre-
existing xhtml2pdf/reportlab limitation, not something introduced by
`rewrite_engine`/`metadata_engine`): **CJK and emoji glyphs render as tofu
boxes** in PDF output, since xhtml2pdf's default font has no CJK/emoji
coverage. Confirmed via `pypdf` text extraction (`'Café Notes ■■'` for
Chinese/emoji input, Latin-accented text like café/naïve/façade renders
correctly). Not fixed here — logged to `BACKLOG.md` as a follow-up, not
silently dropped.

### Round 2 — retest after fixes
Full suite rerun after all fixes: **17/17 pass** (11 original + 3 new
collision-guard tests + `test_creation_date_is_actually_written` +
`test_xmp_strip_path_actually_exercised` replacing the earlier vacuous
version).

### Final end-to-end verification (real file, not synthetic)
Converted `C:\Users\OOrte\Downloads\Temp AEGIS_Deep\README.md` through the
actual `convert_to_pdf()` pipeline.
- Metadata dump: `{'/Producer': 'Tagurit', '/Title': 'README', '/Author':
  '', '/Creator': 'Tagurit', '/CreationDate': "D:20260816074332+00'00'"}`,
  `has_xmp: False` — matches the whitelist exactly.
- **Self-caught verification bug**: first attempt grepped the PDF's raw
  bytes for leftover markdown syntax (`##`, `**`) and got false-positive
  hits — meaningless, since PDF content streams are FlateDecode-compressed
  binary and short byte sequences like `##`/`**` turn up by chance in any
  compressed blob. Corrected by extracting the actual rendered text via
  `pypdf`'s `page.extract_text()` instead and checking *that* for leftover
  syntax — genuinely clean, zero markdown syntax characters present in the
  rendered/extracted text.

### Net result
Rewrite engine: correct on every case tried (80+ adversarial inputs across
2 independent breaker agents, 17 pinned regression tests). Metadata scrub:
correct and now genuinely exercised (not vacuous). Two real UX/data-safety
bugs found and fixed (GUI freeze, silent overwrite). One real limitation
documented and deferred (CJK/emoji glyph rendering) rather than silently
dropped.

## 2026-10-21 (cloud session): output folder feature, backlog 221a

Built from CLOUD-BRIEF.md. `rewrite_engine.py` and `metadata_engine.py` were
not touched; no test needed them to change.

### Built
- `output_dir` setting in `scan_config.json`, stored by `resolve_output_dir`
  in `md_convert.py`. Default is `Path.home() / "Downloads" / "My PDFs"`,
  created on first use by `ensure_output_dir`. Every conversion now goes
  through `plan_output_path`, which places the file in that folder instead
  of beside the source.
- First run step: when the key is absent, `MDConvertApp` asks once via one
  dialog (Yes keeps the default, No opens a folder picker, dismissing the
  picker falls back to the default) and stores the answer. The "Output
  folder" button runs the same dialog later to change it.
- "Open Output" button opens the configured folder in the system file
  manager via `open_in_file_manager` (os.startfile on Windows, `open` on
  macOS, `xdg-open` elsewhere). The folder is created first if missing. The
  status line click after a conversion uses the same opener.
- Dedupe: `plan_output_path` hands the planned path to the existing
  `_dedupe_path`, so two different `notes.md` files from two folders become
  `notes.pdf` and `notes (2).pdf` inside the output folder.

### Tests
`tests/test_output_dir.py`, stdlib unittest, 19 tests: default path, config
key, first run asks once and stores, user pick stored, dismissed dialog falls
back to default, not asked again once set, change later reuses the dialog,
round trip through a real config file, output lands in the folder and not
beside the source, same name dedupe inside the folder, counter keeps
incrementing, matches `_dedupe_path` exactly, a real HTML conversion lands in
the folder, Open Output creates then launches, platform openers. One test is
Windows only (os.startfile) and skips elsewhere.

Full run: `python -m pytest tests/` gives 35 passed, 1 skipped. The original
17 are all among the passes.

### Verified beyond the unit tests
The Tk app was built under Xvfb with the dialogs stubbed: the first run
dialog fired exactly once, the config file held the folder, the change
button reused the dialog, Open Output targeted the configured folder, and a
real `on_convert` wrote `notes.html` into it.

Known limitation left alone, per the brief: CJK and emoji render as boxes in
PDF output. Items 222 and 223 were not started.
