---
name: gin-team
description: Use in a lifecycle stage when `project.team.enabled` is true — member identity, PR-proven gates, track areas and owners, claims, Beads sync.
---

# Team Mode

Applies only when `gin-workflow state --format json` reports `project.team.enabled: true`. `project.team.me` is the member behind `git config user.email`; when it is null this clone cannot record gates or claim tracks: stop and point to `/gin-workflow:team-setup`. Commands are `gin-workflow team <command>`; exit 1 means findings or a rejection to report, exit 2 means an identity, usage, or host problem to fix first.

## Gates
- `record` and `unblock` take the actor from the git email; omit `--actor`.
- A gate with roles in `team.approvals` is recorded with `--evidence <PR/MR URL>`; `record` checks that the PR is merged (open is fine for `verification_passed`) and approved by a member holding a listed role, never by its author. Exit 1 lists the missing approvals: report them to the user. Never switch evidence or waive a gate to get past a rejection.
- `team check --gate <gate> <url>` re-verifies a teammate's gate without recording it.

## discuss
When `team.approvals.requirement_confirmed` lists roles, spec review is `pr`: with `project.layout: sdd` follow the `pr` flow of the `gin-sdd` skill; otherwise commit only the spec file on `spec/<topic>`, push, and open a PR after approval. Record `requirement-confirmed --evidence <pr-url>` once it is merged (`--spec <path>` when the PR changes several spec files).

## plan
Each track's Metadata adds `Area: <area>` and `Owner: <member email>` (required unless `team.beads_sync` is set; reassigning a track means a new plan PR). A track's files stay inside its area; split a track that crosses areas. `team check-plan <plan>` must exit 0 before asking for approval. With `plan_approved: area_lead` (or roles), commit only the plan on `plan/<topic>`, push, and open a PR; after it merges, record `plan-approved --evidence <pr-url>` (`--plan <path>` when the PR changes several plan files).

## orchestrate
Track beads get `--labels track:<N>,area:<area>` and `--assignee <owner>` when the track has one.
- `team.beads_sync` set: the lead orchestrates once for everyone; run `team sync` before and after.
- Not set: each member creates beads only for the tracks they own, and a bead titled `external: <plan path>#<N>` for each dependency on another member's track, blocking the dependent bead.

## execute
- `team deps` first: it closes `external:` placeholders whose track PR has merged.
- Pick from `team ready` and claim with `team claim <bead>` instead of `bd update --status in_progress`; exit 1 means someone else holds it, so pick another.
- Out of quota or unavailable: push the branch, then the assignee (or the area lead) runs `team reassign <bead> <email>`; the new owner claims nothing, checks out the pushed `feat/<topic>-t<N>` branch, and continues. The plan's `Owner:` is not changed.
- In the track worktree, `team deps --bead <bead>` must exit 0 before implementation; exit 1 names the merge commit to fetch or rebase onto.
- Branch `feat/<topic>-t<N>` (`<topic>` from the plan file name, `<N>` the track number); existing branches keep their names. Commits follow `team.commit_convention`.
- The PR/MR uses the generated template; fill `Plan:` with the plan path and `Tracks:` with the track numbers exactly, because `team deps` on other machines reads them.
- With `team.beads_sync`, run `team sync` after closing a bead.

## verify
When `team.approvals.verification_passed` lists roles: push the feature branch, open the PR, ask that role to approve the latest commit, then record `verification-passed --evidence <pr-url>`. A commit pushed after the approval needs a new approval. On GitLab the project must enable 'Reset approvals on push'; when the gate reports `approvals still syncing`, retry.

## ship
Merging follows the host rules (CODEOWNERS, branch protection). With `team.beads_sync`, run `team sync` after closing the beads. A member's ship reports only their own tracks; the lead declares the feature complete once every track PR has merged.
