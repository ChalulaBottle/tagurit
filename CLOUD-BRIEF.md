# Cloud brief: Tagurit output folder feature

For a Claude Code cloud session started by the operator with `claude --cloud` in this repo. Read
this file, then README.md and TAGURIT_BUILD_LOG.md, before touching code.

## What Tagurit is

A markdown converter for digital privacy text formatting. Its core guarantee is in
`rewrite_engine.py`: the source file is never copied into the output; a mirroring engine retypes
it word for word into a fresh buffer, and `NoSliceGuard` proves at runtime that no slicing ever
touches the source. `metadata_engine.py` is the secondary safety net. `md_convert.py` is the app.
`tests/` holds 17 passing tests. Run them first and confirm 17 pass before any change.

## The task: the output folder feature (backlog item 221, part a)

Designed on 2026-08-16, never built. Build exactly this:

1. An `output_dir` setting in `scan_config.json`, defaulting to the user's `Downloads\My PDFs`
   (create it on first use). Every conversion writes there instead of beside the source.
2. A first run step: when `output_dir` is not yet set, the app asks once where output should go,
   offering the default, and stores the answer. Changing it later goes through the same dialog.
3. A dedicated Open Output button in the app that opens the folder in the system file manager.
4. Same name conversions keep the existing `_dedupe_path` behaviour inside the new folder.

## Rules

- The never copy the source guarantee is not touched. Do not edit `rewrite_engine.py` or
  `metadata_engine.py` unless a test proves the feature needs it, and say so in the commit.
- Add tests for the new setting, the default path, the first run step and the dedupe inside the
  output folder. All 17 existing tests must still pass. `python -m pytest tests/` is the check.
- Known limitation, leave alone: CJK and emoji render as boxes in PDF output.
- No bold text, no arrows, no em dashes in anything written. Plain commit messages that say what
  was built.
- Work on a branch named `cloud/output-folder`, push it, and open a pull request against `main`
  with the test output in the description. Do not merge. The operator reviews.
- Items 222 and 223 (DOCX and PDF as source, the MCP server) are not scoped yet. Do not start them.
