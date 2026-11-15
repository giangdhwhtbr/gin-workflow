---
name: team
description: Use in a lifecycle stage when `project.team.enabled` is true — member identity, PR-proven gates, track areas and owners, claims, Beads sync.
---

# Team Mode

Applies only when `gin state --format json` reports `project.team.enabled: true`. `project.team.me` is the member behind `git config user.email`; when it is null this clone cannot record gates or claim tracks: stop and point to `/gin:team-setup`. Commands are `gin team <command>`; exit 1 means findings or a rejection to report, exit 2 means an identity, usage, or host problem to fix first. In a workspace, follow [references/workspace.md](references/workspace.md) for branches, worktrees, ledgers, and closing the epic.

## Gates
- `record` and `unblock` take the actor from the git email; omit `--actor`.
- A gate with a policy in `team.approvals` (roles, `{all, any}`, `area_lead`, or `host`) is recorded with `--evidence <PR/MR URL>`; `record` checks that the PR is merged (open is fine for `ship`) and approved by a member holding a listed role, never by its author. Exit 1 lists missing approvals: report them; never switch evidence or waive a gate. `{all, any}` needs each `all` role.
- With `host`, ask no approver: `record` and `team check` check only that the PR merged in a known repository; the host's branch protection enforces approvals.
- `team check --gate <gate> <url>` re-verifies a teammate's gate without recording it.
- With Beads, `record` mirrors the proof into the epic bead; a teammate's `state --workflow-id <epic>` shows the gate. A `warning:` from `record` means the gate is recorded only locally: report it.

## discuss
When `team.approvals.requirement_confirmed` has a policy, spec review is `pr`: with `project.layout: sdd` follow the `pr` flow of the `sdd` skill; otherwise commit only the spec file on `spec/<topic>`, push, and open a PR after approval (stage-contract Approvals). Record `requirement-confirmed --evidence <pr-url>` once it is merged (`--spec <path>` if it changes several).

When `project.team.me.technical` is false, ask only business questions (purpose, users, rules, edge cases, validation, acceptance criteria, scope); propose no approach or technical design, and never ask the runner to choose or confirm a technical option. Write each technical point as `- TQ-<n>: <question>` under the design doc's `## Open Technical Questions` (the spec, or `03-design.md` with the SDD layout), not as an assumption; plan resolves them.

## plan
Each track's Metadata adds `Area: <area>` and `Owner: <member email>` (required unless `team.beads_sync` is set; reassigning a track means a new plan PR). A track's files stay inside its area; split a track that crosses areas. No file may be listed by two tracks. `team check-plan <plan>` must exit 0 before asking for approval. With a `plan_approved` policy, commit only the plan on `plan/<topic>`, push, and open a PR; after it merges, record `plan-approved --evidence <pr-url>` (`--plan <path>` if it changes several). The plan PR also carries the design doc's new `Decision:` lines and, with the SDD layout, the filled `03-design.md` sections.

## orchestrate
Track beads get `--labels track:<N>,area:<area>` and `--assignee <owner>` if the track has one.
- `team.beads_sync` set: the lead orchestrates once for everyone; run `team sync` before and after.
- Not set: each member creates beads only for the tracks they own, and a bead titled `external: <plan path>#<N>` for each dependency on another member's track, blocking the dependent bead.

## execute
- `team deps` first: it closes `external:` placeholders whose track PR has merged.
- Pick from `team ready`; claim with `team claim <bead>`; exit 1 means someone else holds an unexpired lease or you may not own its area, so pick another; `team ready` marks expired claims you may take over. Without `team.beads_sync` the claim is advisory.
- Out of quota or away: the assignee or area lead runs `team handoff <bead> <email>` (or `--release` to the pool) from the main checkout; the new owner runs `team takeover <bead>` in theirs. The plan's `Owner:` is not changed.
- In the track worktree, `team deps --bead <bead>` must exit 0 before implementation; exit 1 names the merge commit to fetch or rebase onto.
- Branch `feat/<topic>-t<N>` (`<topic>` the plan file name, `<N>` the track number). Commits follow `team.commit_convention`.
- The PR/MR uses the generated template; fill `Plan:` with the plan path and `Tracks:` with the track numbers; `team deps` on other machines reads them.
- With `team.beads_sync`, run `team sync` after closing a bead.

## review
The track owner never reviews; another member (or their agent) does, unless `project.review: self_check`. Without the ledger, push the track branch and open its PR (stage-contract Approvals) before requesting review; that member posts the verdict and findings as a review on the track's PR; the owner answers there (`review-response`) and closes the track after approval, naming the reviewer. With `project.review_ledger: true`, `init` and `start-review` take `--actor-id` from `team whoami`, so the ledger refuses the owner.

## ship
When `team.approvals.ship` has a policy: offer only the PR and keep options, push, open or reuse the PR, ask for approval of the latest commit (with roles, from that role), and before merging run `gin team check --gate ship <pr-url>` (a child PR: from its track worktree); stop if it reports reasons. After the merge, a standalone bead records `gin record shipped --workflow-id <bead> --evidence <pr-url>`; an epic with children ships by closing it as usual. A later push needs a new approval. Host settings: [references/hosts.md](references/hosts.md); when the check reports `approvals still syncing`, retry. Merge per host rules (CODEOWNERS, branch protection). With `team.beads_sync`, run `team sync` after closing the beads. A member's ship reports only their own tracks; the lead declares the feature complete when every track PR has merged.
