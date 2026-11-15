# Plan: Scoped commit for BA and tester output

Spec: .planning/specs/2026-11-14-scoped-commit-design.md
Epic: gin-workflow-yasu
Workflow: gin-workflow-yasu

## Objective

`gin commit <path>... -m <message>` commits only the named paths, on a new branch when the user is on the default branch, and never pushes; gin-qa and gin-ba skills offer it after the user reviews their output.

**Goal** (spec): testers and BAs who are not comfortable with git save their gin-qa and gin-ba output with one command that commits only the named paths, never on `main`/`master`, and never pushes.

**Architecture**: one new module `workflow_core/scoped_commit.py` (argument parsing, checks, branch choice, `git add -A` and `git commit --only`, output), dispatched from `cli.py` as the top command `commit`. It reuses `workspace.locate` for the entry's `default_branch`. Skills name the command; gin-qa and gin-ba import nothing from gin-workflow.

**Tech Stack**: Python 3 standard library, `git` subprocesses; unittest/pytest with real temporary git repositories (follow `tests/workflow_core/test_worktrees.py` or `test_hooks.py` setup); Markdown skills under the 6,000-character budgets (`tests/gin_qa/test_packaging.py`, `tests/gin_ba/test_ba_packaging.py`).

**Global Constraints** (spec, verbatim):
- Out of scope: push and pull requests (they stay manual or with a developer); a commit guard on `main`/`master` for everyone (the remote branch protection in CI already rejects pushes to `master`); the gin-qa `report` skill (its output lives under the git-ignored `evidence/` and must not be committed); the `/gin:discuss` commit of BA asset folders with their change folder (unchanged).
- A new command only; no existing command changes.
- A pre-commit hook failure makes `gin commit` exit with the hook's status and message; a branch it created stays, with nothing committed.
- Skill files stay within the gin-qa budget (6,000 characters) and the gin-ba budget.

## Route Rubric
- Choose the weakest model that can do the work.
- Raise the model for broad context or design judgement.
- Raise the effort for intrinsic difficulty: intricate logic, many edge cases, or long chains of steps.

| Kind of work | Model | Effort |
|---|---|---|
| Mechanical edits, documentation, boilerplate | weakest | `low` |
| Bounded implementation with a clear spec | middle | `medium` |
| Cross-module change, security, migration, concurrency | strongest | `high` |

Unclear requirements never raise the model or effort.

## Requirement Analysis
- Problem statement: testers and BAs commit by hand and by mistake (on `master`, with unrelated files).
- Success criteria: spec requirements 1–8 and US-1 to US-3; `python3 -m pytest -n auto` passes.
- Constraints: Global Constraints above.
- Non-goals: push, pull requests, a global `master` guard.

## Approach Options
### Option 1: one `gin commit` command, skills offer it (selected in `/discuss`)
- Summary: as the spec.
- Pros: one tested place for the git rules; skills stay short.
- Cons: a new top-level command.

### Option 2: skill-only (the agent runs git after asking)
- Summary: no CLI; each skill describes the git steps.
- Pros: no code.
- Cons: the rules (only these paths, never `master`) depend on each agent run; untestable; rejected.

### Recommended Approach
- Selected option: Option 1 (confirmed in `/discuss` on 2026-11-14).
- Rationale: deterministic and testable; the user chose commit-only scope and an automatic branch.

## Scope
- In scope: spec requirements 1–8.
- Out of scope: see Global Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: the skills and guides name the command Track 1 ships; one lane.
```

## Tasks

Run tests from the repository root.

### Track 1: `gin commit`
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/scoped_commit.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py:20-21,105-107` (`commit` in `TOP_COMMANDS`; dispatch like `goal`)
  - Modify `docs/reference/cli.md` (new `gin commit` section)
  - Test `tests/workflow_core/test_scoped_commit.py` (new)
- **Provider role**: `backend`
- **Model:** `sonnet`
- **Effort:** `medium`
- **Why:** bounded git logic with listed edge cases and real-repository tests.
- **Interfaces**:
  - `scoped_commit.main(argv: Sequence[str]) -> int`; arguments: `paths` (one or more), `-m/--message` (required), `--branch`, `--format text|json`.
  - `scoped_commit.commit(cwd: Path, paths: Sequence[str], message: str, branch: str | None = None, today: date | None = None) -> dict` returning `{"repository", "branch", "created_branch", "commit", "files", "pushed": False}` or `{"nothing_to_commit": True, "branch", ...}`; raises `ScopedCommitError` (exit 2) for refusals.
  - Checks, before any change: message non-empty after strip; each path resolved against `cwd` exists or is a tracked path in the index (`git ls-files --error-unmatch` for a deleted file); all paths share one `git rev-parse --show-toplevel` (paths in two repositories refused, naming both); `git symbolic-ref -q HEAD` succeeds (detached refused).
  - Default branch: current branch (`git branch --show-current`) is `main`, `master`, or `workspace.locate(<repository root>).entry.default_branch` when `entry` is not None (a `WorkspaceError` from a broken workspace config is ignored: only `main`/`master` count then). New branch name: `--branch`, else `gin/<slug>-<YYYY-MM-DD>` with `<slug>` = the first path relative to the repository, lower-cased, non `[a-z0-9]` runs replaced by `-`, trimmed, at most 40 characters; while `git rev-parse --verify --quiet refs/heads/<name>` succeeds, append `-2`, `-3`, ... Create with `git switch -c <name>` (working-tree changes carry over, uncommitted). An invalid `--branch` (`git check-ref-format --branch` fails) is refused before any change.
  - Nothing to commit: after the checks and before any branch switch, `git status --porcelain --untracked-files=all -- <paths>` empty → return nothing to commit (no branch created).
  - Commit: `git add -A -- <paths>`, then `git commit --only -m <message> -- <paths>`; a non-zero commit exit (a hook) is reported with git's stderr and the same exit code. Never call `push`, never pass `--no-verify`.
  - Output text: `Committed <n> files to <branch> (<sha7>)`, `Created branch <branch>` when created, one line per file, then `Not pushed.`; nothing to commit: `Nothing to commit under <paths>.`
- **Steps**:
  1. Failing tests in `tests/workflow_core/test_scoped_commit.py` (a helper builds a temp repo with `git init -b master`, user config, one commit; run the CLI via the `gin` launcher or `scoped_commit.main` with `cwd` changed):
     - on a feature branch, another file staged, `gin commit qa/cases/catalog -m x` commits only files under that folder; the other file stays staged; `git log -1 --name-only` lists only them;
     - new, modified, and deleted files under the path are committed; a file matched by `.gitignore` under the path is not;
     - on `master`: creates `gin/qa-cases-catalog-<date>`, commits there, `master` unchanged, output says "Created branch" and "Not pushed."; a second run the same day on `master` with that branch existing creates `...-2`; `--branch qa/my-cases` is used as given;
     - workspace child whose entry has `default_branch: develop`, on `develop`: a branch is created;
     - refusals exit 2 with branch, index, and `git log` unchanged: missing path, path outside the repository, two repositories, detached HEAD, empty message, invalid `--branch`;
     - nothing to commit: exit 0, "Nothing to commit", no branch created;
     - a pre-commit hook that exits 1: the command exits non-zero with the hook message, nothing committed;
     - no push: a bare remote configured as `origin` keeps its refs; JSON output has `pushed: false`.
     Run `python3 -m pytest tests/workflow_core/test_scoped_commit.py -q` → fail.
  2. Implement per Interfaces; add `commit` to `TOP_COMMANDS` and the dispatch.
  3. `docs/reference/cli.md`: a `gin commit` section (usage, checks, branch rule, nothing to commit, never pushes, exit codes 0/2/hook status, JSON keys).
  4. `python3 -m pytest tests/workflow_core/test_scoped_commit.py tests/workflow_core/test_docs_coverage.py -q -n auto` → pass; `gin docs check docs/reference/cli.md` → ok.
  5. Commit: `feat(cli): gin commit commits only the named paths, off the default branch, without pushing (gin-workflow-yasu)`.
- **Acceptance criteria**: spec requirements 1–6 and the `cli.md` part of 8; US-1; US-2.
- **Estimated complexity**: medium

### Track 2: skills and guides offer `gin commit`
- **Dependencies**: Track 1
- **Files**:
  - Modify `plugins/gin-qa/src/skills/cases/SKILL.md:21`, `plugins/gin-qa/src/skills/e2e/SKILL.md:21`, `plugins/gin-qa/src/skills/tests/SKILL.md:29`, `plugins/gin-qa/src/skills/run/SKILL.md:20`, `plugins/gin-qa/src/skills/setup/SKILL.md:36`
  - Modify `plugins/gin-ba/src/skills/capture/SKILL.md:30`, `plugins/gin-ba/src/skills/mockup/SKILL.md:37`
  - Modify `docs/guides/qa.md`, `docs/guides/qa.vi.md`, `docs/guides/ba.md`, `docs/guides/ba.vi.md`
  - Test `tests/gin_qa/test_packaging.py`, `tests/gin_ba/test_ba_packaging.py` (unchanged; must pass)
- **Provider role**: `docs`
- **Model:** `haiku`
- **Effort:** `low`
- **Why:** one short step per skill and one paragraph per guide, guarded by budget tests.
- **Steps**:
  1. Each gin-qa skill (`cases`, `e2e`, `tests`, `run`, `setup`): replace "Do not commit; the user reviews and commits." (or the equivalent "Do not commit; the tester reviews and commits the case files.", or add after the report step in `setup` and `tests`) with: "After the user reviews, ask whether to save the work. Only on a yes, run `gin commit <the files and folders this run wrote> -m \"<capability>: <what was written>\"` and report the branch and that it is not pushed; on exit 2, show the message and change nothing." Name the concrete folders per skill (cases: `<cases>/<capability>/`; e2e: the spec files under `<e2e>/<capability>/`; tests: the test files written; run: the case files whose results changed; setup: the guidelines, README, and project skill files). `report` stays unchanged.
  2. gin-ba `capture` and `mockup`: keep "Do not commit; `/gin:discuss` commits the confirmed folder with the change folder that cites it." and add: "To save the dated folder before that, on the BA's yes run `gin commit <dated folder> -m \"<capability>: <capture|mockup> <date>\"`."
  3. `docs/guides/qa.md` and `ba.md`: a short "Saving your work" paragraph: the skill offers `gin commit` after review; it commits only those files, creates a branch when you are on `master`/`main`, and never pushes; push and the pull request stay with you or a developer; link to `docs/reference/cli.md#gin-commit` (use the real anchor). Mirror in `.vi.md`.
  4. `python3 -m pytest tests/gin_qa/test_packaging.py tests/gin_ba/test_ba_packaging.py tests/workflow_core/test_docs_coverage.py -q` → pass; `gin docs check docs/guides/qa.md docs/guides/ba.md docs/guides/qa.vi.md docs/guides/ba.vi.md` → ok; `python3 -m pytest -n auto` → pass.
  5. Commit: `docs(qa,ba): skills offer gin commit after review (gin-workflow-yasu)`.
- **Acceptance criteria**: spec requirements 7 and the guide part of 8; US-3.
- **Estimated complexity**: low

## Integration
- **Branch**: `feat/scoped-commit`
- **Merge strategy**: sequential

## Validation
- [ ] `python3 -m pytest -n auto` passes
- [ ] `gin docs check` passes on the changed docs
- [ ] gin-qa and gin-ba skills stay within 6,000 characters

## Notes
- The user may override `Model:` and `Effort:` before plan approval.
- Deliverable merge-holds apply only to the Parent Bead; track beads close once tests and review pass.
