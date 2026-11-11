# SDD layout and change flow for a team workspace

Epic: gin-workflow-sdd-team-flow
Status: confirmed by the user on 2026-11-11.

## Goal and scope

The brownfield starter sets the SDD layout with a capture step before discuss, and asset folders, in-flight requirement changes, `Source:` lines, spec checklists, cross-child `specs trace`, and the archive pull request follow one team flow.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`, clusters "SDD layout in the brownfield starter" and "SDD change flow for a team workspace", P2) found, checked again on master `c1e50af4` on 2026-11-11:
- BA-1, QA-11: the brownfield starter's setup answers only `stage`, `shape`, and `workspace` (`docs/starters/brownfield.md:92`), so the layout stays `legacy`; no step runs `/gin-ba:capture` before "Discuss an epic" (`brownfield.md:273`); `/gin-qa:setup` never mentions the layout, though without SDD gin-qa has no `missing` or `stale` lists.
- BA-17: `brownfield.md:296-298` tells the team to describe the legacy behavior as living specs, while `Kind: legacy` asset folders (`docs/guides/sdd.md:73`) already hold that behavior.
- BA-6: `docs/guides/ba.md:71,98` says the BA commits asset folders, but the git agreement (`docs/guides/git-flow.md:55-83`) has no branch or approver for them.
- BA-8: `specs lint` rejects a `MODIFIED` or `REMOVED` block whose REQ is `ADDED` in another open change with "is not in the living spec" (`plugins/gin-workflow/src/scripts/workflow_core/specs.py:458-459`), and `gin specs hash` cannot give its base (`specs.py:585-590`), so a change after plan approval (`docs/roles.md:73`, `git-flow.md:154`) cannot target a requirement that has not shipped.
- BA-9: `specs trace` lists files with `git ls-files` in one root (`specs_trace.py:12-16,38`), so in a workspace it never sees tests in the children and names no repository.
- BA-11: the spec checklist reads "The BA reviews a spec and checks that:" (`git-flow.md:92`), and does not say who uses it on spec pull requests the BA did not write.
- BA-12: the agreement asks for a `Source:` line on every requirement (`git-flow.md:96`); the `sdd` skill and guide ask for it only on a requirement taken from an input (`sdd/SKILL.md:13`, `sdd.md:79`).
- BA-19: the archive into the living spec ends in a commit (`sdd/SKILL.md:29`), and the pull request table (`git-flow.md:75-83`) has no row for it.

In scope:
- The brownfield starter: SDD layout, test globs, a capture and mockup step, and how living specs relate to legacy behavior.
- A warning in `/gin-qa:setup` when the layout is not `sdd`.
- The rule for committing confirmed asset folders.
- `MODIFIED` and `REMOVED` blocks that target a requirement `ADDED` in another open change: lint, hash, and archive.
- `specs trace` across workspace children, and the REQ-ID allocation rule it relies on.
- Wording of the spec checklist, the `Source:` rule, and the archive row of the pull request table.

Out of scope:
- BA work during build, mockup tokens, and capture sign-off (`gin-workflow-ba-workspace`).
- Java globs in `DEFAULT_TEST_GLOBS`; the starter sets them in its config instead.
- `migrate-specs` for a project that is not rewritten: it keeps describing current behavior (`sdd.md:164`).

Confirmed decisions (user, 2026-11-11): confirmed asset folders reach git with the spec pull request, with no branch of their own; during a migration, living specs describe only the new system and legacy behavior stays in `Kind: legacy` folders; a requirement still in flight is changed with a working `MODIFIED` block, not by editing the approved change folder.

The epic had no comments.

## Requirements

R1. Starter setup. `docs/starters/brownfield.md` has setup answer `artifacts.layout: sdd` in addition to `stage: brownfield`, `shape: fullstack`, and `workspace`. Its config example sets `artifacts.test_globs` to include the Maven test tree (`**/src/test/**`) next to the JavaScript and Python defaults.

R2. Capture step. `brownfield.md` gains a section "Capture and mockup (BA)" before "Discuss an epic". In it the BA runs `/gin-ba:capture` for each set of legacy screens of the epic's capabilities, and `/gin-ba:mockup` when the new UI differs from the legacy one, then confirms each folder with `gin specs assets confirm`. Discuss cites only confirmed folders.

R3. Living specs during a migration. `brownfield.md` replaces "Capture current behavior first" (`brownfield.md:296-298`), and `docs/guides/sdd.md` adds the same rule: during a migration, living specs describe the shipped new system; legacy behavior stays in `Kind: legacy` asset folders; a requirement taken from legacy behavior names that folder in its `Source:` line. Living specs of a project that is not rewritten still describe current behavior (`sdd.md:164`).

R4. gin-qa setup. `/gin-qa:setup` reads the layout from `gin state --format json` (`project.layout`) and, when it is not `sdd`, warns that `gin-qa cases plan` and `check` then have no `missing` or `stale` lists, and names `artifacts.layout: sdd` as the fix. Setup continues after the warning.

R5. Asset folders reach git with the spec. `docs/guides/git-flow.md`, `docs/guides/ba.md`, and `docs/guides/sdd.md` state: the BA does not commit a confirmed asset folder on its own branch; `/gin:discuss` commits it with the change folder that cites it on `spec/<epic>-<slug>`, and the approvers of that spec pull request (the roles listed for `requirement_confirmed`) approve the assets with it. A confirmed folder no change cites stays uncommitted. `ba.md:71,98` drop "the BA commits asset folders".

R6. `MODIFIED` and `REMOVED` on an in-flight requirement. A requirement is in flight when it is `ADDED` in an open change folder (any folder under the changes directory other than `archive`, with a spec delta) and is not in a living spec.
- `gin specs lint` accepts a `MODIFIED` or `REMOVED` block whose REQ is in flight in another change. A block whose REQ is neither living nor in flight fails with `<REQ> is not in the living spec or an open change`.
- `gin specs hash <REQ>` returns the hash of the living block, else of the in-flight `ADDED` block, and names the change it came from. A REQ in neither fails as today.
- `gin specs archive` of a change with such a block stops with `<REQ> is added by <change>; archive <change> first` while the REQ is not living. Once that change is archived, the base check compares against the living block as today, and the base taken from the `ADDED` block matches it.
- When the targeted REQ is `ADDED` in two open changes, `gin specs hash` and the lint of the `MODIFIED` change fail with `<REQ> is added by <change-a> and <change-b>; renumber one`.

R7. Flow for a change after plan approval. `docs/roles.md`, `docs/guides/git-flow.md`, and `docs/guides/sdd.md` describe it: a new change folder with a `MODIFIED` block whose base comes from `gin specs hash`, whether the requirement has shipped or is still in flight; the approved change folder is never edited; the in-flight change archives first.

R8. `specs trace` in a workspace. When the project root is a workspace parent, `specs trace` scans the parent's tracked files and the tracked files of every child that is cloned and workable (not frozen, not the Beads repository), each with `git ls-files` in that child's main checkout, against the parent's `artifacts.test_globs`. Each source is a path relative to the workspace root, so it starts with the child's path. The JSON payload adds `skipped`: the paths of workable children that are not cloned (an empty list outside a workspace or when all are cloned); the text output lists them. Outside a workspace the output keeps today's keys and values, plus `skipped: []`.

R9. REQ-ID allocation. `docs/guides/sdd.md` and `docs/guides/workspace.md` state the rule trace relies on: in a workspace, requirements and their REQ-IDs live only in the parent's specs, children only reference them; `gin specs next-id` scans the tree, worktrees, and remote branches; and `gin specs lint --against <base>` (run by the `sdd` skill at ship, `sdd/SKILL.md:29`) flags an `ADDED` id already used on the base, with `gin specs renumber` to fix it. The `sdd` skill's spec review step also runs that lint before the spec pull request is opened.

R10. Spec checklist. `git-flow.md` rewords the checklist heading to "The approver of a spec checks that:", and states that the BA uses it on spec pull requests other members author. Other role checklists keep their wording.

R11. `Source:` rule. `git-flow.md:96` reads "every requirement taken from an input has a `Source:` line that names it", matching `sdd/SKILL.md:13` and `sdd.md:79`.

R12. Archive pull request. The pull request table of `git-flow.md` gains a row for the archive of a change into the living spec: it lands with the parent's integration (the change's feature branch merge, or the parent pull request in a workspace), and the BA reviews the living-spec diff. `sdd/SKILL.md` archive step and `docs/guides/workspace.md` name the same reviewer.

## User Stories

### US-1: A brownfield team starts in the SDD layout
As a tech lead following the brownfield starter, I want setup to choose the SDD layout and the BA to capture legacy screens before discuss, so that specs cite confirmed legacy behavior and QA gets `missing` and `stale` lists.

Acceptance criteria:
- `docs/starters/brownfield.md` shows `artifacts.layout: sdd` and `**/src/test/**` in the setup answers and config.
- The section "Capture and mockup (BA)" appears before "Discuss an epic" and names `/gin-ba:capture`, `/gin-ba:mockup`, and `gin specs assets confirm`.
- `brownfield.md` and `sdd.md` say living specs describe the new system and legacy behavior stays in `Kind: legacy` folders cited by `Source:`; "Capture current behavior first" is gone.
- `/gin-qa:setup` in a project with `artifacts.layout: legacy` prints the layout warning and finishes setup.

### US-2: Confirmed assets travel with the spec
As a BA, I want one rule for when my confirmed asset folders are committed, so that I never open a pull request just for assets and reviewers see them with the spec.

Acceptance criteria:
- `git-flow.md`, `ba.md`, and `sdd.md` state that `/gin:discuss` commits a confirmed asset folder with the change folder that cites it on `spec/<epic>-<slug>`.
- No page tells the BA to commit asset folders on their own.

### US-3: Change a requirement that has not shipped
As a BA, I want to change a requirement another epic added but has not shipped, so that a late business change follows the normal flow without editing an approved spec.

Acceptance criteria:
- With `REQ-CART-004` `ADDED` in open change `e1-cart`, a new change with `MODIFIED REQ-CART-004` and the base from `gin specs hash REQ-CART-004` passes `gin specs lint`.
- `gin specs hash REQ-CART-004` prints the hash and names `e1-cart`.
- A `MODIFIED REQ-CART-999` that is neither living nor in flight fails lint with `REQ-CART-999 is not in the living spec or an open change`.
- `gin specs archive` of the new change before `e1-cart` is archived stops with `REQ-CART-004 is added by e1-cart; archive e1-cart first`.
- After `e1-cart` is archived, archiving the new change applies the `MODIFIED` block to the living spec.
- `roles.md`, `git-flow.md`, and `sdd.md` describe this flow and say the approved change folder is never edited.

### US-4: Trace finds tests in every child
As a BA approving a ship in a workspace, I want `specs trace` to find tests in the service, app, and qa repositories, so that a requirement covered in a child is not reported missing.

Acceptance criteria:
- In a workspace whose `qa` child has a test tagged `REQ-CART-004`, `gin specs trace --change <change> --format json` lists `REQ-CART-004` as `covered` with a source starting `qa/`.
- A frozen child and the Beads repository are not scanned.
- A workable child that is not cloned appears in `skipped`, and the text output names it.
- Outside a workspace the payload equals today's plus `skipped: []`.
- `sdd.md` and `workspace.md` state that REQ-IDs live only in the parent's specs and that the spec pull request runs `gin specs lint --against <base>`.

### US-5: One team flow in the git agreement
As a BA reviewing spec pull requests and archives, I want the git agreement to say what I check, when a `Source:` line is needed, and where I review the living-spec diff, so that the agreement matches the `sdd` skill.

Acceptance criteria:
- The checklist heading reads "The approver of a spec checks that:" and says the BA uses it on spec pull requests other members author.
- The `Source:` item applies to a requirement taken from an input.
- The pull request table has an archive row with the BA as reviewer of the living-spec diff, and `sdd/SKILL.md` names the same reviewer.

## Errors and compatibility

- Lint, hash, and archive messages for living requirements are unchanged; only the message for a REQ that is neither living nor in flight changes (R6).
- `specs trace --format json` only adds `skipped`; gin-console does not read trace output.
- A project without `workspace.repos` traces exactly as today.
- A child whose `git ls-files` fails is listed in `skipped` instead of stopping the trace.
- Skill files stay within their character budgets (`tests/` budget tests).

## Testing

- `tests/workflow_core/test_specs.py`: lint accepts `MODIFIED` and `REMOVED` on an in-flight REQ; lint rejects a REQ neither living nor in flight with the new message; `hash` returns the in-flight block's hash and change.
- `tests/workflow_core/test_specs_archive_trace.py`: archive stops while the target change is open, then applies after it is archived; trace in a workspace fixture with a parent and three children (one cloned workable, one frozen, one not cloned) reports child sources, skips the frozen child, and lists the missing one in `skipped`; trace outside a workspace adds only `skipped: []`.
- Docs and skill tests already in `tests/` (links, budgets, wording checks) pass; new wording checks cover R5, R10, R11, and R12 where a docs test exists for that page.
- Full suite: `python3 -m pytest -n auto`.

## Open Technical Questions
