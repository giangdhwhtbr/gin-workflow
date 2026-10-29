# Docs-wide style and grounding pass

Epic: gin-workflow-9pl2
Status: draft for user review.

## Goal and scope

Every page of the repository's user documentation follows the `docs` rule pack and states only what the code does. Epic `gin-workflow-46ns` added the pack, `references/docs-style.md`, and the regrounding mode of `/tech-doc`; this epic applies them to `README.md` and the 29 pages under `docs/`. A test then stops the mechanical rules from drifting back.

Measured on 2026-10-29 (outside code blocks): 16 of the 30 pages break a mechanical rule. The largest counts are `starters/greenfield.md` (14 bold-label list items, 5 numbered headings), `guides/windows.md` (7 dashes, 5 bold-label items, 7 numbered headings), `getting-started.md` (5 emoji, 6 bold-label items, 5 numbered headings), and `reference/troubleshooting.md` (7 dashes, 8 bold-label items).

Out of scope:
- New pages, moved or renamed pages, and changes to the `docs/` folder structure.
- Code changes. A claim that the docs get right and the code gets wrong becomes a bug bead in this repository; the page is left as it is and the bead is named in the track report.
- The decks (`docs/presentations/*.html`, `*.pptx`) and `build_brownfield_pptx.py`.

## Requirements

### R1. Every page is regrounded

For each page in scope, a track applies the regrounding steps of `/tech-doc` (`plugins/gin-workflow/src/skills/tech-doc/SKILL.md`, "Regrounding existing docs"):
1. List the page's factual claims: commands, flags, paths, defaults, and behavior.
2. Check each claim against the code at HEAD and note the evidence as `file:line`, or that nothing backs it.
3. Fix a wrong claim, remove a claim nothing backs, or call it a convention when it describes team practice.
4. Report per page: claims checked, fixed, and removed, and open questions.

The track report holds the per-page results; they are not written into the repository.

### R2. Every page follows the `docs` rule pack

The writer follows the output of `gin-workflow rules --files <pages>` and `plugins/gin-workflow/src/references/docs-style.md`. Each page ends with:
- no em or en dashes, no list items that open with a bold label, no emoji, and no numbered headings (outside code blocks);
- sentence-case headings, without questions outside a FAQ;
- no sentence longer than 35 words, no promotional or filler words, one term per concept.

Exception: `docs/presentations/brownfield-modernization-script.md` keeps its slide-numbered headings and title, because they map to the slides of the deck. Its claims are regrounded (R1).

### R3. Runbook pages have runbook structure

- `docs/reference/troubleshooting.md`: each entry's heading is the symptom the reader sees, verbatim where an error message exists, and its body gives the cause, then the fix.
- `docs/reference/upgrade-2.0.md` and `docs/reference/upgrade-2.1.md`: each has a table mapping old to new (commands, settings, files, or behavior that changed) and a rollback section. When the code offers no automated rollback, the section says so and names the manual way back, checked against the code.

### R4. A test enforces the mechanical rules

`tests/workflow_core/test_docs_coverage.py` gains a test that scans `README.md` and `docs/**/*.md`, ignores fenced code blocks, and fails with `file:line` for each:
- em dash (U+2014) or en dash (U+2013);
- list item (bulleted or numbered) whose text opens with a bold span;
- emoji;
- heading whose text starts with a digit.

`docs/presentations/brownfield-modernization-script.md` is exempt, named in the test.

### R5. Work is split into five page groups and one test track

| Track | Pages |
|---|---|
| T1 runbooks | `reference/troubleshooting.md`, `reference/upgrade-2.0.md`, `reference/upgrade-2.1.md` |
| T2 reference | `reference/cli.md`, `reference/config.md`, `reference/skills.md`, `reference/orchestrator-contract.md` |
| T3 concepts | `concepts/architecture.md`, `concepts/lifecycle.md`, `concepts/providers.md`, `concepts/state-model.md`, `contributing.md` |
| T4 guides | the 9 pages of `docs/guides/` |
| T5 entry points | `README.md`, `getting-started.md`, `roles.md`, the 3 pages of `docs/starters/`, the 2 pages of `docs/orchestrator/`, `presentations/brownfield-modernization-script.md` |
| T6 style test | `tests/workflow_core/test_docs_coverage.py`; depends on T1 to T5 |

T1 to T5 touch disjoint files and run in parallel. Each track edits only its own pages. A fix another page needs (for example a link to a renamed heading) goes into the track report, and the coordinator applies it after the tracks close.

## User Stories

### US-1: Docs a reader can trust
As a user reading gin-workflow's documentation, I want every command, flag, path, and default on a page to match the code, so that following the docs works the first time.

Acceptance criteria:
- Every page in scope has a per-page regrounding report in its track's handoff: claims checked, fixed, and removed.
- An independent reviewer checks each track's pages against the code and approves the track.
- Every claim found wrong in the code instead of the docs has a bug bead, named in the report.

### US-2: One house style across the docs
As a reader, I want every page in the same plain style, so that pages read alike and nothing distracts from the facts.

Acceptance criteria:
- The R4 scan reports no violation in `README.md` or `docs/**/*.md`, except the exempt script.
- Headings are sentence case and no sentence in a changed paragraph exceeds 35 words.

### US-3: Runbooks for when something breaks
As a user with a failing install or upgrade, I want troubleshooting entries that start from the error I see and upgrade guides that show what changed and how to go back, so that I fix the problem without reading the whole page.

Acceptance criteria:
- Every `reference/troubleshooting.md` entry has a symptom heading, a cause, and a fix.
- `upgrade-2.0.md` and `upgrade-2.1.md` each have an old-to-new mapping table and a rollback section.

### US-4: Style cannot drift back
As a maintainer, I want a test that fails when a page breaks a mechanical rule, so that new pages keep the style without a manual check.

Acceptance criteria:
- The R4 test exists and passes on the finished pages.
- The test fails, naming `file:line`, when a page gains an em dash, a bold-label list item, an emoji, or a numbered heading.

## Errors and compatibility

- Changed headings change anchors. Relative links with anchors inside the repository are checked by `test_relative_links_resolve` only for the file part; each track searches for links to the headings it changes and reports the ones outside its pages for the coordinator to fix.
- Outside links to anchors (from other repositories or bookmarks) may break; this is accepted.
- `test_every_docs_page_is_in_the_readme_map` and `test_every_cli_subcommand_has_a_heading` keep passing: pages are not moved, and `cli.md` keeps its `` ## `gin-workflow <command>` `` headings.

## Testing

- After each of T1 to T5: the coordinator runs the R4 scan on the track's pages (not trusting the worker's own check), `tests.workflow_core.test_docs_coverage`, and the full suite `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`.
- Each track gets an independent review with the `docs` rule pack checklist; claims are checked against the code, not only the diff.
- T6: the new test passes on the finished pages, and a temporary page with one violation of each kind makes it fail (checked in the test with a fixture, not by editing a real page).
