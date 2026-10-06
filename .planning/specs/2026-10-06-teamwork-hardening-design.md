# Teamwork Hardening — Design

Date: 2026-10-06
Status: draft, awaiting user review of this written spec
Workflow ID: `teamwork-hardening`
Extends: [Team Mode](2026-10-03-team-mode-design.md)
Supersedes: the earlier draft of this file (commits `e8e6862`, `df39ba2`)

## Goal and scope

Close the gaps where gates currently pass on the wrong evidence, with the smallest code change that does it. No team uses team mode yet, so this change hardens the gates and documents the team process; it does not build distributed-coordination features ahead of demand.

Team members are trusted. Gates guard against mistakes (wrong URL, stale approval, missing code), not against deliberate circumvention. The Git host's branch protection and CODEOWNERS remain the enforcement layer for merges.

## Confirmed defects (at `master` `b152a0d`)

| # | Defect | Location |
|---|---|---|
| 1 | `requirement_confirmed` / `plan_approved` accept any merged PR with an eligible approver; the PR need not change the spec/plan nor belong to this repository | `team.py` `check_approval`, `team_host.py` `fetch_pr` |
| 2 | `area_lead` passes on an empty plan; `check_plan` does not run inside the gate; `_plan_in` takes the first matching file | `team.py` `check_approval`, `_plan_in` |
| 3 | An approval with unknown commit (`""`) counts as approval of the current head; the GitLab adapter always supplies `""` | `team.py` `_approver_roles`, `team_host.py` GitLab fetch |
| 4 | `verification_passed` is satisfied by any historical `verification.passed` event, even after new commits (solo and team) | `lifecycle_cli.py` `_delivery_gate_state` |
| 5 | `team deps` closes an `external:` placeholder when the PR merged, without checking the merged code is in the workspace | `team_beads.py` `deps` |
| 6 | In local mode two members can both take the same unowned track in their area | `skills/gin-team/SKILL.md` orchestrate |
| 7 | Branch `feat/<epic>-<area>` collides for two tracks in one area and differs across machines (local epic ID) | `skills/gin-team/SKILL.md` execute |

## Requirements

### 1. Approval gates bind to the intended work (defects 1–3; team mode only)

- **Repository.** Parse host and project path from the PR/MR URL and compare with `git remote get-url origin`; SSH and HTTPS forms of the same host/project compare equal. A mismatch rejects the gate.
- **Artifact.** Add `--spec <path>` next to the existing `--plan <path>` on `record` and `team check`. Without a selector the PR must change exactly one candidate artifact for the gate (legacy: `.planning/specs/*.md` / `.planning/plans/*.md`; SDD: files under the configured `artifacts.changes` folder — `spec-delta.md` for the spec gate, `plan.md` for the plan gate). Zero or several candidates report that a selector is needed. With a selector, the path must be in `pr.files`. `_plan_in` no longer picks the first match.
- **Plan validity.** The `plan_approved` gate runs `check_plan` on the selected plan (read from the local checkout, which must contain the merged plan); every error, including an empty plan, is a rejection reason.
- **Approval freshness.** When the gate requires a specific commit (`verification_passed`), an approval with an empty commit is not counted.
- **GitLab.** The adapter reads the project's `reset_approvals_on_push` (`/projects/:id/approvals`). When false, the commit stays `""` and the rejection reason names the setting to enable. When true, approval resets are asynchronous, so the adapter binds `approved_by` entries to `head_sha` only if (a) the MR `head_sha` read before and after the approvals request is identical and (b) `detailed_merge_status` is neither `checking` nor `approvals_syncing`. Otherwise the gate rejects with "approvals still syncing; retry" (exit 1).
- **Event payload.** Team gate events additionally record the repository and the artifact path.

### 2. Verification binds to a commit (defect 4; solo and team)

- `record verification-passed` stores `branch` (current branch) and `head` (`git rev-parse HEAD`) in the event payload. Detached HEAD refuses to record (exit 2).
- `verification_passed` is derived from the latest `verification.passed` event of the workflow: satisfied when `git rev-parse refs/heads/<branch>` equals the recorded `head`, or when the recorded `head` is an ancestor of the branch tip and every commit after it changes only spec artifacts (legacy `.planning/specs/`, `.planning/plans/`; SDD `artifacts.specs` and `artifacts.changes`). This keeps the SDD ship step (`specs archive` then commit on the feature branch, after verification) from invalidating the gate. Ship still re-runs the test command before integration.
- The event store already lives in the main checkout (`main_checkout()` in `_get_event_store`) and refs come from the shared git dir, so the main checkout and linked worktrees agree.
- Any other new commit on the branch returns the gate to unmet; `workflow` routes back to verify.
- Events without `head` (recorded before this change) count as unmet; in-flight workflows verify once more.
- A deleted branch reads as unmet; `shipped` is derived from the closed epic and is unaffected. `state` output must not present this as a regression after ship.
- Uncommitted worktree changes are out of scope here; the `verify` skill already requires fresh command output.

### 3. Dependencies, ownership, branches (defects 5–7)

- **`team deps` ancestry.** After finding a merged PR for a placeholder, run `git merge-base --is-ancestor <merge_commit> HEAD`. Success closes the placeholder and stores the merge commit in the bead's metadata. Failure (missing object or not an ancestor) leaves it in `waiting` with the reason `fetch/rebase onto <target> to include <merge_commit>`. Never merge or cherry-pick automatically.
- **`team deps` rechecks resolved placeholders.** Closed `external:` placeholders that still block an open bead are re-checked against the current workspace `HEAD` using their stored merge commit; a missing commit is reported as `missing` and `team deps` exits 1. The placeholder is not reopened.
- **Run in the execution workspace (skill).** The `gin-team` execute section runs `team deps` inside the selected track worktree, after workspace selection and before implementation, and requires exit 0. A placeholder closed from another checkout therefore cannot stand in for code absent from the track worktree.
- **Owners required in local mode.** Without `team.beads_sync`, `check_plan` reports every track lacking `Owner:`. Because the gate runs `check_plan` (Requirement 1), such a plan cannot pass `plan_approved`.
- **Orchestrate (skill).** In local mode each member creates beads only for tracks they own, plus the `external:` placeholders those tracks need. The "unowned tracks in my areas" rule is removed.
- **Branch name (skill).** `feat/<topic>-t<N>`, where `<topic>` is the plan's topic slug and `<N>` the track number. Every machine derives the same name; same-area tracks no longer collide. Existing branches are not renamed.

### 4. Team process (documentation only)

Document in the team guide and `gin-team` skill:

- The lead assigns `Owner:` in the plan PR; reassignment goes through a new plan PR.
- Host configuration: GitHub — branch protection, "dismiss stale pull request approvals when new commits are pushed", CODEOWNERS per area. GitLab — "reset approvals on push" (required for the verification gate, Requirement 1).
- A member's ship reports their own tracks only. The lead declares the whole feature complete once every track PR has merged.

## Errors and compatibility

- Exit 0: check passed. Exit 1: evidence rejected, plan invalid, dependency not integrated. Exit 2: missing selector/tool/config, detached HEAD, host unavailable.
- A rejected gate writes no event. A failed host query never closes a placeholder.
- Solo behavior changes only in Requirement 2. Team behavior without configured approvals is unchanged.
- Existing shared-Beads (`team.beads_sync`) installations keep their current orchestration and sync behavior, except the gate checks above.

## Testing

Extend the existing team and lifecycle tests:

- Gate: PR without the artifact; PR from another repository (SSH vs HTTPS equality); zero/several candidates without selector; empty plan; plan errors via gate when `check-plan` was skipped; approval with empty commit; GitLab with `reset_approvals_on_push` true/false, head changed between reads, and `approvals_syncing` (fixtures).
- Verification: temporary git repo — verify → met; new commit → unmet; spec-artifact-only commit after verify (SDD archive) → still met; re-verify → met; legacy event without `head` → unmet; record in a worktree, read from the main checkout → same result; detached HEAD → exit 2.
- Deps: temporary git repo with a stubbed host — merge commit is/is not an ancestor of HEAD; placeholder closed in one worktree, re-checked from another worktree lacking the commit → `missing`, exit 1.
- `check-plan`: missing owner in local mode is an error; with `beads_sync` it is not.

Host interactions are fixtures, not live provider validation. Keep skill instruction budgets and documentation checks passing.

## Out of scope

Approval revocation rechecks, plan-revision diffing, ownership-change handoff holds, whole-feature integration reporting, PR search pagination/ambiguity handling, idempotent re-orchestration via shared track identity, verifying artifact content at the reviewed host revision, automatic host configuration, and changes to `team.beads_sync`. Revisit when a real team reports the need.
