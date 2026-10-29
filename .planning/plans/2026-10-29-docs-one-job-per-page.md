# Plan: docs reorganization, one job per page

Epic: gin-workflow-tvf5
Spec: `.planning/specs/2026-10-28-docs-one-job-per-page-design.md`

## Objective

Every topic in `docs/` lives on one page. The four role handbooks and the team roles starter are replaced by one `docs/roles.md`. The two brownfield starters each have one job. The README docs map links every page under `docs/`, and a test keeps it that way.

## Goal

Bring the pages added on branch `chore-role-handbooks` back to the docs-rewrite rules (`.planning/specs/2026-10-04-docs-rewrite-design.md`): one job per page, one copy of each topic, every statement checked against the code.

## Architecture

- `docs/roles.md` holds who owns what, the reading path for each role, and the team conventions that keep work apart. It links to the pages that own the mechanics and repeats none of them.
- The feature pages own their topics:
  - `docs/guides/qa.md` owns the QA add-on, including the prompts, rule examples and ship checklist that move there from `qa-guide.md`.
  - `docs/guides/sdd.md` owns living specs, including images and mockups.
  - `docs/guides/customizing-templates.md` owns template overrides.
  - `docs/guides/team.md` owns team mechanics.
- `docs/starters/brownfield-walkthrough.md` owns the end-to-end flow. `docs/starters/brownfield-modernize.md` owns the modernization strategy.
- `README.md` "Documentation" links every `docs/**/*.md`. `tests/workflow_core/test_docs_coverage.py` fails on a page it does not link.

## Tech Stack

Markdown, Python 3 stdlib (`re`, `pathlib`), unittest.

## Global Constraints

Copied from the spec:
- Out of scope: the Windows page (`docs/guides/windows.md`) and the Windows section of `docs/contributing.md`. `docs/guides/recommended-tools.md` keeps its path: `setup_service.py` and the `setup` skill link to its GitHub URL.
- Deleted and renamed pages break outside links to them. They were added on this unmerged branch, so no released link breaks.
- When `fix/windows-support` merges, `docs/guides/windows.md` must appear in the README docs map, or the new test fails. Whichever branch merges second resolves this.
  - `fix/windows-support` merged first (PR #4), so this branch adds the README link to `windows.md`, and only the link.
- Relative links to removed files are caught by the existing `test_relative_links_resolve`.

Style rules (spec R4), for every page this epic adds content to or edits as a whole:
- no numbered headings;
- sentence case headings;
- no promotional wording;
- slash commands written as `/gin-workflow:<skill>` or `/gin-qa:<skill>`;
- every CLI command named on the page exists in `docs/reference/cli.md`.

Repository rules: no commits on `master`. Docs state only what the code does.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `standard_impl`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: see the spec's Goal and Requirements 1–6.
- Success criteria: the spec's US-1 to US-4 acceptance criteria, proven by:
  - `tests.workflow_core.test_docs_coverage`, with the new orphan test;
  - the style checks in each track;
  - the full suite.
- Constraints: Global Constraints above.
- Non-goals: the Windows page content, `recommended-tools.md`, and a style pass on pages that only get a link fixed.

## Approach Options
### Option 1: three tracks (roles and handbooks, brownfield and templates, orphan test)
- Summary: Track 1 removes the handbooks and creates `roles.md`, Track 2 splits the brownfield pages and restyles the templates page, and Track 3 adds the test and completes the README map.
- Pros: each track can be reviewed and rejected on its own; the content moves are reviewed apart from the test.
- Cons: tracks share the README and the brownfield pages, so they run in order.

### Option 2: one track
- Summary: every requirement in one change.
- Pros: one review.
- Cons: a 1,500-line docs diff in one review; one rejection blocks all of it.

### Recommended Approach
- Selected option: Option 1.
- Reasoning: the handbook removal, the brownfield split and the test are separable units, and each has its own checks.

## Scope
- In scope: spec Requirements 1–6.
  - Link-only fixes on `docs/getting-started.md`, `docs/guides/team.md` and `docs/starters/greenfield.md`, which link to deleted pages.
  - The README link to `docs/guides/windows.md`.
- Out of scope:
  - the spec's out-of-scope list;
  - a style pass on `getting-started.md`, `team.md` and `greenfield.md`, which only get a link fixed (they keep their numbered headings).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three docs tracks that share README.md and the brownfield pages; one session runs them in order.
```

## Tasks

### Track 1: one roles page; handbooks merged into feature pages and deleted
- **Dependencies**: none
- **Files**:
  - Create `docs/roles.md`
  - Delete `docs/starters/team-roles.md`
  - Delete `docs/guides/pm-guide.md`, `docs/guides/ba-guide.md`, `docs/guides/dev-guide.md`, `docs/guides/qa-guide.md`
  - Modify `docs/guides/qa.md:5` (handbook link removed) and append sections after `## End-to-end specs`
  - Modify `docs/guides/sdd.md:42-64` (new section after `## Requirements`; line 64 handbook link removed)
  - Modify `README.md:10-13` (Starters row, Role Handbooks row)
  - Modify `docs/getting-started.md:91` (link only)
  - Modify `docs/guides/team.md:3` (link only)
  - Modify `docs/starters/greenfield.md:159` (link only)
  - Modify `docs/starters/brownfield-walkthrough.md:8-14` (team table links only)
  - Modify `docs/starters/brownfield-modernize.md:145` (link only)
- **Provider role**: `general`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Estimated complexity**: medium
- **Interfaces produced**: the `docs/roles.md` headings `### PM`, `### BA`, `### Developer and tech lead` and `### Tester`, with anchors `#pm`, `#ba`, `#developer-and-tech-lead` and `#tester`. Track 2 links to them.
- **Acceptance criteria**: US-1 and US-2 of the spec.
- **Steps**:
  1. Create `docs/roles.md` with exactly these sections, in this order. Every statement below has been checked against `plugins/gin-workflow/src/skills/gin-team/SKILL.md`, `gin-sdd/SKILL.md`, `roadmap/SKILL.md` and `docs/guides/team.md`.
     - `# Team roles`
     - An intro paragraph, which says:
       - In [team mode](guides/team.md) each member holds roles, each area of the repository has a lead role, and a gate can require approval from listed roles.
       - This page suggests how a PM, a BA, developers and testers split the work, and what each of them reads.
       - gin-workflow enforces only what `team.areas` and `team.approvals` configure.
     - `## Who owns what`: the matrix from `team-roles.md:11-16`, rewritten as follows.

       | Role | Skills | Files | Branch | Approves |
       |---|---|---|---|---|
       | PM | `/gin-workflow:roadmap`, `/gin-workflow:progress`, `/gin-workflow:report` | `.planning/roadmap.md` (`docs/roadmap.md` with the SDD layout) | `roadmap/<topic>` | `roadmap` |
       | BA | `/gin-workflow:discuss`, `/gin-workflow:tech-doc`, `/gin-workflow:progress` | `.planning/specs/` (`docs/specs/` and `docs/changes/` with the SDD layout) | `spec/<topic>` (`spec/<epic>-<slug>` with the SDD layout) | `requirement_confirmed` |
       | Developer and tech lead | `/gin-workflow:plan`, `/gin-workflow:orchestrate`, `/gin-workflow:execute`, `/gin-workflow:review`, `/gin-workflow:ship` | source and test paths, `.planning/plans/` | `plan/<topic>`, then `feat/<topic>-t<N>` per track | `plan_approved` |
       | Tester | `/gin-qa:cases`, `/gin-qa:e2e`, `/gin-workflow:progress` | `qa/cases/`, `qa/e2e/`, `qa/evidence/` | reviews the developer's pull request | `ship` |
     - `## What each role reads`, with one `###` subsection per role. Each is a numbered reading list of links only; no mechanics.
       - `### PM`: the Roadmap, Sprint planning, and Ship and sprint review sections of the [brownfield walkthrough](starters/brownfield-walkthrough.md) (no anchors; name the sections in text); [AI usage report](guides/usage-report.md); [skills reference](reference/skills.md).
       - `### BA`: [getting started](getting-started.md); [SDD living specs](guides/sdd.md); [customizing templates](guides/customizing-templates.md); the Discuss an epic section of the [brownfield walkthrough](starters/brownfield-walkthrough.md).
       - `### Developer and tech lead`: [getting started](getting-started.md); [lifecycle and gates](concepts/lifecycle.md); [team mode](guides/team.md); [rule packs](guides/rules.md).
       - `### Tester`: [QA add-on](guides/qa.md); the Requirements section of [SDD living specs](guides/sdd.md#requirements); the Test cases and E2E sections of the [brownfield walkthrough](starters/brownfield-walkthrough.md).
     - `## Keeping work apart`: the safeguards from `team-roles.md:102-116`, one bullet each.
       - Requirement changes after plan approval (a team convention): do not edit the in-flight spec. With the SDD layout, the change goes in a new change folder whose `MODIFIED` block carries the base hash of the requirement it replaces, and `gin-qa cases plan` shows which test cases went stale.
       - Tests (a team convention): developers own unit and integration tests next to the code; testers own acceptance cases and end-to-end specs under `qa/`. Give each its own area in `team.areas`, so plans keep them apart.
       - Worktrees: each track runs in its own worktree created by `/gin-workflow:orchestrate`.
       - Claims, hand-overs and approvals: one sentence each, linking to [team mode](guides/team.md) for the mechanics:
         - a claim fails while someone else holds the bead;
         - `gin-workflow team reassign` hands a track over;
         - a gate with roles is recorded only with an approved pull request, never approved by its author.
  2. Edit `docs/guides/qa.md`:
     - Delete line 5 (the QA Guide link) and the blank line after it.
     - Append the following sections, in this order, before `## Commands`.
     - `## Prompts`:
       - The three prompts from `qa-guide.md:100-114`, each as a `###` heading in sentence case with a blockquote. Use these headings: "Cover a requirement in depth", "Check a pull request against the cases", "Diagnose an end-to-end failure".
       - Keep the prompt text as written. In the second prompt, replace "PR #45 for `AUTH-101-social-login`" with "pull request #45".
     - `## Team rules`:
       - One sentence: `/gin-qa:cases` and `/gin-qa:e2e` read `qa/guidelines.md` (`qa.guidelines`) first, and its rules override their defaults.
       - Two example rules:
         - "Every `Priority: high` requirement has at least one `Type: e2e` case." The handbook said `P1`; the case format has `Priority: high | medium | low`.
         - "Steps start with an action verb: Navigate, Enter, Click, Verify."
       - Then: "File format, extra fields, and end-to-end rules: [customizing templates](customizing-templates.md)."
     - `## Ship approval checklist`, starting with "With `team.approvals.ship` listing a tester role, the tester approves the latest commit of the developer's pull request after checking:"
       - `gin-qa cases plan` reports no `missing` and no `stale` cases.
       - `gin-qa cases check` exits 0.
       - `gin-qa e2e run` passes, and `gin-qa e2e check --run <folder>` exits 0 on its evidence.
       - The approval comment names the evidence folder.
       - End with: "A commit pushed after the approval needs a new approval ([team mode](team.md))."
     - Drop the rest of `qa-guide.md`, which repeats this page:
       - the intro and "Why QA Loves This Workflow";
       - the case format and the `cases plan`, `pin` and `e2e` mechanics;
       - the customization link.
  3. Edit `docs/guides/sdd.md`:
     - After the `## Requirements` section (which ends at line 42), add `## Images and mockups`:
       - Store screenshots, mockups and diagrams for a capability in `docs/specs/<capability>/assets/`, as `.png`, `.jpg`, `.svg` or `.webp` files with kebab-case names that say the screen and state (`login-form-error.png`).
       - Link them from a requirement with a path relative to the living spec (`![Login form](assets/login-form.png)`). `specs archive` copies requirement blocks into `docs/specs/<capability>/spec.md` unchanged, so the link resolves there after ship.
       - An agent in `/gin-workflow:discuss` can read the images when you point it at them.
     - Do not carry over the `ba-guide.md:54` claim that `specs lint`, `trace` and `archive` inspect only `spec.md` and `spec-delta.md`. The code does not confirm it:
       - `specs_trace.py` also reads `tests.md` and test files;
       - `specs.renumber` reads every `*.md` in the change folder.
     - Do not carry over the in-flight `docs/changes/<change>/assets/` convention either. Archive copies block text into the living spec, so those relative links would break.
     - On line 64, delete the sentence "The [BA Guide](ba-guide.md) explains how Business Analysts define specs and attach visual mockups."
     - Lines 5 and 60: write the bare `/migrate-specs` as `/gin-workflow:migrate-specs`. Leave the branch name `chore/migrate-specs` as it is.
  4. Delete `docs/guides/pm-guide.md` without moving anything. `roles.md` links its topics. Its statements that the code does not back are dropped:
     - `gin-workflow task label` (the code uses `gin-workflow task update <epic> --add-label sprint:<name>`, in `roadmap/SKILL.md:29`);
     - the named model versions.
  5. Delete `docs/guides/dev-guide.md` without moving anything. Every statement is either owned elsewhere or not backed by code.
     - Owned elsewhere:
       - `Requirements:` per track and REQ-IDs in tests: `sdd.md` "How the stages change";
       - `Area:`/`Owner:`, `team ready`, `team claim` and `team check-plan`: `team.md`;
       - worktrees and the review ledger: `concepts/lifecycle.md`;
       - review responses: the `gin-review-response` skill in `reference/skills.md`.
     - Not backed by code:
       - "ship runs the full test suite" (ship runs no tests; git hooks do);
       - `bd list --spec auth`.
  6. Delete `docs/guides/ba-guide.md` (its content moved in step 3), `docs/guides/qa-guide.md` (moved in step 2) and `docs/starters/team-roles.md` (moved in step 1).
  7. Fix every link to a deleted page. `git grep -n -E "pm-guide|ba-guide|dev-guide|qa-guide|team-roles" -- . ':!.planning'` lists them.
     - `README.md:10`: remove `, [team roles (PM/BA/Dev/Tester)](docs/starters/team-roles.md)` from the Starters row.
     - `README.md:13`: replace the Role Handbooks row with `| [Team roles](docs/roles.md) | who owns what in a team, and what each role reads |`.
     - `docs/getting-started.md:91`: replace the line with `- 👥 **Working in a team?** Read [Team roles](roles.md).`
     - `docs/guides/team.md:3`: replace the last sentence with `For how a PM, a BA, developers, and testers split the work, see [Team roles](../roles.md).`
     - `docs/starters/greenfield.md:159`: replace with `- **Collaborating with a team?** Read [Team roles](../roles.md).`
     - `docs/starters/brownfield-walkthrough.md:8-14`: rename the column `Handbook` to `Reads`. Its links become `[PM](../roles.md#pm)`, `[BA](../roles.md#ba)`, `[Developer](../roles.md#developer-and-tech-lead)` (rows Binh and Em) and `[Tester](../roles.md#tester)`.
     - `docs/starters/brownfield-modernize.md:145`: replace with `- **Collaborating with BA, Dev, and Tester?** Read [Team roles](../roles.md).`
  8. Check the style of `docs/roles.md`, `docs/guides/qa.md` and `docs/guides/sdd.md`:
     - `grep -nE '^#{1,4} [0-9]+\.' docs/roles.md docs/guides/qa.md docs/guides/sdd.md`. Expected: no output.
     - `grep -nP '(?<![:\w])/(discuss|plan|orchestrate|execute|ship|review|roadmap|progress|report|tech-doc|setup|quick|workflow|migrate-specs|team-setup|cases|e2e)(?=[\s\x60)]|$)' docs/roles.md docs/guides/qa.md docs/guides/sdd.md`. Expected: no output.
     - `grep -niE 'loves|official|seamless|powerful|comprehensive|beginner-friendly|proven' docs/roles.md docs/guides/qa.md docs/guides/sdd.md`. Expected: no output.
     - Read every heading on the three pages and confirm it is in sentence case.
     - Confirm that every `gin-workflow …` and `gin-qa …` command on the three pages has its subcommand in `docs/reference/cli.md`.
  9. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage`. Expected: `OK`. `test_relative_links_resolve` proves that no link points to a deleted page.
  10. Run `git grep -n -E "pm-guide|ba-guide|dev-guide|qa-guide|team-roles" -- . ':!.planning'`. Expected: no output.
  11. Commit: `docs: one team roles page; handbooks merged into the pages that own each topic`, with `Refs: gin-workflow-tvf5`.

### Track 2: brownfield pages split by job; templates page restyled
- **Dependencies**: Track 1
- **Files**:
  - Modify `docs/starters/brownfield-modernize.md` (rewritten as a strategy page)
  - Modify `docs/starters/brownfield-walkthrough.md` (headings, stage references, `Customizing outputs`, `bd` commands)
  - Modify `docs/guides/customizing-templates.md` (style pass; template table moved in from the walkthrough)
- **Provider role**: `general`
- **Reasoning**: `medium`
- **Model guidance**: `standard_impl`
- **Estimated complexity**: medium
- **Interfaces consumed**: the `docs/roles.md` anchors from Track 1.
- **Acceptance criteria**: US-3 of the spec; style rule R4 on the three pages.
- **Steps**:
  1. Rewrite `docs/starters/brownfield-modernize.md` with these sections, in this order:
     - `# Brownfield modernization`
     - An intro of two sentences:
       - In an existing codebase the code is often the only specification, so preventing regressions comes first.
       - This page covers the strategy for replacing a legacy system piece by piece; the [brownfield walkthrough](brownfield-walkthrough.md) covers setup, the survey, the roadmap and every lifecycle stage.
     - `## Capture current behavior first`: one paragraph. Before changing a capability, describe its current behavior as living specs, including the legacy edge cases, validation rules and error codes. Then:
       - keep the `REQ-AUTH-001` example from lines 64-67, without the word "seamlessly";
       - link [migrating to the SDD layout](../guides/sdd.md#migrating) for the setup.
     - `## Strangler fig`: lines 71-86, restyled:
       - no "Never attempt", no bold step labels;
       - keep the `team.areas` YAML and the note that the facade or gateway is your own infrastructure, not part of gin-workflow.
     - `## Parity and characterization tests`: lines 92-98 as written (the golden-master steps). Then one sentence: "With the gin-qa add-on, test cases pin the hash of the requirement they test, so a changed requirement shows its stale cases: see the [QA add-on](../guides/qa.md)."
       - Drop the `TC-AUTH-001` example and the `gin-qa cases plan` line, which `qa.md` owns.
     - `## Migration cycle`, which keeps only what is specific to a migration:
       - what to settle in `/gin-workflow:discuss`: the data migration strategy (dual-write or backfill) and the rollback criteria;
       - the five-track split from lines 123-127, for `/gin-workflow:plan`;
       - that parity tests and data validation scripts run in the `pre-push` hook once they are in `verify.checks` ([configuration](../reference/config.md#verifychecks)).
       - For the stages themselves, link [lifecycle and gates](../concepts/lifecycle.md).
     - `## Related`: links to the modernization deck (HTML and PPTX), the [brownfield walkthrough](brownfield-walkthrough.md), [team roles](../roles.md), the [QA add-on](../guides/qa.md) and [gin-orchestrator](../orchestrator/README.md). Each is one plain line, with no question-style bold labels.
     - Remove the old sections 1 (setup) and 2 (the tech-doc survey) entirely. The walkthrough's "Survey the legacy system" section owns the survey. Before deleting, confirm that the ten tech-doc file names in `brownfield-modernize.md:37-46` match the list in `brownfield-walkthrough.md:88`.
  2. Edit `docs/starters/brownfield-walkthrough.md`:
     - Title: `# Brownfield walkthrough: from legacy code to sprint delivery`.
     - Add a blank line between the intro and `## The scenario` (line 3-4). After the intro, add: "For the modernization strategy itself (strangler fig, parity tests, the migration cycle), see [brownfield modernization](brownfield-modernize.md)."
     - Drop the numbers from the ten stage headings: `## Setup`, `## Survey the legacy system`, `## Roadmap`, `## Sprint planning`, `## Discuss an epic`, `## Plan and orchestrate`, `## Test cases`, `## Execute`, `## E2E`, `## Ship and sprint review`.
     - Line 182: replace "run stage 5 first" with "run [Discuss an epic](#discuss-an-epic) first".
     - Solo variant: replace "Stage 3:" with "Roadmap:" and "Stage 8:" with "Execute:".
     - Line 118: replace "`bd list --label sprint:2026-s1` shows it" with "`gin-workflow task list --label sprint:2026-s1 --all` shows it".
     - Line 122: replace "`bd ready` still hides blocked epics" with "`gin-workflow task ready` still hides blocked epics".
     - Solo variant: replace "`bd ready` instead of `team ready`" with "`gin-workflow task ready` instead of `gin-workflow team ready`".
     - Replace the whole `## Customizing outputs` section (lines 218-249) with: "Every artifact starts from a template you can override; test cases follow `qa/guidelines.md`. See [customizing templates](../guides/customizing-templates.md)."
  3. Restyle `docs/guides/customizing-templates.md`:
     - Title: `# Customizing templates`.
     - Intro: one sentence, without "By leveraging": "Override the templates gin-workflow and gin-qa write from, and the rules gin-qa follows, to match your team's formats."
     - Drop the `---` separators.
     - Rename the sections: `## How overrides work`, `## Spec, story, and roadmap templates`, `## Test case guidelines and fields`, `## The end-to-end evidence fixture`, `## Summary`.
     - Sub-headings: "Mechanism A: The Rulebook" becomes `### The guidelines file`; "Mechanism B: Custom Metadata Fields in Test Cases" becomes `### Extra fields`; "Step-by-Step Walkthrough" is removed (keep its numbered list); "Inspecting Built-in Templates" becomes `### Built-in templates`.
     - In the built-in templates list (line 28), add `roadmap.md`, `epic.md` and `design-spec.md`. These are the files in `plugins/gin-workflow/src/templates/`.
     - Add, after that list, the "Template | Used by | Override file" table from `brownfield-walkthrough.md:222-228`, with three more rows:
       - `spec.md` | `specs archive` (a new capability) and `/gin-workflow:migrate-specs` | `.agent-workflow/templates/spec.md`
       - `specs-README.md` | `specs archive` and `specs migrate` | `.agent-workflow/templates/specs-README.md`
       - `team/*` | `gin-workflow team init` | `.agent-workflow/templates/team/<file>`
     - Summary table, Living spec row: replace "New specs created by `/discuss` or `specs archive` adopt this layout." with "A new capability's spec from `specs archive`, and the specs `/gin-workflow:migrate-specs` seeds, start from it." (`template_text(root, "spec.md")` is called only in `specs_archive.py` and the migrate-specs skill.)
     - Summary table: remove the bold from the artifact cells.
  4. Check the style of the three pages:
     - Run the three `grep` checks of Track 1 step 8 on `docs/starters/brownfield-modernize.md docs/starters/brownfield-walkthrough.md docs/guides/customizing-templates.md`. Expected: no output.
     - Read every heading and confirm it is in sentence case.
     - Confirm that every `gin-workflow …` and `gin-qa …` subcommand on the three pages appears in `docs/reference/cli.md`.
  5. Check the job split:
     - `grep -niE 'strangler|parity|golden' docs/starters/brownfield-walkthrough.md`. Expected: only the line added in step 2.
     - `grep -niE '/gin-workflow:(setup|tech-doc)|^## .*(setup|survey)' docs/starters/brownfield-modernize.md`. Expected: no output.
  6. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage`. Expected: `OK`.
  7. Commit: `docs: brownfield pages split by job; templates page restyled`, with `Refs: gin-workflow-tvf5`.

### Track 3: README docs map lists every page, enforced by a test
- **Dependencies**: Track 1
- **Files**:
  - Test `tests/workflow_core/test_docs_coverage.py:39-48` (new test after `test_relative_links_resolve`)
  - Modify `README.md:14-16` (Guides and Reference rows)
- **Provider role**: `general`
- **Reasoning**: `low`
- **Model guidance**: `cheap_simple`
- **Estimated complexity**: low
- **Acceptance criteria**: US-4 of the spec.
- **Steps**:
  1. In `tests/workflow_core/test_docs_coverage.py`, add after `test_relative_links_resolve`:
     ```python
         def test_every_docs_page_is_in_the_readme_map(self):
             readme = ROOT / "README.md"
             linked = {(ROOT / target.split("#", 1)[0]).resolve()
                       for target in LINK.findall(readme.read_text(encoding="utf-8"))}
             self.assertEqual([str(p.relative_to(ROOT)) for p in sorted(DOCS.rglob("*.md")) if p.resolve() not in linked], [])
     ```
  2. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_docs_coverage`. Expected: one failure in `test_every_docs_page_is_in_the_readme_map` listing `docs/guides/windows.md`, `docs/presentations/brownfield-modernization-script.md` and `docs/reference/orchestrator-contract.md`.
  3. In `README.md`:
     - Guides row (line 14): add `[Windows](docs/guides/windows.md)` after `[recommended tools](docs/guides/recommended-tools.md)`.
     - Reference row (line 16):
       - add `[orchestrator contract](docs/reference/orchestrator-contract.md)` after `[troubleshooting](docs/reference/troubleshooting.md)`;
       - change `[Modernization deck](docs/presentations/brownfield-modernization.html) ([PPTX](docs/presentations/brownfield-modernization.pptx))` to `[Modernization deck](docs/presentations/brownfield-modernization.html) ([PPTX](docs/presentations/brownfield-modernization.pptx), [script](docs/presentations/brownfield-modernization-script.md))`.
  4. Run the command of step 2. Expected: `OK`.
  5. Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`. Expected: `OK`.
  6. Commit: `test(docs): every docs page is linked from the README docs map`, with `Refs: gin-workflow-tvf5`.

## Integration
- **Branch**: `chore-role-handbooks` (`master` merged in at `6bad396`)
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all` passes.
- [ ] `git grep -n -E "pm-guide|ba-guide|dev-guide|qa-guide|team-roles" -- . ':!.planning'` prints nothing.
- [ ] The style `grep` checks of Track 1 step 8 print nothing on the six pages edited in Tracks 1 and 2.

## Notes
- Track beads close after tests and review pass. Only the parent epic `gin-workflow-tvf5` waits for a human-confirmed merge.
- Track 3 depends only on Track 1, because its test passes on any tree where `roles.md` exists and the handbooks are gone. It runs after Track 2 in this sequential plan.
- Pages that only get a link fixed (`getting-started.md`, `team.md`, `greenfield.md`, and the README rows) are not restyled. Their numbered headings stay, which keeps this epic to the pages the spec names.
