# Role-aware discuss: business-only questions for a business member, technical questions resolved at plan

Epic: gin-workflow-746z
Status: draft for user review.

## Goal and scope

In team mode, a BA who runs `/gin:discuss` is asked technical questions they cannot answer. Discuss does not look at the runner's roles: step 3 asks them to pick one of two or three technical approaches, and step 4 asks them to confirm architecture, components, data flow, error handling, and testing section by section (`plugins/gin-workflow/src/skills/discuss/SKILL.md`). The `team` skill adds only the pull request for `requirement_confirmed` (`skills/team/SKILL.md`, `## discuss`).

Once the spec is confirmed, no stage lets a technical member settle open technical questions. Plan has no clarify step: it copies Goal, Architecture, Tech Stack, and Global Constraints from the spec and returns to discuss when anything is unclear (`skills/plan/SKILL.md` steps 1, 2, and 6).

This spec changes the skills and the CLI so that:
- in team mode, discuss run by a member with no technical role asks business questions only and writes every technical point it finds as an open technical question in the design doc;
- plan resolves each open technical question with the technical member who runs it, writes the decision under the question, and, with the SDD layout, completes the empty technical sections of `03-design.md`;
- `gin record plan-approved` refuses while the design doc still has an open technical question.

Decisions confirmed with the user:
- A role is technical when it is the `lead` of an area or listed in an area's `roles`. A member holding no technical role is business-only. No new config key.
- Technical questions are resolved at the start of `plan`, not in a second discuss pass or a new stage.
- The CLI enforces it at `record plan-approved`, not only the skill text.
- Questions and their decisions both live in the design doc (legacy: the spec file; SDD: the change's `03-design.md`), because the CLI finds the design doc from the workflow id in every mode, while in team mode `plan-approved` evidence is a pull request URL and the plan path is not always given.
- With the SDD layout, plan fills only the empty `## Architecture`, `## Error Handling`, and `## Testing` sections of `03-design.md`; it never rewrites a section someone already wrote.

Out of scope:
- A new lifecycle stage or gate, and changes to `gin state` gates.
- A config key that classifies roles.
- Checking that the technical sections of `03-design.md` are filled: an empty section stays a reviewer's call.
- gin-console: it reads none of the new fields.

## Requirements

### R1. Technical member flag
- `team.summary()` (`scripts/workflow_core/team.py:172`) adds `technical: bool` to `me`. It is true when any of the member's roles is the `lead` of an area or appears in an area's `roles`.
- An area with no `roles` counts only its `lead` role: `TeamConfig.eligible` (`team.py:57`) makes every member eligible for such an area, so `me.areas` cannot tell a business member apart.
- `me` stays `null` when `git config user.email` is not a member, and `project.team` stays `{"enabled": false, "host": null, "me": null}` in solo mode.
- `gin state --format json` exposes the flag as `project.team.me.technical`; `gin team whoami` shows it.

### R2. Business-only discuss
- The `team` skill's `## discuss` section says: when `project.team.me.technical` is false, ask only business questions (purpose, users, rules, edge cases, validation, acceptance criteria, scope, out of scope); skip proposing approaches; present only the business sections of the design; never ask the runner to choose or confirm a technical option.
- Every technical point found while exploring or clarifying goes into the design doc's `## Open Technical Questions` as one open question, not into the assumptions.
- Activity and state diagrams stay with discuss: they describe the business flow.
- A member with at least one technical role, solo mode, and `me: null` keep today's discuss.
- The text lives in the `team` skill, which loads on demand, so the discuss chain does not grow.

### R3. Open technical questions format
- Section `## Open Technical Questions` in the legacy design spec and in the SDD `03-design.md`.
- One question per line: `- TQ-<n>: <question>`, `<n>` a positive integer unique in the file.
- A question is resolved when the next line is indented and reads `Decision: <text>` with non-empty text. A decision may be "not needed, because ...".
- Lines inside fenced code blocks are ignored.
- The templates `templates/design-spec.md` and `templates/design.md` add the section with a comment that shows the format and says that a business-only discuss writes it and plan resolves it.

### R4. Lint
- A shared parser in `scripts/workflow_core/specs.py` returns each question with its line and decision.
- `specs lint --spec` (legacy, `lint_design_spec`, `specs.py:71`) and `specs lint --change` (SDD) report: a line in the section that is neither a question nor its decision, a duplicate `TQ-<n>`, and an empty `Decision:`.
- An open question is not a lint error, so `record requirement-confirmed`, which runs the legacy lint (`lifecycle_cli.py:252`), still records a spec with open questions.

### R5. Plan resolves the questions
- `skills/plan/SKILL.md` step 1: when the design doc has an open `TQ-<n>`, ask the runner about each one in turn, one question per message with two or three options and a recommendation, write `Decision:` under the question, and carry the decisions into the plan's `## Approach Options` and `### Recommended Approach`.
- With the SDD layout, then fill each empty `## Architecture`, `## Error Handling`, and `## Testing` section of `03-design.md` from the decisions and the plan; leave a section that already has text unchanged.
- The design doc changes are committed with the plan. In team mode they go in the plan pull request, so the approver of `plan_approved` reviews both; the `team` skill's `## plan` section says so.
- The rule applies outside team mode too: a spec written by hand can carry open questions.

### R6. Record refuses open questions
- A new function finds the design doc of a workflow id:
  - legacy: the files in `.planning/specs/*.md` with a line `Epic: <id>` (`_EPIC_LINE`, `specs.py:38`) or `Workflow: <id>`;
  - SDD: `find_change(root, cfg, <id>)` (`specs.py:234`), then `change_file(change, "design")` (`specs.py:246`).
- `gin record plan-approved` (`_record_command`, `lifecycle_cli.py:265`) runs the check before the team pull request checks and before appending the event:
  - open questions: `{"status": "rejected", "message": "plan-approved refused: open technical questions\n<path>:<line>: TQ-<n>" ...}`, exit 1, nothing recorded;
  - several legacy spec files for one id: `status: error`, exit 2, naming the files;
  - no design doc found (no matching spec, no change folder, or no design file): no check, the gate records as today.
- The check reads the working tree. In team mode the lead pulls the merged plan pull request before recording, as today.
- No flag skips the check; the way out is a `Decision:` line.

## User Stories

### US-1: A BA discusses without technical questions
As a BA in team mode, I want discuss to ask me only business questions, so that I confirm a spec I can answer for and leave technical choices to the developers.

Acceptance criteria:
- With `team.enabled` and a runner whose roles are neither an area `lead` nor in an area's `roles`, discuss asks no question about architecture, components, storage, libraries, or error handling, and proposes no technical approach.
- A technical point found during discuss appears in the design doc as `- TQ-<n>: <question>` under `## Open Technical Questions`.
- `record requirement-confirmed` records a spec that still has open questions.
- A runner holding a technical role, a solo project, and a runner who is not a member get today's discuss.

### US-2: A technical member settles the open questions at plan
As a tech lead, I want plan to walk me through the open technical questions before it writes tracks, so that the design is decided by someone who can answer for it and is reviewed with the plan.

Acceptance criteria:
- When the design doc has open questions, plan asks about each one with two or three options and a recommendation before writing tracks.
- Each answer is written as `Decision: <text>` under its question, and the decisions appear in the plan's approach section.
- With the SDD layout, the empty `## Architecture`, `## Error Handling`, and `## Testing` sections of `03-design.md` are filled, and a section with text is left unchanged.
- In team mode, the plan pull request contains the plan and the design doc changes.

### US-3: The plan gate holds while a question is open
As a tech lead, I want `record plan-approved` to refuse while a technical question is open, so that no plan is approved on an undecided design.

Acceptance criteria:
- `gin record plan-approved` exits 1 with `status: rejected` and lists each open `TQ-<n>` with its path and line, and the gate stays unmet.
- Once every question has a non-empty `Decision:`, the same command records the gate.
- A workflow whose design doc cannot be found records the gate as today.
- `gin team whoami` and `gin state --format json` show `technical` for the current member.

## Errors and compatibility

- Solo projects, technical members, and workflows without `## Open Technical Questions` behave as today: the section is optional and no question means nothing to check.
- Existing specs and change folders need no migration.
- `project.team.me` gains one key; consumers that read it ignore unknown keys (gin-console does not read `project.team`).
- A malformed section fails `specs lint` with `path:line`; `record plan-approved` reports only open questions and leaves format errors to lint.
- Several legacy specs naming the same epic is a usage error (exit 2) instead of a guess.

## Testing

- `tests/workflow_core/` for `team.summary`: a role that is an area lead, a role listed in an area's `roles`, a business-only member, a member with both kinds of role, an area with no `roles`, and a non-member (`me: null`).
- Parser and lint: well-formed questions with and without decisions, an empty `Decision:`, a duplicate id, a stray line in the section, and questions inside a code fence; legacy `--spec` and SDD `--change`.
- Design doc lookup: legacy by `Epic:` and by `Workflow:`, SDD by change folder, not found, and two legacy specs for one id.
- `record plan-approved`: refused with open questions (exit 1, nothing appended), recorded once all are decided, recorded when no design doc is found, and the check runs before the team pull request check.
- `test_token_budget.py`: the discuss and plan chains stay within their budgets.
- Docs: `gin docs check` passes; `docs/guides/team.md`, `docs/roles.md`, `docs/concepts/lifecycle.md`, `docs/reference/cli.md`, and their `.vi.md` pairs describe the split.
