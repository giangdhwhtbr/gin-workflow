# Plan: Move the Beads databases into gin-harness

Workflow: beads-harness-migration
Spec: .planning/specs/2026-10-21-beads-harness-migration-design.md

## Goal

Keep the Beads databases of every child project in `~/gin-harness/beads/<repo>/`
with a symlink at each repo root, add a `gin-harness` database for cross-project
epics, wire cross-repo dependencies, make gin-workflow's git hooks run, and turn
the `beads-migration` skill into the reusable procedure.

## Architecture

No product code changes. One plugin skill, one test, one config file, one
`.gitignore` line and one spec amendment change in gin-workflow (Track 1). The
rest is a one-time operation on live data outside the repo, done repo by repo
(Tracks 2–4) with a backup before each move and a count/context check after it.

## Tech Stack

`bd` 1.0.5 (embedded Dolt), git, POSIX shell, Python `unittest`.

## Global Constraints (from the spec)

- Each child database keeps its name, prefix, issue ids, project id and
  `sync.remote`.
- Never move a database in use; back up with `cp -a` first.
- Out of scope: one shared database, `scripts/sync.sh`, `versions.lock`, any
  gin-console code change, making ship run `bd ship`, `/setup` in the harness,
  a gin-orchestrator database.

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `implement`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for the live-data tracks (2–4).

## Requirement Analysis
- Problem statement: two repos keep separate Beads databases in their own trees;
  there is no home for cross-repo epics; gin-workflow's git hooks never run.
- Success criteria: US-1 to US-5 of the spec.
- Constraints: as above. A `.gitignore` entry `.beads/` (trailing slash) does
  not match a symlink, so both repos need a plain `.beads` entry.
- Non-goals: as in the spec's out-of-scope list.

## Approach Options
### Option 1: Move by hand once, then document
- Pros: fastest. Cons: the skill stays wrong; gin-orchestrator repeats the work blind.
### Option 2: Fix the skill first, then follow it for each repo
- Pros: the procedure is tested on two real repos before gin-orchestrator needs it.
- Cons: one extra track.

### Recommended Approach
- Selected option: Option 2.
- Reasoning: the spec requires the skill (US-3), and following it is the check that it works.

## Scope
- In scope: Tracks 1–4 below.
- Out of scope: the spec's out-of-scope list.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Four sequential tracks; Tracks 2-4 act on live databases outside the repo and must not run in parallel.
```

## Tasks

### Track 1: Skill, config and spec changes in gin-workflow
- **Dependencies**: none
- **Provider role**: `general`
- **Reasoning**: `medium`
- **Estimated complexity**: low
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/beads-migration/SKILL.md` (whole file)
  - Modify `tests/workflow_core/test_token_budget.py` (add one test after `test_ship_merge_never_rewrites_the_local_base`)
  - Modify `.agent-workflow/config.yaml` (add a top-level `verify` section)
  - Modify `.gitignore` (line 30, `.beads/` → `.beads`)
  - Modify `.planning/specs/2026-10-20-split-orchestrator-design.md` (US-4 and release step 3)
- **Interfaces**: produces the migration procedure used by Tracks 2–4, and
  `verify.checks.test` read by `gin-workflow hooks run pre-push`.
- **Steps**:
  1. Add the failing test:
     ```python
     def test_beads_migration_targets_the_harness(self):
         text = (SRC / "skills/beads-migration/SKILL.md").read_text(encoding="utf-8")
         self.assertNotIn("/home/coder/workspace/brain", text)
         for needle in ("~/gin-harness/beads/<repo>", "cp -a", "git rm -r --cached .beads",
                        "core.hooksPath", "bd count", "bd context", "external_projects"):
             self.assertIn(needle, text)
     ```
     Run `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_token_budget`: expect 1 failure.
  2. Rewrite the skill. Keep the frontmatter name, set the description to
     "Move a repository's .beads directory into ~/gin-harness/beads/<repo> and symlink it back."
     and keep "Load only when the user explicitly invokes it." Body, as numbered steps:
     inputs (`<repo>` root, target dir default `~/gin-harness/beads/<repo>`);
     record `bd count` and `bd context`; stop if `pgrep -af "bd |gin-workflow"` shows a process for the repo;
     `cp -a <repo>/.beads ~/gin-harness/backup/<repo>-$(date +%F)`;
     `mv` then `ln -s <target> <repo>/.beads`;
     if `git ls-files .beads` lists files: `git rm -r --cached .beads`, add a `.beads` line (no trailing slash) to `.gitignore`, commit on a feature branch;
     check `git config core.hooksPath` exists (`mkdir -p` it if it points into `.beads`), then `gin-workflow hooks install`;
     add `external_projects` entries for the other databases to the moved `config.yaml`;
     verify `bd count` and `bd context` match, and `gin-workflow task ready` runs;
     rollback: `rm <repo>/.beads && mv <target> <repo>/.beads`, or restore the backup.
  3. Run the same test command: expect OK. Run `python3 -m unittest tests.test_no_direct_bd`: expect OK (the skill is in `BEADS_ONLY`).
  4. Add to `.agent-workflow/config.yaml`:
     ```yaml
     verify:
       checks:
         test: PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all
     ```
     Run `gin-workflow setup refresh --non-interactive --approve`, then
     `grep -A3 'verify' .agent-workflow/generated/effective-config.yaml`: expect the test command.
  5. Change `.gitignore` line `.beads/` to `.beads`.
  6. In the split spec, replace US-4's story and criteria with: each repo's
     database kept under `~/gin-harness/beads/<repo>`, a `gin-harness` database
     for cross-project epics, cross-repo order through `external:` dependencies;
     narrow release step 3 to `scripts/sync.sh` and `versions.lock`.
  7. Run the full suite `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.test_all`: expect OK.
- **Acceptance criteria**: the new test and the full suite pass; the effective
  config has `verify.checks.test`; US-3 criteria hold.

### Track 2: Migrate gin-workflow and enable its hooks
- **Dependencies**: Track 1 (merged to master, so the symlink and `.gitignore` agree)
- **Provider role**: `general`
- **Reasoning**: `high`
- **Estimated complexity**: medium
- **Files**: `~/gin-workflow/.beads` (becomes a symlink), `~/gin-harness/beads/gin-workflow/`, `~/gin-harness/backup/gin-workflow-<date>/`
- **Interfaces**: produces `~/gin-harness/beads/gin-workflow` used by Track 4's `external_projects`.
- **Steps**: follow the reworked skill for `<repo>` = `~/gin-workflow`. Before
  the move, remove every worktree under `.planning/worktrees/` that is not
  needed. After the move: `mkdir -p "$(git config core.hooksPath)"`,
  `gin-workflow hooks install` (expect `pre-commit: installed`, `pre-push: installed`).
  Create a fresh worktree with `worktree-create.sh probe-beads probe/beads master`,
  run `gin-workflow task ready` inside it, then remove it with `worktree-cleanup.sh probe-beads`.
- **Acceptance criteria**: US-1 criteria for gin-workflow (symlink, count 293 or
  the pre-move count, same database and project id, `task ready` and `state` in
  main checkout and worktree); US-4 (`git push` of a branch prints
  `gin-workflow pre-push: test:`).

### Track 3: Migrate gin-console
- **Dependencies**: Track 2
- **Provider role**: `general`
- **Reasoning**: `high`
- **Estimated complexity**: medium
- **Files**: `~/gin-console/.beads` (symlink), `~/gin-console/.gitignore`, `~/gin-harness/beads/gin-console/`, `~/gin-harness/backup/gin-console-<date>/`
- **Interfaces**: produces `~/gin-harness/beads/gin-console`.
- **Steps**: follow the skill for `<repo>` = `~/gin-console`. The 10 tracked
  files are untracked with `git rm -r --cached .beads` on branch
  `chore/beads-to-harness` in gin-console, with `.beads` added to its
  `.gitignore`; commit and push that branch. `core.hooksPath` already points to
  `.beads/hooks`, which moves with the directory; check that `git commit` there
  still runs the bd pre-commit hook (`BD_GIT_HOOK=1` in its output or no error).
- **Acceptance criteria**: US-1 criteria for gin-console (symlink, count 31 or
  the pre-move count, same database and project id, nothing under `.beads`
  tracked, `.beads` in `.gitignore`).

### Track 4: Harness database and cross-repo dependencies
- **Dependencies**: Track 3
- **Provider role**: `general`
- **Reasoning**: `high`
- **Estimated complexity**: medium
- **Files**: `~/gin-harness/.beads/`, `~/gin-harness/.gitignore`, the `config.yaml` of all three databases
- **Interfaces**: consumes the two database paths from Tracks 2–3.
- **Steps**:
  1. In `~/gin-harness`: `bd init --prefix gin-harness`; write `.gitignore` with
     `beads/`, `backup/` and `.beads/` except `.beads/config.yaml`; commit on
     branch `chore/beads-init` (the harness has no commits yet).
  2. Add `external_projects` to each database's `config.yaml`, mapping
     `gin-workflow`, `gin-console`, `gin-harness` to the other database
     directories (`~/gin-harness/beads/gin-workflow`, `~/gin-harness/beads/gin-console`,
     `~/gin-harness/.beads`). If the US-5 probe below does not resolve with
     database directories, use the repo roots instead and record which form works
     in the skill.
  3. US-2 check: `bd context` in `~/gin-harness` shows prefix `gin-harness`;
     `bd create "probe" -t task` returns a `gin-harness-` id; delete it.
  4. US-5 probe: in gin-workflow create a task labelled `export:probe-cap`; in
     gin-console create a task and `bd dep add <it> external:gin-workflow:probe-cap`;
     check it is absent from `bd ready` and `gin-workflow task ready`; close the
     gin-workflow task and `bd ship probe-cap`; check it now appears in both.
     Delete both probe beads. If `gin-workflow task ready` disagrees with
     `bd ready`, file a bug bead in gin-workflow.
- **Acceptance criteria**: US-2 and US-5 criteria; the probe beads are gone.

## Integration
- **Branch**: `feat/beads-harness-migration` in gin-workflow (Track 1);
  `chore/beads-to-harness` in gin-console (Track 3); `chore/beads-init` in gin-harness (Track 4).
- **Merge strategy**: sequential. Track 1 merges to gin-workflow master before
  Track 2 starts (needs user approval at that point).

## Validation
- [ ] Full gin-workflow suite passes (Track 1)
- [ ] US-1 checks for both repos, recorded as evidence (Tracks 2–3)
- [ ] US-2, US-4, US-5 checks recorded (Tracks 2, 4)
- [ ] Backups exist under `~/gin-harness/backup/` until the epic ships

## Notes
- Parent bead: the deliverable; it stays open until the human-confirmed merge
  of Track 1's branch and the gin-console and gin-harness branches.
- Track beads close when their tests or checks and review pass.
- The probe beads in Track 4 must be deleted; they are not part of the evidence.
