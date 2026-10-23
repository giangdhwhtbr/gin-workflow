# ADLC deck

Workflow: adlc-deck
Bead: gin-workflow-c8ko
Status: draft for user review.

## Goal and scope

One slide deck that explains the Agentic Development Lifecycle gin-workflow 2.1 applies, to a developer or team lead new to gin-workflow. It replaces the removed `docs/interactive/index.html` and `docs/presentations/brownfield-onboarding.html` (commit `90f4370`, both out of date with the lifecycle).

The deck ships in two formats with the same 17 slides:

- `docs/presentations/adlc.html`: the source of truth, readable in a diff, opens offline in a browser.
- `docs/presentations/adlc.pptx`: the same slides for presenting and editing in PowerPoint, Keynote or Google Slides.

Out of scope: a generator script that builds one format from the other, translations, speaker notes, and any change to the lifecycle itself.

## Requirements

1. **Outline.** Both formats carry these slides, in this order:
   1. Title: the Agentic Development Lifecycle in gin-workflow 2.1.
   2. Why an agentic lifecycle: agents need gates, evidence and a bounded scope.
   3. Swim-lane diagram (below).
   4. `discuss` → `requirement_confirmed`.
   5. `plan` → `plan_approved`: tracks, provider role and reasoning tier, the `Human gate:` field.
   6. `orchestrate` → `orchestration_ready`: epic and track beads, routes, worktree, the printed `/goal`.
   7. `execute` → `implementation_complete`.
   8. Independent review: the review ledger, session or provider independence, bounded cycles, with a diagram of the ledger states.
   9. Evidence over self-assessment: the Claim / Requires / Not enough table from `docs/concepts/lifecycle.md`.
   10. Quality gates in git hooks by rigor.
   11. `ship` → `shipped`: the four options and the approvals they need.
   12. Isolation with worktrees, and task tracking: markdown by default, Beads optional, dependencies across repositories.
   13. Knowledge capture and rules packs.
   14. Variations: `/quick`, SDD living specs, team mode.
   15. Running unattended: `gin-workflow goal`, `human-gate` tracks, one-way `notify`.
   16. Product family diagram: gin-workflow core, the gin-orchestrator extension, gin-qa, gin-console.
   17. Get started: `/setup`, the first commands, links to the docs.
2. **Swim-lane diagram (slide 3).**
   - The swim lanes are:
     - people: Requester (BA/PM), Area lead, Developer, Ship approver;
     - agents: Main agent, Worker (gin-orchestrator, optional), Reviewer;
     - automation: Git hooks & CI.
   - The columns are the five stages, and a gate strip runs along the bottom.
   - Moments where the agent waits for a person are marked as such.
   - The draft at https://claude.ai/artifact/FSmCSu6J9pu62gcbc1WUu7 (version 2) is the agreed layout.
   - The deck does not mention solo mode.
3. **Visual style.** The deck has a new, bolder style instead of the old deck's:
   - large type and one idea per slide;
   - hand-drawn diagrams (inline SVG in HTML, native shapes in PPTX);
   - one colour reserved for human decisions;
   - a dark theme in the HTML.
4. **HTML deck.**
   - One self-contained file: inline CSS, JS and SVG, with no network requests (no external `src`/`href`, system font stacks).
   - One slide at a time, with a slide counter.
   - ←/→, PageUp/PageDown, Space, Home and End navigate.
   - It works at phone width.
5. **PPTX deck.**
   - 16:9 and the same slide content as the HTML.
   - Diagrams are native, editable shapes, not images.
   - It is built once with python-pptx and committed. No build script or dependency is added to the repository.
6. **Accuracy.**
   - Every stage and gate shown matches the table in `docs/concepts/lifecycle.md`.
   - Commands and keys are the ones in `docs/reference/cli.md` and `docs/reference/config.md`.
   - Neither format names a provider or a model.
7. **Links.** `README.md` (Documentation table) and `docs/getting-started.md` link both files.

## User Stories

### US-1: Learn the lifecycle from one deck
As a developer new to gin-workflow, I want one deck that walks the lifecycle from idea to merge, so that I know which stage I am in and what it needs from me.

Acceptance criteria:
- `docs/presentations/adlc.html` opens from disk with networking off and shows slide 1.
- ←/→, Home and End move between all 17 slides.
- Slide 3 shows the eight lanes, the five stages and the five gates.

### US-2: Present and edit the deck in a slide tool
As a team lead, I want the deck as a `.pptx`, so that I can present it and adapt it for my team.

Acceptance criteria:
- `docs/presentations/adlc.pptx` opens in PowerPoint and Google Slides with 17 slides in 16:9.
- The swim-lane and product-family diagrams can be edited shape by shape.

### US-3: Trust that the deck matches the docs
As a maintainer, I want a test that fails when the deck drifts from the lifecycle doc, so that both formats stay correct.

Acceptance criteria:
- A test fails when a stage or gate in `docs/concepts/lifecycle.md` is missing from either format.
- A test fails when either format names a provider or a model.
- A test fails when `README.md` or `docs/getting-started.md` does not link both files.

## Errors and compatibility

- The HTML relies on the browser's system fonts. A missing face falls back within the stack, and no slide depends on a specific font's metrics.
- The PPTX is binary, so its diff cannot be reviewed. The reviewer reads the text extracted from it and the test results instead.
- The two formats are kept in sync by hand. A lifecycle change updates both in the same change, and the test catches missing stages or gates.

## Testing

`tests/workflow_core/test_adlc_deck.py` uses only the standard library and reads the PPTX text with `zipfile`. It checks:

1. Every stage and gate name from the `docs/concepts/lifecycle.md` table appears in the HTML and in the PPTX slide XML.
2. The HTML has no `src` or `href` that starts with `http://` or `https://`.
3. The HTML has handlers for ArrowLeft, ArrowRight, Home and End.
4. The PPTX has 17 slides, and so does the HTML.
5. Neither format contains `codex`, `antigravity`, `opencode`, `gemini`, `sonnet`, `opus`, `haiku` or `gpt` (case-insensitive).
6. `README.md` and `docs/getting-started.md` link `presentations/adlc.html` and `presentations/adlc.pptx`.

The existing `test_docs_coverage` checks that the relative links resolve.
