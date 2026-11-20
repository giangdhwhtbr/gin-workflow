# Team mode: the lead plans lanes, each member plans their own lane

Epic: gin-workflow-g9az
Kind: capability
Status: confirmed by the user on 2026-11-19.

## Goal and scope

In team mode the lead's `/plan` answers every open technical question and writes every track's steps, also for areas the lead does not own. Members do not own the implementation plan of the work they deliver.

Since `gin-workflow-ifbt` (shipped as `17743a82`) a member's tracks of a plan form a lane: one branch `feat/<topic>-<lane>`, one worktree, one pull request, with contracts between lanes fixed in the plan's `## Contracts`. This epic splits the plan in two levels on top of that:

- The lead's plan declares the lanes (owner, areas, repository, scope, acceptance criteria, the contracts each lane produces or consumes), fixes the contracts, and answers only the technical questions that concern more than one area. One plan pull request and one `plan_approved` gate, as today.
- A technical question that concerns one lane is marked with that lane and answered by the lane's owner.
- The member who claims a lane writes the lane plan: the lane's tracks and steps, in a file of its own, with no approval gate. The lead reads it in the lane's pull request.
- One epic and one spec stay. No child epics per area.

Success criteria:

- A lead can get `plan_approved` for a team plan that declares lanes and has no track, while questions marked for a lane are still open.
- A member can claim a declared lane, write and check its lane plan, create the lane's track beads and routes, and run the tracks, without the lead taking part before the lane's pull request.
- Plans and beads made before this change (plans without `## Lanes`) work unchanged.

Confirmed decisions (2026-11-19):

- A lane plan is a file of its own next to the lead's plan: `<lead plan stem>.lane-<lane>.md`.
- At orchestrate the lead creates one lane bead per lane that has no track in the lead's plan; the member claims it, writes the lane plan, and creates the lane's track beads and routes.
- A technical question for one lane is written `- TQ-<n> (lane <name>): <question>` in the spec. `plan-approved` ignores such a question while it is open; the lane plan answers it with a `Decision:` line in the spec, on the lane branch.
- The lead's plan may mix declared lanes with tracks written in full (with `Lane:`); a lane with tracks in the lead's plan is planned by the lead, as today.

Assumptions (defaults, not asked):

- The lane bead stands for planning the lane. It closes when the lane plan is committed and the lane's track beads exist, not when the tracks close. `implementation_complete` stays unmet until the tracks close.
- `gin goal` covers tracks, not lane beads.
- The `## Lanes` format and the lane plan procedure are described in `skills/team/references/lanes.md`, not in `skills/plan/plan-schema.md`: the plan stage has 64 characters of budget left.
- Lane plans use the existing track schema of `skills/plan/plan-schema.md`, with track numbers unique within the lane plan file.
- Out of scope: approval of a lane plan before the lane's pull request, gin-console views of lanes, changes outside team mode, and splitting one lane between two members.

Comments considered: 1, latest 2026-11-19T17:45:49Z

## Requirements

Paths are relative to `plugins/gin-workflow/src/` unless they start with `docs/` or `tests/`.

### R1. Lane declarations in the lead's plan

- A team plan may contain `## Lanes` before `## Tasks`, with one `### Lane <name>` per lane. Each declaration has `Owner: <member email>`, one or more `Area: <area>` lines, an optional `Repo: <path>`, `Scope:`, `Acceptance criteria:`, `Contracts:` (the `## Contracts` entries the lane produces or consumes), and an optional `Depends on lanes: <name>, ...`.
- A lane name follows the rule of `team.valid_lane`.
- `team` parses the declarations next to `plan_tracks`. A declared lane with no `### Track N` whose `Lane:` names it is planned by its owner (R5); a declared lane with such tracks is planned in the lead's plan.

### R2. Plan check with lanes

`gin team check-plan` on a plan with `## Lanes`:

- accepts a plan with no `### Track N` section;
- reports a lane without `Owner:`, a lane name `team.valid_lane` refuses, a lane declared twice, an owner who may not own one of the lane's areas, and a `Depends on lanes:` entry that names no declared lane;
- reports a track whose `Lane:` names no declared lane, and a track whose `Owner:` or `Repo:` differs from its lane's declaration;
- keeps every existing check of the tracks it has.

A plan without `## Lanes` is checked as today.

### R3. Technical questions marked for a lane

- `gin specs lint` and `specs.technical_questions` accept `- TQ-<n> (lane <name>): <question>`; the question keeps its id and records the lane.
- `gin record plan-approved` refuses an open question without a lane, as today, and does not refuse an open question marked with a lane that the plan declares. It refuses a question marked with a lane the plan does not declare.
- The plan stage of the lead does not answer questions marked with a lane.

### R4. Approval of the lead's plan

With the `area_lead` policy of `team.approvals.plan_approved`, the areas that need their lead's approval are those of the declared lanes and of the plan's tracks.

### R5. Lane beads

- The lead's orchestrate creates, for each declared lane with no track in the lead's plan, one bead under the epic: title `Lane <name>: <scope>`, labels `lane:<name>` and `area:<area>` per area, assignee the lane's owner, and a description with the line `Plan: <lead plan path>, Lane <name>` and the line `Lane: <name>`.
- Tracks written in the lead's plan get track beads as today.
- A lane bead closes when its lane plan is committed and the lane's track beads exist (R7).

### R6. Topic and lane of a lane plan

- A lane plan's path is the lead plan's path with `.md` replaced by `.lane-<lane>.md`.
- `team_pending.topic_of` drops the `.lane-<lane>` suffix, so a lane plan's tracks keep the branch `feat/<topic>-<lane>` and the worktree `.planning/worktrees/<epic>-<lane>`.
- The beads of a lane are the children of the epic with the same topic and lane, whichever plan file they name. `gin team claim` on a lane bead claims the lane bead and every open track of the lane, as R6 of `gin-workflow-ifbt` does for tracks.

### R7. Lane plan

The member who holds a lane bead runs `/plan` for the lane, in the lane's worktree:

- It writes the lane plan file (R6) with the existing track schema; every track has `Lane: <lane>`, `Owner:` the lane's owner, `Area:` one of the lane's areas, and the lane's `Repo:`.
- It answers each question marked `(lane <lane>)` with a `Decision:` line in the spec.
- `gin team check-plan <lane plan>` checks the lane plan against its lane's declaration in the lead's plan: every track in that lane, with its owner, an area of the lane, its repository, and files inside the track's area; it exits 0 before the commit.
- It commits the lane plan and the spec's decisions on the lane branch. No gate is recorded.

### R8. Lane orchestrate

The member then runs `/orchestrate` for the lane plan:

- It creates one track bead per track of the lane plan under the epic, with `Plan: <lane plan path>, Track <N>` and `Lane: <lane>`, and the dependencies between them.
- It resolves routes for these tracks only; `gin routes resolve` merges them into the workflow's assignment manifest.
- It closes the lane bead with a reason that names the lane plan path and the track beads.
- Run again after a failure, it skips the tracks whose bead (same `Plan:` path and track number) exists.

### R9. Dependencies on another lane

- For a lane with `Depends on lanes:`, the lead's orchestrate creates one bead `external: <lead plan path>#lane-<name>` per named lane, and the lane orchestrate makes each track of the dependent lane depend on it.
- `gin team deps` closes such a bead when the named lane has no open bead and every track of it is listed in the `Tracks:` line of a merged pull request whose `Plan:` names that track's plan file.
- `external: <plan path>#<N>` for one track works as today.

### R10. Ship and complete

- The lane's pull request carries `Plan: <lane plan path>` and `Tracks:` with track numbers of the lane plan. `gin team complete` and `gin team deps` accept a track when a merged pull request names its plan file and number, as today.
- Ship of a lane refuses while a question marked `(lane <lane>)` has no `Decision:`.

### R11. Goal

`gin goal` in team mode covers tracks only. When the member's only open beads in the epic are lane beads, it prints `No goal: lane <name> has no tracks yet; run /plan for it.` (one line per lane).

### R12. Documentation

`skills/team/references/lanes.md` describes `## Lanes`, questions marked for a lane, lane beads, the lane plan, and the lane orchestrate. `skills/team/SKILL.md`, `skills/plan/SKILL.md`, and `skills/orchestrate/SKILL.md` point to it within their character budgets. `docs/reference/cli.md` (`gin team check-plan`, `gin team claim`, `gin team deps`, `gin goal`, `gin specs lint`), `docs/guides/team.md` and `docs/guides/team.vi.md`, and `docs/changelog.md` describe the change.

## User Stories

### US-1: Approve a plan that declares lanes
As a tech lead, I want to approve a plan that declares lanes and their contracts without writing every track, so that I spend my review on the parts that cross areas.

Acceptance criteria:
- `gin team check-plan` exits 0 for a plan with `## Lanes`, `## Contracts`, and no track section.
- `gin record plan-approved` succeeds while the spec has an open `- TQ-4 (lane be):` question, and refuses while it has an open `- TQ-5:` question without a lane.
- Under the `area_lead` policy, the lead of each declared lane's area must approve the plan pull request.

### US-2: Plan my own lane
As a developer who owns a lane, I want to split my lane into tracks and answer my area's technical questions, so that I own how my part is built.

Acceptance criteria:
- After the lead's orchestrate, `gin team ready` lists my lane bead, and `gin team claim <lane bead>` gives the worktree `.planning/worktrees/<epic>-<lane>` on `feat/<topic>-<lane>`.
- `gin team check-plan <lane plan>` exits 1 when a track names another lane, another owner, or a file outside my areas, and 0 when it does not.
- After the lane orchestrate, the epic has one track bead per track of my lane plan with `Plan: <lane plan path>, Track <N>`, the routes of these tracks are in the assignment manifest, and the lane bead is closed.
- No gate is recorded and no other member is asked anything before my lane's pull request.

### US-3: Review the lane plan in the lane's pull request
As a tech lead, I want the lane plan and the answers to the lane's questions in the lane's pull request, so that I review the plan with the code it produced.

Acceptance criteria:
- The lane's pull request contains the lane plan file and the spec's `Decision:` lines for the lane's questions.
- Its body has `Plan: <lane plan path>` and `Tracks:` with the lane plan's track numbers, and `gin team complete <epic>` accepts the tracks once it has merged.
- Ship of the lane refuses while a question marked for the lane has no decision.

### US-4: Wait for another lane's merged code
As a QA engineer whose lane tests the joined behaviour, I want my lane's tracks to wait until the lanes they test have merged, so that I do not run tests against code that is not there.

Acceptance criteria:
- A lane with `Depends on lanes: be, fe` gets `external: <lead plan>#lane-be` and `#lane-fe` beads, and each of its tracks depends on both.
- `gin team deps` closes `#lane-be` only when lane `be` has no open bead and merged pull requests list every track of it.

### US-5: Keep plans made before this change
As a developer with an epic in flight, I want plans without `## Lanes` to keep working, so that the upgrade does not stop my work.

Acceptance criteria:
- `gin team check-plan` gives the same findings as before for a plan without `## Lanes`.
- Claim, ready, pending, deps, complete, and goal behave as before for beads whose plan has no lane plan.

## Errors and compatibility

- `check-plan` findings (R2, R7) exit 1 and name the lane or track; the lane orchestrate creates no bead while the lane plan check fails.
- A claim of a lane bead held by another member refuses with the existing `lane <name> is claimed by <email> until <expires_at> (<bead>)`.
- A lane orchestrate that fails part way leaves the lane bead open; running it again creates only the missing track beads (R8).
- A lane plan file whose lane has no declaration in the lead's plan is refused by `check-plan`.
- The spec changes on several lane branches; each lane edits the `Decision:` lines of its own questions, so the merges touch different lines.
- `gin team` JSON output gains fields only; no field is removed.
- Outside team mode nothing changes. A plan without `## Lanes` and beads orchestrated before this change behave as before.

## Testing

- `tests/workflow_core/`: parsing `## Lanes`; each `check-plan` finding of R2 and R7, and a mixed plan; `technical_questions` and `specs lint` with `(lane <name>)`; `plan-approved` with open questions with and without a lane, and with an undeclared lane; the `area_lead` areas of R4; `topic_of` with `.lane-<lane>`; claim of a lane bead with the lane's tracks; `lane_beads` across the lead plan and a lane plan; `team deps` closing `#lane-<name>`; `team complete` with a lane plan in `Plan:`; ship's refusal on an open lane question; `goal` with only lane beads.
- Skill and documentation invariants: the tests that read skill files and the character budgets pass; `gin docs check` prints `ok` on the changed pages.
- The full suite `python3 -m pytest -n auto` passes, also with `bd` off `PATH`.

## Open Technical Questions
