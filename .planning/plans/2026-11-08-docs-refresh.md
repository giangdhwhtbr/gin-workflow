# Plan: Docs refresh after the BA flow and the rename

Epic: gin-workflow-docs-refresh
Spec: `.planning/specs/2026-11-08-docs-refresh-design.md`

## Objective

The docs describe the shipped behaviour as one whole: a BA learns the job from one page (`docs/guides/ba.md`), the starters walk the roadmap and milestone process in its real order with realistic multi-line prompts, and the reference and concept pages match the shipped CLI, skills, and config. Every changed `.vi.md` reads as native technical Vietnamese with the same headings as its English pair.

**Architecture.** Documentation only: Markdown pages under `docs/` and `README.md`, built by MkDocs Material with the `i18n` plugin (`<page>.vi.md` next to `<page>.md`), and the nav in `mkdocs.yml`.

**Tech stack.** Markdown, Mermaid (via `pymdownx.superfences`), MkDocs (`requirements-docs.txt`), `gin docs check`.

**Global Constraints** (from the spec):
- New behaviour; changes to skills, templates, or the CLI are out of scope. A mismatch between docs and code becomes a bug bead on the epic that owns the code, not a fix here.
- No new `.vi.md` pairs for pages that have none (`cli.md`, `config.md`, `troubleshooting.md`, `concepts/*`, `orchestrator/*`, `contributing.md`).
- No task-ordered role pages for roles other than the BA.
- The `gin-workflow` lines in `docs/reference/troubleshooting.md` stay: they describe the upgrade to 3.0 on purpose.
- Every Vietnamese text is written with the `vietnamese-language-skill` plugin (its `vietnamese-tech-writing` skill). A `.vi.md` page keeps the heading structure of its English pair.
- Per-epic docs already on `master` are kept unless they are wrong; anchors other pages link to keep working; the file path `guides/ba.md` stays.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: a BA reads five pages to learn the job; the brownfield starter shows the pre-forecast milestone prompt (`Capacity: ... Sizes: ...`, `docs/starters/brownfield.md:231`) and one-line prompts with no reference value; the reference and concept pages were patched per epic and never checked as a whole.
- Success criteria: spec R1–R6 and US-1–US-5; `gin docs check` and `mkdocs build --strict` pass.
- Constraints: the Global Constraints above.
- Non-goals: behaviour changes, new `.vi.md` pairs, role pages other than the BA.

## Approach Options
### Option 1: Tracks per page group, English and Vietnamese together
- Summary: T1 BA guide, T2 starters, T3 accuracy pass, T4 final checks; each track writes the English page and its `.vi.md` pair.
- Pros: pairs never drift; each track is reviewable on its own; T1 and T2 run in parallel.
- Cons: each track needs the Vietnamese skill loaded.

### Option 2: English pass, then a translation pass
- Summary: all English pages first, one translation track after.
- Pros: one English review.
- Cons: pairs drift between tracks; two review rounds per page.

### Recommended Approach
- Selected option: Option 1 (user decision 2026-11-08).
- Rationale: pairs stay in sync and each track can be rejected independently.

## Scope
- In scope: `docs/guides/ba.md`, `docs/roles.md`, `docs/starters/brownfield.md`, `docs/starters/greenfield.md`, `README.md`, `docs/guides/sdd.md`, `docs/reference/cli.md`, `docs/reference/skills.md`, `docs/reference/config.md`, `docs/concepts/architecture.md`, `docs/concepts/lifecycle.md`, their existing `.vi.md` pairs, `mkdocs.yml` nav.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: worker
  workers:
    mode: parallel
  rationale: Track 1 and Track 2 touch disjoint files and run together; Track 3 shares README.md and sdd.md link text with Track 1 and runs after it; Track 4 checks the result of all three.
```

## Conventions for every track

- **Vietnamese.** Before writing any `.vi.md` text, read `/home/gin/.claude/plugins/marketplaces/vietnamese-language-skill/skills/vietnamese-tech-writing/SKILL.md` and the references it names for docs (at least `references/doc-registers.md`, `references/glossary.md`, `references/banned-phrases.md`), then apply them: impersonal technical register, English kept for code, identifiers, commands, file paths, and established terms (spec, epic, track, bead, gate, capability, mockup, worktree). The `gin:docs-writer` agent has no Skill tool, so it reads these files directly; a session with the Skill tool invokes `vietnamese-language-skill:vietnamese-tech-writing` instead. Note in the bead notes that the skill was applied.
- **Heading parity.** For each changed pair: `diff <(grep -c '^#' P.md) <(grep -c '^#' P.vi.md)` prints nothing, and the heading order matches.
- **Checks per track.** `gin docs check <every page the track changed>` prints `ok`.
- **Commits.** One commit per track on its track branch, message `docs(<area>): <summary> (gin-workflow-docs-refresh.<n>)` ending with the `Co-Authored-By` line. Docs-only: no test-suite baseline.

## Tasks
### Track 1: BA guide as one end-to-end page
- **Dependencies**: none
- **Files**:
  - Modify `docs/guides/ba.md` (full rewrite, R1)
  - Modify `docs/guides/ba.vi.md` (full rewrite, R1, R5)
  - Modify `docs/roles.md:21,45-50` (BA row skills gain `/gin-ba:capture`, `/gin-ba:mockup`, `/gin:explain`; BA reading list starts with the new page)
  - Modify `docs/roles.vi.md` (same lines as `roles.md`)
  - Modify `mkdocs.yml:79,121` (nav `BA add-on` → `Business analyst`; Vietnamese nav translation `Business analyst: Business analyst (BA)` replacing `BA add-on: Tiện ích BA`)
  - Modify `README.md:16` (link text `BA add-on` → `business analyst`)
  - Modify `docs/guides/sdd.md:86`, `docs/guides/sdd.vi.md:86` (link text `BA add-on` / `Add-on BA` → `BA guide` / `hướng dẫn cho BA`)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** one page rewritten from a fixed outline in the spec, with all facts already in `ba.md`, `sdd.md`, `team.md`, `roles.md`; needs writing judgement, not cross-module analysis.
- **Steps**:
  1. Read `docs/guides/ba.md`, `docs/guides/sdd.md`, `docs/guides/team.md`, `docs/roles.md`, and `plugins/gin-ba/src/skills/{capture,mockup}/SKILL.md`, `plugins/gin-workflow/src/skills/{discuss,explain}/SKILL.md` for facts. Run `gin specs assets --help` and `gin specs export --help` to confirm flags.
  2. Rewrite `docs/guides/ba.md` with these headings, in order: `# Business analyst`, intro paragraph (one sentence: the page follows the BA's work in order; mechanics live in [SDD living specs](sdd.md) and [team mode](team.md); the legacy layout has no dated asset folders, so steps 2–5 apply to the SDD layout), the existing mermaid flowchart (kept, first node `Dated folder`), `## Your role` (table: Skills, Files, Branch `spec/<epic>-<slug>`, Gate `requirement_confirmed`, approved by another member in team mode), `## Steps` with `### 1. Install gin-ba` (the current install block), `### 2. Open a dated asset folder` (`gin specs assets add`, `docs/specs/<capability>/assets/<YYYY-MM-DD>/description.md`, frozen and continued folders), `### 3. Capture legacy behaviour` (current capture steps), `### 4. Build the mockup` (current mockup section), `### 5. Confirm the inputs` (`Confirmed: <date>`, `gin specs assets confirm`, skills never commit), `### 6. Discuss the epic` (`/gin:discuss <epic-id>`: capabilities-affected table, spec delta, diagrams, `Source:` lines with the current example, `gin specs lint`), `### 7. Open the spec pull request` (`requirement_confirmed`, not self-approved in team mode, link to `team.md`), `### 8. Export and explain` (`gin specs export <capability>`, `/gin:explain <capability|change>`), `## Conventions` (a change after plan approval goes in a new change folder with a `MODIFIED` block; capture legacy behaviour and the REST contract first; common mistakes: a second epic by hand, stories without acceptance criteria, missing legacy edge cases), `## Commands` (current table plus `gin specs assets add|confirm`, `gin specs export`, `/gin:explain`), `## Reading list` (team.md#join-it-member, sdd.md, customizing-templates.md, brownfield.md#discuss-an-epic).
  3. Write `docs/guides/ba.vi.md` with the same headings in Vietnamese (Conventions above).
  4. Update `roles.md`/`roles.vi.md`, `mkdocs.yml`, `README.md:16`, `sdd.md:86`/`sdd.vi.md:86` as listed in Files.
  5. Run `gin docs check docs/guides/ba.md docs/guides/ba.vi.md docs/roles.md docs/roles.vi.md docs/guides/sdd.md docs/guides/sdd.vi.md README.md` → `ok`; heading parity for `ba` and `roles` → no output. Commit.
- **Acceptance criteria**: US-1; `ba.md` has Your role → Steps (8, in the order above) → Conventions → Commands → Reading list; no section of `sdd.md` or `team.md` is repeated beyond one sentence and a link; nav shows `Business analyst`; parity holds.
- **Estimated complexity**: medium

### Track 2: Starters: roadmap process in order and realistic prompts
- **Dependencies**: none
- **Files**:
  - Modify `docs/starters/brownfield.md:193-245` (Roadmap overview and Milestone planning, R2) and every `**Prompt**` block at lines 86, 147-157, 178, 199, 224, 252, 282, 332, 358, 389, 414, 433 (R3)
  - Modify `docs/starters/brownfield.vi.md` (same sections)
  - Modify `docs/starters/greenfield.md:33,61,70,85-86,93,100-129` (R3)
  - Modify `docs/starters/greenfield.vi.md` (same sections)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded rewrite of known sections against shipped skills (`roadmap`, `milestone`) whose specs are on disk; many prompts, but each follows one pattern.
- **Steps**:
  1. Read `.planning/specs/2026-11-08-roadmap-deadline-forecast-design.md`, `.planning/specs/2026-11-08-roadmap-pipeline-design.md`, `plugins/gin-workflow/src/skills/roadmap/SKILL.md`, `plugins/gin-workflow/src/templates/roadmap.md`; run `gin milestone --help`, `gin milestone create --help`, `gin milestone list --help`, `gin milestone show --help`, `gin milestone estimate --help`.
  2. Rewrite Roadmap overview and Milestone planning in `brownfield.md` in three steps (R2): (a) `/gin:roadmap` writes `Deadline:` and `AI capacity:` under `## Constraints`, `## Way of working`, an `Estimate:` per epic stored with `gin milestone estimate`, and a report comparing the forecast with the deadline; (b) `gin milestone create "<title>" --start <date> --end <date> --lanes <N>` then `/gin:roadmap --milestone <id>`, which writes `Spec ready by:` and `Integration point:`; a sprint's lanes may differ from the project capacity; (c) `gin milestone list` prints the forecast line and `gin milestone show <id>` warns `spec_not_ready`; repeat per sprint. Remove the `Capacity: ... Sizes: ...` prompt.
  3. Roadmap prompt (business input only, no `Team:`, no sequencing bullets):
     ```text
     /gin:roadmap Goal: replace the catalog, cart and checkout JSP flows with the Spring Boot REST API and the React SPA.
     Deadline: 2027-05-28.
     Constraints: the Oracle schema stays; no downtime; each module cuts over behind the facade.
     Non-goals: reporting screens.
     ```
  4. Replace every other one-line prompt in both starters with a multi-line prompt for the page's scenario (shop-portal for brownfield, the greenfield page's own project for greenfield) that carries the inputs its `Put in the prompt:` line lists; keep that line as the checklist. Example for discuss:
     ```text
     /gin:discuss shop-portal-catalog-read
     Replace the JSP catalog list and product detail pages. Legacy rules: hidden products never show; price shows the customer's price list, falling back to list price; out-of-stock items show "Notify me".
     API contract: GET /api/products?category=&page=, GET /api/products/{id}; same fields as the JSP model.
     Out of scope: search, reviews.
     ```
  5. For each command and flag in a prompt, confirm it in `gin <group> --help` or the skill's `SKILL.md` argument line; list the checks in the bead notes.
  6. Write the `.vi.md` pairs (Conventions); prompt text inside code blocks stays English.
  7. Run `gin docs check docs/starters/brownfield.md docs/starters/brownfield.vi.md docs/starters/greenfield.md docs/starters/greenfield.vi.md` → `ok`; heading parity → no output; `grep -n 'Sizes:' docs/starters/*.md` → no output; `grep -n '^Team:' docs/starters/*.md` → no output. Commit.
- **Acceptance criteria**: US-2, US-3; anchors `#discuss-an-epic`, `#execute`, `#test-cases` still exist.
- **Estimated complexity**: medium

### Track 3: Accuracy pass over reference, concept, and overview pages
- **Dependencies**: Track 1 (shares `README.md` and `docs/guides/sdd.md`)
- **Files**:
  - Modify `README.md` (mismatches only)
  - Modify `docs/guides/sdd.md`, `docs/guides/sdd.vi.md` (mismatches only)
  - Modify `docs/reference/cli.md` (mismatches only)
  - Modify `docs/reference/skills.md`, `docs/reference/skills.vi.md` (mismatches only)
  - Modify `docs/reference/config.md` (mismatches only)
  - Modify `docs/concepts/architecture.md` (BA stages and `gin-ba` in the flow diagrams and text, R4)
  - Modify `docs/concepts/lifecycle.md` (BA inputs before discuss, SRS export and explain after, R4)
- **Provider role**: `docs`
- **Model:** `sonnet`
- **Effort:** `high`
- **Why:** checks seven pages against three sources (CLI help at flag level, skill sources, config schema); many small edge cases, but each check is mechanical, so effort rises, not the model.
- **Steps**:
  1. CLI: for each group in `gin --help` (setup, state, unblock, record, quick-check, rules, specs, docs, team, usage, reviewer, hooks, evidence, task, routes, notify, paths, goal, worktree, workspace, milestone), run `gin <group> --help` and each subcommand's `--help`; compare commands and flags with `docs/reference/cli.md`. `gin task` passes through to `bd`: check only what cli.md claims about the passthrough.
  2. Skills: compare `ls plugins/*/src/skills/` with the tables in `docs/reference/skills.md` and `skills.vi.md` (plain names, add-on sections), and each row's summary with the skill's `description:` front matter.
  3. Config: find the schema and defaults (`grep -rn 'max_questions' plugins/gin-workflow/src lib 2>/dev/null`), compare keys and defaults with `docs/reference/config.md`.
  4. `README.md`, `sdd.md`, `architecture.md`, `lifecycle.md`: check commands, skill names, and flow against the same sources; add the BA inputs (`gin-ba` capture and mockup, dated asset folders) before discuss and `specs export` / `explain` after it where these pages draw the lifecycle.
  5. Record every mismatch in the bead notes as a table `page:line | claim | shipped behaviour (evidence) | action` (fixed, or the bug bead id created with `gin task create "<title>" -t bug` and linked to the owning epic for a code bug).
  6. Mirror fixes in the existing `.vi.md` pairs (Conventions).
  7. Run `gin docs check` on every changed page → `ok`; heading parity on changed pairs. Commit.
- **Acceptance criteria**: US-4; every table row is fixed or has a bug bead; no `gin-workflow:` skill prefix and no `gin-knowledge` in `docs/` or `README.md` (`grep -rnE 'gin-workflow:[a-z]|gin-knowledge' docs README.md` prints nothing).
- **Estimated complexity**: medium

### Track 4: Final checks
- **Dependencies**: Track 1, Track 2, Track 3
- **Files**:
  - Modify `AGENTS.md` (only if `gin setup refresh` changes it)
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** runs fixed commands and commits their output; no writing judgement.
- **Steps**:
  1. `python3 -m venv "$CLAUDE_JOB_DIR/tmp/mkdocs-venv" && "$CLAUDE_JOB_DIR/tmp/mkdocs-venv/bin/pip" install -q -r requirements-docs.txt` (outside a job, use any temporary directory).
  2. `"$CLAUDE_JOB_DIR/tmp/mkdocs-venv/bin/mkdocs" build --strict -d "$CLAUDE_JOB_DIR/tmp/site"` → exit 0, no `WARNING`.
  3. `gin docs check $(git diff --name-only master -- docs README.md)` → `ok`.
  4. `gin setup refresh`; if `git status --short AGENTS.md` shows a change, commit it.
  5. Paste the outputs of steps 2–4 into the bead notes as evidence.
- **Acceptance criteria**: R6; a failure goes back to the track that owns the page.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/docs-refresh`
- **Merge strategy**: parallel-then-merge (Track 1 and Track 2 in parallel, then Track 3, then Track 4)

## Validation
- [ ] `mkdocs build --strict` passes (Track 4)
- [ ] `gin docs check` passes on every changed page
- [ ] Heading parity on every changed `.vi.md` pair
- [ ] Manual: read `docs/guides/ba.md` top to bottom as a BA new to the project; every step names its command and its files

## Notes
- `Model:` and `Effort:` are chosen from the main harness catalog using the route rubric.
- The user may override `Model:` and `Effort:` before plan approval.
- Provider roles describe responsibility rather than filename patterns.
- The Parent Bead `gin-workflow-docs-refresh` remains open until the human-confirmed merge; track beads close once their checks and review pass, so dependents unblock.
