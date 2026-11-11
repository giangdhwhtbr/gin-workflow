# gin-qa runs from the qa child, its worktrees, and a QA folder anywhere

Epic: gin-workflow-qa-workspace
Status: confirmed by the user on 2026-11-11.

## Goal and scope

gin-qa reads config, specs, and Beads from the project root (the workspace parent, or the repository root), and keeps everything QA owns under one QA home: the `shape: qa` workspace child, or a configurable folder of a single repository. The Playwright project is a subfolder of the QA home. gin-qa then runs from the QA child, from a worktree of it, or from any directory of the project.

The process review (`.planning/reviews/2026-11-07-process-review/synthesis.md`, cluster "gin-qa runs from the qa child and its track worktrees", P1) found:
- QA-1 (blocker): gin-qa uses the current directory as the repository root (`plugins/gin-qa/src/scripts/gin_qa/cli.py:20`) and stops when it has no `.agent-workflow/config.yaml` (`gin_qa/reqs.py:37-38`), so it cannot run from the `qa` child the workspace guide sends QA to (`docs/guides/workspace.md:104-106`).
- QA-2: run from the parent, gin-qa writes `playwright.config.ts`, `package.json`, and the evidence ignore line into the parent (`gin_qa/e2e.py:192-200,224-228,277-282`) and reads case-ID history from the parent's git log (`gin_qa/cases.py:242-243`).

Research on 2026-11-11 also found that a single repository cannot keep its Playwright project in a subfolder: `e2e.py` requires `package.json` and `playwright.config.*` at the repository root and runs `npm`/`npx` there. gin-qa calls `gin` by subprocess and imports none of `workflow_core` (`gin_qa/reqs.py:34`); the core already resolves a child or worktree directory to the workspace root when `--repository` is omitted (`workflow_core/workspace.py:136-157`); `qa` is an allowed workspace shape (`workspace.py:17`).

In scope:
- Project root and QA home resolution through `gin specs reqs`.
- A `qa.dir` setting and QA-home-relative defaults.
- The Playwright project in `<QA home>/e2e`.
- Case-ID history from the git repository that holds the QA home.
- Docs and skills.

Out of scope:
- QA tracks in the lifecycle, acceptance cases in review and ship (`gin-workflow-qa-lifecycle`).
- Moving files of existing projects.

Confirmed summary (user, 2026-11-11): everything QA owns lives in one QA home with Playwright as its `e2e` subfolder; in a workspace the QA home is the `shape: qa` child (any path and name), in a single repository it is `qa.dir` (default `qa`); gin-qa learns the project root and QA root from `gin specs reqs`; existing projects with Playwright at the repository root keep working.

## Requirements

R1. `gin specs reqs --format json` adds two keys: `root`, the project root `gin` resolved, and `qa_root`, the QA child's checkout in a workspace or null. `qa_root` is the current directory's checkout (main checkout or linked worktree) when that directory belongs to the `shape: qa` entry, else that entry's checkout under the workspace root. With more than one `shape: qa` entry the command fails naming them; with none, `qa_root` is null.

R2. gin-qa calls `gin specs reqs` without `--repository` when the user gave none, so the core resolves the project root from the current directory; with an explicit `--repository` it passes it on as today. It no longer requires `.agent-workflow/config.yaml` in the current directory. A `gin` whose payload lacks `root` is refused with "this gin is too old for gin-qa; reinstall gin-workflow".

R3. gin-qa resolves once per command a project root (from `root`) and a QA home: `qa_root` when it is not null, else `<root>/<qa.dir>` where `qa.dir` defaults to `qa` and must be a path inside the repository.

R4. Default QA paths are relative to the QA home: `cases`, `guidelines.md`, `evidence`, and `e2e`. An explicit `qa.cases`, `qa.guidelines`, or `qa.e2e` is relative to the git repository that holds the QA home: the project root in a single repository (its current meaning), the QA child in a workspace. The project root keeps config, specs, requirements, Beads (`gin task`), and `gin state`.

R5. Case-ID history (`git log` in `cases.py`) runs in the git repository that holds the QA home.

R6. `gin-qa e2e` keeps its Playwright project in `<QA home>/e2e`: `package.json`, the lockfile, `playwright.config.ts`, `node_modules`, and the `npm`/`npx` commands all use that folder. The evidence ignore line is written to the `.gitignore` of the repository that holds the QA home, with a path relative to it. When the project root already has `playwright.config.*`, or a `package.json` with an `e2e` script, and `qa.dir` is not set, gin-qa keeps using the project root as today.

R7. `docs/guides/qa.md`, `docs/guides/workspace.md`, `docs/starters/brownfield.md`, and the gin-qa skills (`e2e`, `setup`, and any that name the repository root) describe the QA home, `qa.dir`, the workspace QA child, and running from the QA child or its worktree. The project QA skill written by setup goes to the project root.

## User Stories

### US-1: QA works from the qa repository
As a QA engineer in a workspace, I want gin-qa to run from the `qa` repository and its track worktrees, so that I follow the guide without errors.

Acceptance criteria:
- From the `qa` child, `gin-qa cases next-id <capability>` reads requirements from the parent and returns an ID based on the child's git history.
- From a linked worktree of the `qa` child, the same command uses the worktree's files and history.
- `gin-qa e2e` writes `e2e/package.json`, `e2e/playwright.config.ts`, and the evidence ignore line in the child; the parent's files are unchanged.

### US-2: A QA folder anywhere in a single repository
As a tech lead of a monorepo, I want to set `qa.dir: new-app/testing`, so that cases, evidence, and the Playwright project all live in that folder.

Acceptance criteria:
- With `qa.dir: new-app/testing`, cases go to `new-app/testing/cases` and the Playwright project to `new-app/testing/e2e`.
- `qa.dir: ../x` is refused as outside the repository.

### US-3: Existing projects keep working
As a QA engineer on an existing project, I want my root-level Playwright setup to keep working, so that the change does not break my runs.

Acceptance criteria:
- A repository with `playwright.config.ts` at the root and no `qa.dir` keeps running `npx playwright test` at the root.
- Explicit `qa.cases: qa/cases` keeps resolving to `<root>/qa/cases`.
- The existing gin-qa tests pass unchanged.

## Errors and compatibility

- Without a workspace and without `qa.dir`, the QA home is `<root>/qa`, which matches today's default paths (`qa/cases`, `qa/guidelines.md`, `qa/evidence`, `qa/e2e`); only the Playwright project moves from the root into `qa/e2e` for new setups (R6 keeps existing root setups).
- `gin` older than this change: gin-qa refuses with the reinstall message (R2).
- The `specs reqs` JSON only gains keys; gin-console does not read it.

## Testing

- `tests/gin_qa/`: a workspace fixture (parent with a manifest, a `qa` child as its own git repository, a linked worktree of the child) covering US-1; a single-repository fixture with `qa.dir` covering US-2; a root-Playwright fixture covering US-3; existing gin-qa tests unchanged.
- `tests/workflow_core/`: `specs reqs` payload with `root` and `qa_root` from the parent, the child, a child worktree, and with two `qa` entries.
- `gin docs check` on changed docs; skill budget tests.

## Open Technical Questions

## Assumptions

- `qa.dir` is a new key of the `qa:` block in `.agent-workflow/config.yaml`; the config schema accepts it.
- In a workspace with a `qa` child, `qa.dir` is ignored and the child's root is the QA home.
- `gin task` run with the project root as its working directory uses the workspace's Beads database.
