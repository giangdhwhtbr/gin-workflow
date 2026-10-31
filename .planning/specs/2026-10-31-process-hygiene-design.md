# Process hygiene: consistent skills, rules that bind where it matters

Epic: gin-workflow-rm-process-hygiene
Status: draft for user review.

## Goal and scope

Stage skills agree with each other and with the CLI, carry no hard-coded locale, and the safety rules block what they claim to block.

In scope:
- English handoff options in `execute`.
- One commit/push rule, owned by `stage-contract.md`, that `execute` and `quick` both follow.
- Named runner of `review-ledger.py checkpoint` and `transition-requested`.
- Named branch for spec and plan commits before a worktree exists.
- `safety-check.sh` blocks `git commit -n` and `core.hooksPath` overrides.
- `post-edit.sh` removed.
- Orchestrator dispatch sets `WORKTREE_PATH` for workers.
- Legacy-layout spec lint, enforced by `record requirement-confirmed`.
- ADR template referenced for legacy knowledge records; `state` warns at ship time when `.planning/knowledge` did not change since orchestration.
- `setup doctor` compares the installed snapshot with `src`.
- One approvals table in `stage-contract.md`, referenced by the skills.
- One doc line naming the writer of `.beads.gate.lock`.

Out of scope: changing the default layout to `sdd`; shrinking skill size; the roadmap skill's tech-doc rule; `WORKTREE_PATH` for Claude Code native subagents (the Agent tool cannot set a child environment; the variable reaches only gin-orchestrator workers).

Current behavior this changes (`S` = `plugins/gin-workflow/src`):
- `S/skills/execute/SKILL.md:46-47` lists the two handoff options in Vietnamese.
- `S/skills/quick/SKILL.md:28` says "Never commit or push; the user commits", against the Git section of `S/references/stage-contract.md` and `execute/SKILL.md:45`, which commit and push the feature branch.
- `S/skills/review/SKILL.md:15` runs `checkpoint` and `transition-requested` as `--actor-role worker`; `execute/SKILL.md:43` only says "request review through the `review` skill"; `docs/concepts/architecture.md:97` draws the orchestrator as the caller.
- `S/skills/discuss/SKILL.md:25` says "commit it on a feature branch" without naming it; `plan` and `orchestrate` say nothing about the branch. `workflow_core/worktrees.py:39` forks a new worktree from the current branch when no base is given.
- `S/scripts/safety-check.sh:80-81` blocks only `--no-verify` on `commit`, `push`, `merge`.
- `S/scripts/post-edit.sh` only echoes the edited path (line 20); `S/hooks/hooks.json` wires it as a PostToolUse hook; nothing reads its output. `.planning/roadmap.md:58` plans to port it to Python.
- `safety-check.sh:88` reads `WORKTREE_PATH`, but nothing sets it; `gin_orchestrator/native_cli.py:85` `sanitized_environment` is an allowlist that drops it.
- `workflow_core/lifecycle_cli.py:147` records `requirement-confirmed` without reading the evidence; `workflow_core/specs.py` lints only SDD `### REQ-` blocks.
- `S/templates/adr.md` exists and `gin-workflow specs template adr.md` works in the legacy layout, but `S/skills/gin-knowledge/SKILL.md` does not use it; `S/skills/ship/SKILL.md:36` reconciles knowledge with no check.
- `workflow_core/setup_service.py:405` `doctor()` never compares installed files with `src`; `install.sh:132` `generate_manifest` writes only name and version.
- Approval rules are restated in `plan`, `orchestrate`, `execute`, `gin-worktrees`, `gin-parallel-agents`, `ship`, `gin-sdd`, `gin-team`, `migrate-specs`, and `AGENTS.md`.
- `.beads.gate.lock` appears only in `.gitignore:31` (commit `87f83fc`, "ignore bd's .beads.gate.lock").

## Requirements

### Skill and doc text
- `execute/SKILL.md` handoff options are in English with the same meaning: (1) ask for the command to create a PR from the pushed feature branch; (2) keep the pushed branch and continue with the next track using the produced artifact.
- `stage-contract.md` Git section holds the only commit/push rule: commit on a feature or worktree branch, never on `main`/`master`; `execute` pushes its track branch, `quick` does not push. `quick` creates `quick/<slug>` when started on `main`/`master` and commits there. `execute`, `quick`, and `AGENTS.md` reference the rule instead of restating it.
- `execute/SKILL.md` names the session running `execute` as the runner of `init`, `checkpoint`, and `transition-requested --to review-requested` (through the `review` skill, `--actor-role worker`). `architecture.md:97` shows the same actor.
- `discuss` commits the spec on `feat/<topic>` (`<topic>` is the spec's topic slug, as in `.planning/specs/<date>-<topic>-design.md`), creating it from the base branch if needed; `plan` commits the plan on the same branch; `orchestrate` runs `worktree create` from that branch so the worktree contains both. SDD and team modes keep their own `spec/...` branch names.
- `stage-contract.md` has one approvals table (action → when approval is needed → what is recorded) covering: `plan-approved`, production-impacting parallel work, disabling worktree isolation or working in place, execution-strategy or scope changes, PR creation, merge into the base branch, force-push, discard/cleanup. The skills listed above reference the table and keep only stage-specific detail.
- `docs/concepts/state-model.md` has one line naming `bd` as the writer of `.beads.gate.lock` (verified against bd 1.0.5 at execute time; if `bd` is not the writer, the line names the actual writer).
- `gin-knowledge` starts a decision record from `gin-workflow specs template adr.md` and stores it under `.planning/knowledge/` in the legacy layout.

### Safety hook
- `safety-check.sh` exits 2 for `git commit` with `-n` as a standalone short flag or inside a bundled short-flag group (`-an`, `-nm`), counting only text outside quotes.
- It exits 2 for `git -c core.hooksPath=<value>` with any subcommand.
- It exits 2 for `git config [scope flags] core.hooksPath <value>` and `git config --unset core.hooksPath`; a read (`git config core.hooksPath`, `git config --get core.hooksPath`) passes.
- Existing allows keep passing: `git commit -m 'fix -n flag'`, `git push -n`.
- `post-edit.sh`, its PostToolUse entry in `hooks.json`, and its test are removed; `install.sh`/`install.ps1` and the smoke tests no longer reference it. `.planning/roadmap.md:58` (windows-parity scope) ports only `safety-check.sh`.

### Dispatch
- When gin-orchestrator spawns a worker whose working directory is a worktree under `.planning/worktrees/`, the worker environment contains `WORKTREE_PATH=<that directory>`; otherwise the variable is absent. `sanitized_environment` stays an allowlist.

### Legacy spec lint
- `gin-workflow specs lint` in the legacy layout takes `--spec <path>` and reports, per spec: a `### US-<n>:` block with no `Acceptance criteria:` line or no `-` bullet under it; a spec with no `### US-` block; any `{{...}}`, `TBD`, or `TODO` left outside inline code and code fences (so a spec can name these tokens in backticks). Exit 1 with one line per error, else 0.
- `gin-workflow record requirement-confirmed` in the legacy layout, when `--evidence` is an existing `.md` file, runs the same lint and refuses (exit 1, errors on stderr, no event written) on any error. Other evidence forms are recorded as today.

### Knowledge warning
- `gin-workflow state --format json --workflow-id <id>` adds a warning to `warnings` when `orchestration.ready` is recorded for the workflow, `implementation_complete` is satisfied, and `git log --since=<orchestration.ready timestamp> -- <artifacts.knowledge>` is empty. The warning names the directory and the timestamp. `ship/SKILL.md` step 7 shows `state` warnings to the user before reconciling knowledge. The change to the JSON is additive.

### Installed snapshot check
- `install.sh` and `install.ps1` write `.gin-workflow-src.json` (`{"src": "<absolute src path>", "sha256": "<hash>"}`) into each installed plugin target. The hash covers the relative path and bytes of every file under the copied `src` directories, in sorted order.
- `setup doctor` reads that file for each installed target it knows; when `src` exists it recomputes the hash and warns "installed snapshot differs from src; run ./install.sh" on mismatch. A missing file or missing `src` skips the check without a warning or error.

## User Stories

### US-1: Skills give one answer per rule
As a workflow user, I want every stage skill to state commit, approval, and review-ledger rules the same way, so that the agent's behavior does not depend on which skill it read.

Acceptance criteria:
- `execute/SKILL.md` contains no Vietnamese text.
- `quick/SKILL.md` no longer says "Never commit or push"; it references the Git rule in `stage-contract.md`.
- `stage-contract.md` has one approvals table, and the listed skills reference it.
- `execute/SKILL.md` and `architecture.md` name the same runner for `checkpoint` and `transition-requested`.
- `discuss`, `plan`, and `orchestrate` name the same `feat/<topic>` branch.

### US-2: Safety hook blocks hook bypasses
As a maintainer, I want the safety hook to block every common way of skipping git hooks, so that quality checks cannot be skipped silently.

Acceptance criteria:
- `git commit -n -m x`, `git commit -anm x`, `git -c core.hooksPath=/dev/null commit -m x`, `git config core.hooksPath /tmp/h`, and `git config --unset core.hooksPath` exit 2.
- `git commit -m 'fix -n flag'`, `git push -n`, and `git config --get core.hooksPath` exit 0.

### US-3: No no-op hooks
As a maintainer, I want hooks that do nothing removed, so that every installed hook has a job and the Windows port carries no dead code.

Acceptance criteria:
- `post-edit.sh` and its `hooks.json` entry no longer exist in `src`.
- The unit tests and `install_smoke_test` pass after the removal.

### US-4: Workers know their worktree
As a maintainer, I want orchestrator workers to receive `WORKTREE_PATH`, so that the safety hook's worktree containment check runs for them.

Acceptance criteria:
- A unit test shows a worker spawned in `.planning/worktrees/<id>` gets `WORKTREE_PATH` set to that directory.
- A worker spawned elsewhere gets no `WORKTREE_PATH`.

### US-5: Confirmed specs have testable stories
As a reviewer, I want `requirement-confirmed` refused for a legacy spec without acceptance criteria, so that planning starts from testable stories.

Acceptance criteria:
- `record requirement-confirmed --evidence <spec>` exits 1 and writes no event when a story lacks acceptance criteria or a placeholder remains.
- The same command records the gate for a spec that passes `specs lint --spec`.
- Evidence that is not a `.md` file is recorded as before.

### US-6: Ship reminds about knowledge
As a maintainer, I want a warning at ship time when no knowledge record changed since orchestration, so that decisions made during implementation are not lost.

Acceptance criteria:
- `state` shows the warning for a completed workflow with no commit under `.planning/knowledge` since `orchestration.ready`.
- `state` shows no such warning when such a commit exists, or before `implementation_complete`.
- `gin-knowledge/SKILL.md` references `specs template adr.md`.

### US-7: Doctor detects a stale install
As a maintainer of this repo, I want `setup doctor` to tell me when the installed plugin differs from `src`, so that I do not test old skills by accident.

Acceptance criteria:
- After `./install.sh`, `setup doctor` reports no snapshot warning.
- After editing a file under `src` without reinstalling, `setup doctor` reports the snapshot warning.
- With no `.gin-workflow-src.json`, `setup doctor` reports nothing about the snapshot.

## Errors and compatibility

- The `requirement-confirmed` lint is new enforcement: a legacy spec with no `### US-` block now fails. Specs already recorded are unaffected, since the gate is not re-checked.
- The state warning is additive; gin-console ignores unknown warnings.
- `.gin-workflow-src.json` appears only after the next install; until then doctor skips the check.
- Removing `post-edit.sh` changes `hooks.json`; installed snapshots keep the old entry until reinstall, and the old script still exists there, so nothing breaks in between.
- The `safety-check.sh` rules use the existing quote-aware segment split; a false block is reported with the matched rule so the user can rephrase.

## Testing

- `tests/test_safety_check.py`: cases from US-2; remove the post-edit test.
- `tests/gin_orchestrator/`: worker environment with and without a worktree cwd.
- Specs lint unit tests for the legacy checks; a `lifecycle_cli` test for refusal and success of `record requirement-confirmed`.
- `state` warning tests using a temporary git repo with and without a knowledge commit after the event timestamp.
- `setup doctor` tests: matching hash, mismatched hash, missing file.
- `tests/install_smoke_test.sh` passes; `install_smoke_test.ps1` is updated for the removed script.
- Full suite: `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py`.
