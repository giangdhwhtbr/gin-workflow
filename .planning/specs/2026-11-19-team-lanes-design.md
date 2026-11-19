# Team mode: deliver a member's tracks as one lane, one branch, one pull request

Workflow: team-lanes
Kind: capability
Status: confirmed by the user on 2026-11-19.

## Goal and scope

In team mode a member who owns five to seven tracks of an epic runs them one at a time, opens one pull request per track, and waits for a person after each. The tech lead reviews five to seven small pull requests per member and is interrupted for each.

The cause is in the code, not in the team's habits:

- `gin team claim` gives each track its own worktree on `feat/<topic>-t<N>`, created from `origin/<default>` (`team_beads._track_place`, `team_beads.track_worktree`). A track that depends on the member's previous track does not contain its code until that track's pull request has merged.
- The `team` skill asks another member to review each track on the track's pull request, and `team.approvals.ship` asks the lead to approve the same pull request.
- `gin team complete` requires a merged pull request per track branch (`team_complete.py`), and `gin team pending` lists one branch per track (`team_pending.candidates`).
- `gin goal` exists, but it cannot run through an epic in team mode for the first reason above.

This epic replaces "one track, one branch, one pull request" with the lane: the tracks of one plan that one member does in one repository, delivered on one branch. A member claims a lane, runs every track of it unattended, and opens one pull request. Agents review each track; a person reviews the lane's pull request.

Success criteria:

- For an epic with N tracks in L lanes, the pull requests after the plan pull request number L, unless a member chooses to deliver a lane in parts.
- From `gin team claim` to the pushed lane branch, a member is asked nothing unless a track is blocked, needs a person, or fails review `project.max_cycles` times.
- An epic orchestrated before this change finishes on its `feat/<topic>-t<N>` branches with no migration step.

Confirmed decisions (2026-11-19):

- The lane replaces per-track delivery in team mode. There is no configuration key that selects one or the other.
- One epic, one spec, and one plan stay. No child epics per area.
- Each track is reviewed by the agent reviewer `gin reviewer` picks. The rule that another member reviews each track on its pull request is removed. A person reviews once, on the lane's pull request, under `team.approvals.ship`.
- Lanes do not wait for each other's code. The plan fixes each interface two lanes exchange, and each lane builds against it. The joined behaviour is checked by a QA track that runs after the lanes have merged.
- This epic keeps the plan as detailed as today. A second epic (plan in two levels: the lead plans contracts and lanes, each member plans their own lane with no approval gate) follows and builds on the lane.

Assumptions (defaults, not asked):

- The plan author names each lane; the area name is the usual choice (`be`, `fe`, `qa`).
- With `team.beads_sync` set and no `Owner:` on a lane's tracks, the first member to claim any track of the lane holds the whole lane.
- A member's tracks in one lane run one after another. Parallel work happens between lanes.
- Opening the lane's pull request still needs the member's confirmation (stage contract, Approvals).
- The acceptance-case check of the `qa-track` skill at ship is unchanged.
- gin-console reads `gin state` and `bd`, not `gin team` output, so the changed `gin team` JSON does not reach it.

Out of scope:

- The plan in two levels, technical questions scoped by area, and a member splitting their own lane into tracks (the follow-up epic).
- Parallel tracks inside one lane.
- Opening a pull request without the member's confirmation.
- The spec and plan gates and their approval policies.
- Showing lanes in gin-console.

## Requirements

Paths are relative to `plugins/gin-workflow/src/` unless they start with `docs/` or `tests/`.

### R1. Lane in the plan

- A track's Metadata may carry `Lane: <name>`. A lane name matches `^[a-z0-9][a-z0-9-]*$` and is not of the form `t<digits>`, which is reserved (R3).
- `team.plan_tracks` reads the line into the track's `lane` field. The `team` skill names it next to `Area:` and `Owner:`, and `skills/team/references/lanes.md` holds the rules.
- With `project.team.enabled`, the `plan` skill writes `Lane:` on every track.

### R2. Plan check

`gin team check-plan` adds these findings to the existing ones:

- `Track <N>: missing Lane:` when a track has no `Lane:` line.
- `Track <N>: invalid lane <name>` when the name breaks R1.
- `lane <name>: tracks <a> and <b> have different owners` when two tracks of a lane name different `Owner:` values, or one names an owner and the other none.
- `lane <name>: tracks <a> and <b> are in different repositories` when two tracks of a lane name different `Repo:` values (a track without `Repo:` is in the parent).

A lane may span areas when its owner is eligible for each; the existing area and owner rules apply per track.

### R3. Lane of a track bead

- `orchestrate` puts `Lane: <name>` in the description of each track bead whose plan track has one, and the label `lane:<name>`.
- The lane of a bead is the `Lane:` line of its description. A track bead without the line is in the implicit lane `t<N>`, a lane of that one track. Its branch is therefore `feat/<topic>-t<N>` and its worktree `.planning/worktrees/<bead>`, as before this change.
- The tracks of a lane are the track beads of one epic with the same plan path and the same lane.

### R4. Contracts in the plan

- `skills/team/references/lanes.md` defines a `## Contracts` plan section, placed before `## Tasks`. The plan stage's character budget leaves no room for it in `skills/plan/plan-schema.md`. In team mode, the plan has one entry there for each interface a track of one lane produces and a track of another lane consumes: for an HTTP endpoint the method, path, request, response, and error codes; otherwise the exact names and types.
- A consuming track names the contract entry in its Interfaces and does not list the producing track as a dependency.
- A change to a contract entry after plan approval goes through a new plan pull request, like any other plan change in team mode.
- The plan may still declare a dependency between tracks of two lanes when a track needs the other lane's merged code (for example an end-to-end QA track); R5 applies to it.

### R5. Dependencies between lanes

- A dependency between two tracks of the same lane is a direct Beads dependency, as today.
- For a dependency on a track of another lane, `orchestrate` creates the bead `external: <plan path>#<N>` and makes it block the dependent track. This applies with and without `team.beads_sync`. Before this change, a shared database used a direct dependency, so the dependent track became ready when the other track closed, before its code had merged.
- `gin team deps` and `gin team deps --bead` are unchanged: a placeholder closes when a merged pull request names the plan and the track number in `Tracks:`, and a track starts only when the merge commit is in its worktree.

### R6. Claim

`gin team claim <bead>` claims the lane of the bead:

- It writes the same lease (holder, `expires_at`) to every open track of the lane and assigns each to the member. Only the named bead becomes `in_progress`; the other tracks keep their status, so `gin team ready` still lists the next one.
- It refuses, changing nothing, when any open track of the lane is assigned to another member whose lease has not expired: `lane <name> is claimed by <email> until <expires_at> (<bead>)`. An expired lease on every such track is taken over, with the existing note.
- The eligibility check runs for the areas of every open track of the lane.
- Claiming a lane the member already holds renews the lease on every open track.
- The JSON result adds `lane` and `beads` (the ids claimed) and keeps `status`, `bead`, `assignee`, `expires_at`, `advisory`, `worktree`, `branch`, and `created`.

### R7. Branch and worktree

- A lane has one branch `feat/<topic>-<lane>` in the lane's repository and one worktree `.planning/worktrees/<epic>-<lane>` (R3 gives the implicit lane its earlier names). The existing rule for finding the branch stays: a local branch, else the branch on `origin`, else a new branch from `origin/<default>`.
- Every track of the lane commits on that branch, in dependency order.
- When a pull request of the lane's branch has merged and the branch holds no commit made after the merged head, the next claim of the lane starts the branch again from `origin/<default>` in the same worktree. When it holds such commits, claim keeps the branch and says so; the member merges `origin/<default>` into it.

### R8. Handoff and takeover

- `gin team handoff <bead> <email>` and `--release` push the lane's branch, record it on every open track of the lane, and reassign or release each of them. Closed tracks keep their assignee.
- `gin team takeover <bead>` checks the branch out at the lane's worktree path and claims the lane (R6).
- The review-ledger steps of both commands run for each open track of the lane.

### R9. Ready

`gin team ready` adds `lane` and `branch` to each row and, in text output, lists rows under their lane's branch with the lane's holder. An open track assigned to another member whose lease has expired is listed as an expired claim, as an in-progress one is today.

### R10. Goal

With `project.team.enabled`, `gin goal --workflow-id <id>`:

- covers only the open tracks assigned to the calling member; `--lane <name>` narrows it to one lane and also includes that lane's unassigned tracks;
- holds back a track that has an open `external:` dependency, and every track that depends on it, the way it holds back `human-gate` tracks, and names them: `Do not start <ids>: they wait for another lane to merge.`;
- adds to the condition that each covered lane's branch is pushed (`git status -sb` in its worktree shows nothing ahead of `origin`), and leaves out the `implementation_complete` clause, which other members' lanes would keep unmet;
- prints `No goal: <member> has no open track in epic <epic>.` when nothing is assigned to the member and `--lane` is not given.

Outside team mode the output is unchanged.

### R11. Execute in team mode

- `execute` claims the lane with `gin team claim` and works in the lane's worktree.
- After a track closes, it pushes the lane's branch and returns. It does not offer to create a pull request per track.
- Before each track, `gin team deps --bead <bead>` must exit 0, as today.
- `references/stage-contract.md` (Git) says that in team mode `execute` pushes the lane's branch.

### R12. Review in team mode

- A track is reviewed as outside team mode: the implementer's session requests the review, `gin reviewer` picks the reviewer, and independence follows `project.independence`. The reviewed diff runs from the lane branch's head when the track started to the track's last commit.
- The `team` skill no longer asks another member to review a track or to post the verdict on a track's pull request.
- With `project.review_ledger: true`, the reviewer's actor id is the one `gin reviewer` returns. The ledger still refuses the implementer's id as reviewer.
- A person reviews the lane's pull request (R13).

### R13. Ship in team mode

`ship` delivers a lane:

- It requires every track it delivers to be closed with its review approved or waived. The tracks it delivers are the closed tracks of the lane that no merged pull request lists yet.
- The pull request body, from `templates/team/pull_request_template.md`, carries `Plan:`, `Tracks:` with every delivered track number, `Beads:`, and one entry per delivered track: title, bead id, commit range, reviewer, review cycles, finding count, and the test commands run. The template gains that per-track block.
- Approval, `gin team check --gate ship`, and the merge follow the existing rules. A push after approval needs a new approval.
- A lane with open tracks left (a `human-gate` track, a track waiting for another lane) may be delivered in parts: each pull request lists only the tracks it delivers, and the rest continue per R7.
- After the merge, `ship` removes the lane's worktree when no track of the lane is open.

### R14. Pending

`gin team pending` lists one `feat/<topic>-<lane>` branch per lane with an open track, in place of one branch per open track.

### R15. Complete

`gin team complete <epic>` treats a track as delivered when a merged pull request names its plan and its number in `Tracks:` (the proof `gin team deps` uses). A track without one is reported as `<bead> (<plan>#<N>): no merged pull request lists it`. The check no longer looks up a pull request by track branch name.

### R16. Documentation

`skills/team/SKILL.md`, `skills/team/references/lanes.md` (new), `skills/team/references/workspace.md`, `skills/plan/SKILL.md`, `skills/orchestrate/SKILL.md`, `skills/execute/SKILL.md`, `skills/ship/SKILL.md`, and `references/stage-contract.md` describe the lane and no longer describe a pull request per track. So do `docs/concepts/lifecycle.md`, `docs/concepts/state-model.md`, `docs/reference/cli.md`, `docs/reference/skills.md`, `docs/roles.md`, `docs/starters/brownfield.md`, and the guides `git-flow.md`, `ai-strategy.md`, `team.md`, and `workspace.md`, each with its `.vi.md` translation where one exists. `docs/changelog.md` gains an entry.

## User Stories

### US-1: Run my lane unattended
As a developer, I want to claim all my tracks of an epic and let the agent implement them one after another, so that I am not stopped after every track.

Acceptance criteria:
- `gin team claim <bead>` on one of my tracks reports the lane, every open track of it as claimed, one worktree, and the branch `feat/<topic>-<lane>`.
- The second track of the lane starts in the same worktree and sees the first track's commits without any pull request having merged.
- `gin goal --workflow-id <id>` prints a goal that names only my open tracks and requires the lane's branch to be pushed.
- After each track closes, the lane's branch is on `origin` and no pull request has been opened.
- A track with `human-gate`, or with an open `external:` dependency, is named in `Do not start ...` and is not part of the goal.

### US-2: Review one pull request per member
As a tech lead, I want one pull request for all of a member's tracks, so that I review the change as a whole and am interrupted once.

Acceptance criteria:
- The lane's pull request lists every delivered track number in `Tracks:` and has one entry per track with its commit range, reviewer, review cycles, and finding count.
- `gin team check --gate ship <pr-url>` passes only when a member with a `team.approvals.ship` role, other than the author, approved the latest commit.
- `gin team pending` shows one branch for the lane, not one per track.
- `gin team complete <epic>` reports the epic complete when every track is listed in the `Tracks:` of a merged pull request.

### US-3: Build against the contract, join at QA
As a frontend developer, I want to build against the API contract in the approved plan, so that my lane does not wait for the backend lane to merge.

Acceptance criteria:
- A plan with two lanes that exchange an interface has a `## Contracts` entry for it, and the consuming track lists no dependency on the producing track.
- Both lanes can be claimed and run at the same time by two members.
- A QA track that depends on tracks of both lanes is blocked by `external:` beads, with or without `team.beads_sync`, and becomes ready only after `gin team deps` has closed them.

### US-4: Finish an epic started before this change
As a developer, I want my in-flight tracks to keep their branches, so that the upgrade does not break work in progress.

Acceptance criteria:
- `gin team claim` on a track bead without a `Lane:` line uses the branch `feat/<topic>-t<N>` and the worktree `.planning/worktrees/<bead>`, and claims only that bead.
- `gin team complete` accepts those tracks when their merged pull requests list them in `Tracks:`.

### US-5: Hand a lane to a colleague
As a developer who is away or out of quota, I want to hand my lane over, so that a colleague continues on the same branch.

Acceptance criteria:
- `gin team handoff <bead> <email>` reassigns every open track of the lane and records the lane's branch on each; closed tracks keep their assignee.
- `gin team takeover <bead>` in the colleague's checkout creates the lane's worktree on that branch and claims every open track of the lane.

## Errors and compatibility

- A second member claiming a track of a held lane gets exit 1 with the holder, the expiry, and the bead that holds the lease; no bead is changed.
- A git failure while creating the lane's worktree keeps the leases; running the claim again finishes it (the existing behaviour, now for the lane).
- A track that is blocked, or whose review is not approved after `project.max_cycles` cycles, stays `in_progress` with a note and stops the run. The closed tracks before it can be delivered in a pull request of their own (R13).
- A lane branch behind the default branch is brought up to date by merging `origin/<default>` into it; nothing force-pushes.
- With `project.review_ledger: true`, a change made on the lane's branch after the newest approved commit needs the last approved track reopened and reviewed again, as `ship` requires today. Without the ledger, the fix is pushed and the lead approves the new commit.
- A squash merge does not affect `gin team deps` or `gin team complete`: both read the pull request body, not branch history.
- A plan approved before this change has no `Lane:` lines. Its beads fall under R3's implicit lane; `gin team check-plan` reports `missing Lane:` only when that plan is checked again.
- A pull request of an earlier epic that lists one track in `Tracks:` satisfies R15 as it is.
- `gin team` JSON output gains fields (`lane`, `beads`) and `pending` rows change from track branches to lane branches. No field is removed from `claim` or `ready`.

## Testing

- `tests/workflow_core/`: `plan_tracks` reads `Lane:`; each `check-plan` finding of R2; the lane of a bead with and without a `Lane:` line; claim writes one lease to every open track of the lane, refuses on a foreign unexpired lease, and takes over expired ones; one worktree and one branch per lane, and the implicit lane keeps its earlier names; the branch restart of R7 and its refusal case; handoff and takeover over a lane; `ready` rows carry `lane`; `goal` in team mode covers only the member's tracks, honours `--lane`, holds back tracks behind an open `external:` bead, and adds the pushed-branch clause; `pending` lists lane branches; `complete` accepts a track listed in a merged pull request and names one that is not.
- Skill and documentation invariants: the tests that read the skill files pass with the changed `team`, `plan`, `orchestrate`, `execute`, `review`, and `ship` text, and `gin docs check` prints `ok`.
- The full suite `python3 -m pytest -n auto` passes, also with `bd` off `PATH`.

## Open Technical Questions
