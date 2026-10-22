# Growth: Tagurit

Purpose: an open source markdown converter that guarantees the source file is never copied into the output, only retyped character by character into a fresh buffer.
State: growing
Lane: free
Rules: a draft pull request is already open for the output folder feature, do not rebuild that same feature on another branch. Do not edit the rewrite engine or the metadata engine unless a test proves the change is needed, and say so in the commit. All existing tests must keep passing. No bold text, no arrows, no em dashes in anything written.

## Next improvements, in order

1. Write a real README. Why: the whole project is public on GitHub with a detailed build log and a cloud session brief, but the README itself is two lines and tells a visitor nothing about what the project does or how to run it. Size: S. Done when: the README explains the no-copy guarantee in plain terms, how to install and run the converter, and links to the build log for anyone who wants the detail.
2. Give the PDF output real coverage for CJK text and emoji, instead of the boxes they render as today. Why: the build log confirms this exact failure with real test input and logs it as a known limitation, deferred rather than fixed. Size: M. Done when: a markdown file containing Chinese, Japanese and emoji text converts to a PDF whose extracted text contains the real characters, not boxes, and the existing test suite still passes in full.
3. Write a short scoping note for the DOCX and PDF as source feature, answering whether the no-copy guarantee can extend to a binary source file the same way it does for a markdown one. Why: the cloud session brief names this as not scoped yet and says explicitly not to start building it, so the useful next step is the scoping question, not code. Size: S. Done when: a note in the build log or a new scoping file states what a binary source format would need to prove the same guarantee.
4. Write a short scoping note for an MCP server exposing the converter, answering what it would need to expose and whether it depends on a local model backed version of the rewrite engine first. Why: the cloud session brief names this as not scoped yet and says explicitly not to start building it. Size: S. Done when: a note states the minimum tool surface such a server would need and what open questions block starting it.
5. (operator step) Review the open draft pull request for the output folder feature and either merge it or send back specific changes. Why: the rotation plan is explicit that nothing merges itself, and this is the one piece of in-flight work in the repository today. Size: S. Done when: the pull request is merged, or has specific operator feedback on it.

## Grown recently

- 2026-10-22: GROWTH.md seeded for the growth rotation.
