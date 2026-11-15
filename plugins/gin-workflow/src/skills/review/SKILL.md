---
name: review
description: Request or perform a bead review (independent or self check) with bounded cycles and an optional review ledger.
---

## Before you start
1. If `.agent-workflow/generated/effective-config.yaml` does not exist in the main checkout (the parent of `git rev-parse --path-format=absolute --git-common-dir`; linked worktrees have none), stop: tell the user to run `/setup` once and do nothing else. (`capabilities: {}` is a valid config.)
2. Read [references/stage-contract.md](../../references/stage-contract.md) now: it defines the gate CLI, valid evidence, approval, and git rules this stage relies on.

# Review

Review after every track, after a major feature, and before merge; never skip because "it's simple". A completed implementation starts review; it is not evidence that the task may close. Read `project.review`, `project.review_ledger`, `project.run_at`, and `project.max_cycles` from `gin state --format json`.
- `project.review: self_check`: no reviewer. After Requesting step 1, the implementer re-reads the diff for debug leftovers, secrets, and test coverage and fixes what it finds; nothing else here applies.
- `project.review_ledger: true`: read `ledger.md` in this skill's folder; its sections say where their commands go.
- `project.review_ledger: false`: run no `review-ledger.py` command and write nothing under `.planning/reviews/`.

## Requesting (implementer)
1. Commit the track's changes (with the ledger, `checkpoint` in `ledger.md` commits them). With `project.run_at: track`, run `gin evidence run` and fix any failure first. With `push` or `host`, run the tests of the changed code only.
2. Pick the reviewer with `gin reviewer --base <the track's base commit> --implementer <provider> --model <model> [--effort <effort>] --json`. Spawn `gin:code-reviewer` with its `actor_id` (the reviewer uses the implementer's final model and effort, which includes any escalation, and never a lower one): always natively when `route.provider == main_harness` is `claude` (`Agent`) or `antigravity` (`invoke_subagent`, `Model="inherit"`), else via `gin-orchestrator dispatch --workflow-id <id> --task-id <id> --role review --provider <provider> --model <model> [--effort <effort>] --stage review --agent code-reviewer --workspace <worktree> --objective "<review brief>" --json` (fallback: native subagent), trying the next on quota, rate-limit, or timeout failure (exit 2 means `human_decision_required`). Without a native subagent or `gin-orchestrator`, stop for the user; no self-review unless `allow_self_review_fallback`. Give fresh context: reviewed diff, requirement, criteria, test evidence, rules checklist (`gin rules --files <reviewed files>`), and, with the ledger, the absolute path of this skill's `ledger.md`. Exclude private reasoning, self-assessment, persuasive summaries, unrelated history, secrets. Fixes after `changes requested` go to `gin:developer` at its current route.
3. Record the implementation's original provider/model route as runtime affinity only; never put concrete providers in the plan or Beads.
4. Handle findings with the `review-response` skill: fix Critical immediately and Important before proceeding, note Minor ones, and push back with evidence when the reviewer is wrong. Then ask the same reviewer again.

## Reviewing (reviewer)
1. Independence follows `project.independence`: `provider`: the reviewer provider must differ from the implementation provider; `session`: a fresh session/subagent of the same provider with a clean context and a different actor id (`reviewer:<provider>:session-<id>`), never the implementer's session. Self-review only under the explicit `allow_self_review_fallback` policy; otherwise route exhaustion needs a human decision. Provider independence needs gin-orchestrator; without it independence is `session`.
2. Inspect in-scope files for correctness, edge cases, error handling, security, performance, plan alignment. Never modify implementation files. Check rules checklist, `critical`/`high` first; cite `<pack>#<anchor>`, record `critical` as `IMPORTANT`+. Grade `lean` by impact: `high` bullet as `IMPORTANT`, others `MINOR`; name cuts and replacements (ignore `simplified:`). Check docs claims against the code and grade docs findings per [references/docs-style.md](../../references/docs-style.md). With `project.layout: sdd`, each REQ scenario needs a test (the `sdd` skill).
3. Tests: with `project.run_at: track`, cite `gin evidence check` in the worktree when it exits 0, else run the tests in isolation. With `push` or `host`, run the tests of the changed code only. Run tests in the foreground with a timeout, and never stop a process you did not start.
4. Check each spec/plan requirement this track delivers against the code, not only the diff. For a claimed fix, check the tree; never accept what you could not confirm.
5. Report a verdict, `approved` or `changes requested`, and each finding with an id, severity, file and line, and fix. Approve only when every finding is resolved.

## Cycles
Each unresolved revision is a new review cycle. After `project.max_cycles` cycles without approval, ask the user (with the ledger, `human_decision_required` per `ledger.md`) instead of retrying. Never loop unbounded. Never manufacture approval.
