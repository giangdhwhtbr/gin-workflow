# Capture and mockups in a workspace, and the BA during build

Epic: gin-workflow-ba-workspace
Status: confirmed by the user on 2026-11-12.

## Goal and scope

Mockup reads the target app's design tokens, capture records who confirmed it, the area lead reviews mockups before confirm, business questions raised in execute reach the BA as epic comments, and each epic gets one BA acceptance point.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`, clusters "Capture and mockups in a workspace" and "BA during build", P2) found, checked again on master `1e505465` on 2026-11-11:
- BA-14, FE-LEAD-15: `/gin-ba:mockup` reads "the product's existing UI in the repository" (`plugins/gin-ba/src/skills/mockup/SKILL.md:18-19`). A BA session runs in the workspace parent (`docs/guides/workspace.md:65`), which holds no UI code, so the skill never reads the tokens of the `shape: frontend` child. Nothing says a mockup is optional when the new UI is a 1-1 copy of the legacy screens (only `docs/starters/brownfield.md` does), and no one but the BA sees a mockup before `gin specs assets confirm` (`mockup/SKILL.md:28-34`).
- BA-15: `description.md` has `Kind:`, `Source:`, `Previous:`, and `Confirmed:` only (`plugins/gin-workflow/src/templates/iteration.md`); `gin specs assets confirm` writes the date and records no person (`plugins/gin-workflow/src/scripts/workflow_core/specs_assets.py:109-122`).
- BA-7: on `needs_clarification`, execute notifies and leaves a bead note (`plugins/gin-workflow/src/skills/execute/SKILL.md:36`); no question reaches the BA as an epic comment, and `/gin:progress` lists no open questions.
- BA-10: the BA has no acceptance point after the spec; `docs/guides/git-flow.md` names the BA only for spec pull requests and, by convention, the living-spec diff; the milestone integration point has only a QA sign-off (`plugins/gin-workflow/src/skills/roadmap/references/way-of-working.md:18`).

In scope:
- `/gin-ba:mockup` in a workspace: the frontend child as the visual source, a 1-1 copy needing no mockup, and the area lead's agreement before confirm.
- `Confirmed by:` and `Agreed with:` in `description.md`, written by `gin specs assets confirm`.
- `[gin question]` and `[gin answer]` epic comments between execute and the BA, listed by `/gin:progress`.
- `[gin accept]`: one BA acceptance per epic, checked as a warning by ship.
- Docs and translations for the BA during build.

Out of scope:
- The SDD change flow (`gin-workflow-sdd-team-flow`, shipped).
- A new lifecycle gate for acceptance (rejected in `/discuss`: it needs router, state model, and gin-console changes).
- Lint rules for the new `description.md` lines; folders confirmed before this epic stay valid.

Confirmed summary (user, 2026-11-11): the five findings are open on master; the `[gin ship]` comment of `gin-workflow-sdd-team-flow` changed only that asset folders reach git with the spec pull request, that the BA reviewing the archive diff is a team convention, and that the brownfield starter already says to run mockup only when the new UI differs; the execute stage chain has 50 characters of headroom.

Confirmed decisions (user, 2026-11-11): BA acceptance is an epic comment `[gin accept]` that ship checks with a warning, not a gate; questions during build use `[gin question]` and `[gin answer]` epic comments.

Comments considered: 1, latest 2026-11-11T16:40:55Z

## Requirements

R1. Mockup visual source in a workspace. When `gin state --format json` reports a workspace, step 3 and step 4 of `/gin-ba:mockup` take "the existing UI" from a cloned `shape: frontend` child of `workspace.repos`: the only one, or the one the BA names when there are several. When that child is not cloned, the skill names `gin workspace clone <path>` and continues with the next visual source of step 4. Outside a workspace the skill reads the repository as today.

R2. No mockup for a 1-1 copy. When the BA says the new screens copy the legacy ones without change, `/gin-ba:mockup` writes nothing, says that the confirmed capture folder is the input for `/gin:discuss`, and stops.

R3. Area lead before confirm. In team mode, when an area in `team.areas` has a path glob that matches the frontend child's path (or, outside a workspace, a path of the existing UI the skill read), `/gin-ba:mockup` asks the BA to get that area's lead role's agreement before confirm, and passes the lead's name to `--agreed-with`. The skill never confirms without the BA's explicit answer, as today.

R4. Sign-off lines. `gin specs assets confirm <cap> --date D [--agreed-with TEXT]` writes, after the `Confirmed:` line, `Confirmed by: <git user.email>` and, when `--agreed-with` is given, `Agreed with: <TEXT>`. With no git `user.email` the command refuses with exit 2 and `set git user.email before confirming`, and writes nothing. The JSON result adds `confirmed_by` and `agreed_with` (null when not given). `iteration.md` documents both lines in its comment. `/gin-ba:capture` and `/gin-ba:mockup` ask the BA at confirm time who else agreed (business owner, PM, area lead) and pass it to `--agreed-with`.

R5. Questions during build. When execute cannot answer a worker's `needs_clarification` from the spec or plan, it runs `gin task comment <epic> "[gin question] <track-id>: <question>"`, notifies, and leaves the track `in_progress` with a note. When it resumes an `in_progress` track, it reads `gin task comments <epic> --json` and, when a `[gin answer] <track-id>:` comment is newer than the track's latest `[gin question]`, re-dispatches with that answer. With the markdown task backend there are no comments, and execute keeps today's notify-and-note behaviour.

R6. Open questions in progress. `/gin:progress` lists, per open epic it reports, each `[gin question] <track-id>:` comment with no newer `[gin answer] <track-id>:` comment, with its date and text.

R7. BA acceptance. After the epic's tracks are closed (for an epic behind a feature flag, at the milestone integration point), the BA reviews the epic's `/gin-qa:report` output and runs `gin task comment <epic> "[gin accept] <epic>: <what was checked>"`. This is a team convention.

R8. Ship check. Step 1 of `/gin:ship`: when `team.members` has a member with the role `ba` and `gin task comments <epic> --json` has no `[gin accept]` comment, ship warns `no BA acceptance ([gin accept]) on <epic>` and continues. Outside team mode, or without a `ba` member, ship does not check.

R9. Budgets. The execute stage chain stays at most 12,000 characters, ship and progress chains at most 12,000, and each gin-ba skill at its packaging limit; text added to execute is offset by shortening other execute-chain text without dropping a rule.

R10. Docs. `docs/guides/ba.md` gains a section on the BA during build: answering `[gin question]` comments with `[gin answer]`, and accepting an epic with `[gin accept]`. `docs/guides/git-flow.md` says the BA does not review track pull requests and accepts each epic once. `way-of-working.md` adds the BA acceptance after the QA sign-off at the integration point. `docs/roles.md`, `docs/guides/workspace.md` (PM and BA), `docs/starters/brownfield.md`, `docs/reference/cli.md` (`assets confirm --agreed-with`), and the `.vi.md` translations follow. Each fact has one home and other pages link to it.

## User Stories

### US-1: A mockup that looks like the target app
As a BA in a workspace, I want the mockup to reuse the frontend repository's tokens and components, so that the screens I confirm match what the FE team will build.

Acceptance criteria:
- In a workspace with one cloned `shape: frontend` child, the mockup skill text tells the agent to read that child's tokens, theme, and components.
- With the frontend child not cloned, the skill text names `gin workspace clone <path>` and the fallback visual source.
- When the BA says the screens are a 1-1 copy of legacy, the skill text says to write nothing and go to `/gin:discuss`.

### US-2: Who confirmed and who agreed
As a PM or area lead, I want each confirmed asset folder to say who confirmed it and who agreed, so that a later dispute has a name and not only a date.

Acceptance criteria:
- `gin specs assets confirm catalog --date 2026-11-12 --agreed-with "fe_lead Binh"` writes `Confirmed: <today>`, `Confirmed by: <git user.email>`, and `Agreed with: fe_lead Binh`.
- Without `--agreed-with` only `Confirmed:` and `Confirmed by:` are written.
- With no git `user.email` the command exits 2 with `set git user.email before confirming` and the file is unchanged.
- `gin specs lint` passes on a folder confirmed before this epic (no `Confirmed by:` line).
- In team mode with an area whose path covers the frontend child, the mockup skill text asks for that area lead's agreement before confirm.

### US-3: A developer's business question reaches the BA
As a BA, I want questions the spec does not answer to appear on the epic, so that I answer them before the developer guesses.

Acceptance criteria:
- The execute skill text posts `[gin question] <track-id>: <question>` on the epic when the spec and plan do not answer, and keeps the track `in_progress`.
- On resume, the execute skill text re-dispatches with a newer `[gin answer] <track-id>:` comment.
- `/gin:progress` text lists unanswered `[gin question]` comments per epic.
- The execute, ship, and progress stage chains stay within 12,000 characters (`tests/workflow_core/test_token_budget.py`).

### US-4: One BA acceptance per epic
As a BA, I want to accept each epic once against the QA report instead of reviewing every track pull request, so that my review effort matches the business outcome.

Acceptance criteria:
- `docs/guides/ba.md` describes `[gin accept]` and when to post it.
- `docs/guides/git-flow.md` says the BA does not review track pull requests and accepts each epic once.
- The ship skill text warns when a team with a `ba` member ships an epic without `[gin accept]`, and does not stop.
- `way-of-working.md` puts the BA acceptance after the QA sign-off at the integration point.

## Errors and compatibility

- `assets confirm` without `--agreed-with` and with a git email keeps today's output keys and adds `confirmed_by` and `agreed_with`.
- A missing git `user.email` is a new refusal of `assets confirm` (exit 2); every other refusal is unchanged.
- `confirmed_value_errors` keeps matching only the `Confirmed:` line; `Confirmed by:` and `Agreed with:` are not parsed by lint.
- With the markdown task backend there are no comments: execute, progress, and ship skip the comment steps and say so.
- No new gate, event, or state JSON key; gin-console is unaffected.

## Testing

- `tests/workflow_core/test_specs_assets.py`: `Confirmed by:` from the repository's git `user.email`; `Agreed with:` with and without `--agreed-with`; refusal without `user.email`; lint passes on a folder without `Confirmed by:`; CLI JSON keys.
- `tests/workflow_core/test_token_budget.py`: execute, ship, progress chains within limits.
- `tests/gin_ba/test_ba_packaging.py` (budget and links) for the changed gin-ba skills.
- `gin docs check` on every changed page; `tests/workflow_core/test_docs_coverage.py`.
- Full suite: `python3 -m pytest -n auto`.

## Open Technical Questions
