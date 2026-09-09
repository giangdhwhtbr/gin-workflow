---
name: bead-worker
description: Implement and validate one provider-backed durable work unit.
---

# Bead Worker Skill

Execute one assigned work unit inside its approved plan scope.

## Required inputs

- resolved `EffectiveConfig`
- `ArtifactRegistry`
- `ContextManifest(stage="execute")`
- native-harness `ApprovalDecision`

## Execution rules

1. Read task identity, status, dependencies, description, and acceptance criteria through `task.read` (or `bd show <id> --json`); claim or update it through `task.update` (or `bd update <id>`).
2. Resolve its file scope and validation intent from the approved plan in the artifact registry. For standalone or pre-existing work units executed without a separate plan file, derive file scope and validation intent directly from the task description and acceptance criteria.
3. Keep that work unit and scope required; discover related symbols, tests, and project knowledge on demand.
4. Implement only in-scope changes and run relevant local validation. Submit notable discoveries as knowledge proposals through the knowledge capability and record results through the evidence capability.
5. Route review findings through `receiving-code-review` and read terminal review state through the review capability.
6. Follow the canonical verification and handoff workflow. Write outcome notes and final state through task-tracking capabilities only after validation, review, repository status, follow-up capture, and handoff evidence are complete. Once technical acceptance criteria and code review pass, close the track bead in Beads to unlock downstream tracks; closing a track bead does not require commit/push or deliverable merge.
7. If commit/push authority has not been granted upon track completion, do NOT claim or report "waiting for PR merge" ("chờ PR merge") when no commit/push has occurred and no PR exists. Stop at handoff and present two explicit options to the user:
   - Option 1: Request authorization to commit & push worktree branch to create PR (`Xin lệnh commit & push nhánh worktree để tạo PR`).
   - Option 2: Keep code uncommitted in the worktree and proceed to the next track using the generated artifacts (`Giữ nguyên code uncommitted trong worktree và tiếp tục chuyển sang track tiếp theo sử dụng artifact vừa sinh`).

Scope or execution-strategy changes and production-impacting parallel work require native-harness approval plus a durable audit event. Notifications are optional and provider-backed.

Read [context and evidence policy](../../references/context-and-evidence-policy.md) for bounded worker context, fresh review context, result/event rules, knowledge proposals, evidence indexes, and secret references. It is the sole methodology-policy reference; this skill does not duplicate implementation, TDD, debugging, planning, or review methodology.
