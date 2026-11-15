# Scoped commit for BA and tester output

Epic: gin-workflow-yasu
Status: draft for user review.

## Goal and scope

Testers and BAs who are not comfortable with git save their gin-qa and gin-ba output with one command that commits only the named paths, never on `main`/`master`, and never pushes.

In scope: a `gin commit` command (`workflow_core`, a new module plus `cli.py` dispatch); the gin-qa skills `cases`, `e2e`, `tests`, `run`, and `setup`; the gin-ba skills `capture` and `mockup`; `docs/reference/cli.md`, `docs/guides/qa.md`, `docs/guides/ba.md` and their `.vi.md` versions; tests.

Out of scope: push and pull requests (they stay manual or with a developer); a commit guard on `main`/`master` for everyone (the remote branch protection in CI already rejects pushes to `master`); the gin-qa `report` skill (its output lives under the git-ignored `evidence/` and must not be committed); the `/gin:discuss` commit of BA asset folders with their change folder (unchanged).

Confirmed understanding (no epic comments, no prep tasks): the epic was deferred on 2026-11-07 until a real BA or tester hit a commit problem; the user reports that the team's testers and BAs commit by mistake, which reopens it. Today the gin-qa skills end with "Do not commit; the user reviews and commits", gin-ba's capture and mockup never commit, no gin command runs `git commit`, and nothing local stops a commit on `master`. The user chose the commit-only scope (no push or PR) and an automatic branch when the user is on the default branch, because a local commit on `master` is rejected at push by the remote protection and leaves the local `master` diverged, which these users cannot repair.

Comments considered: 0

## Requirements

1. `gin commit <path>... -m <message> [--branch <name>] [--format text|json]` commits the named files and folders only.
2. Checks before any change, each exiting 2 with a message and changing nothing: every path exists (a deleted tracked file named by path also counts) and resolves inside one git repository (the repository holding the first path; in a workspace this may be a child such as the QA repository); paths in different repositories are refused; a detached `HEAD` is refused; an empty message is refused.
3. Default branch: when the current branch is `main`, `master`, or the `default_branch` of the workspace entry the repository belongs to, the command creates a new branch and switches to it before committing. The name is `--branch` when given, else `gin/<slug of the first path>-<YYYY-MM-DD>`; an existing name gets `-2`, `-3`, and so on. Changes outside the named paths stay in the working tree, uncommitted.
4. Commit: `git add -A -- <paths>` (new, changed, and deleted files; ignored files stay out), then `git commit --only -m <message> -- <paths>`, so the commit holds only the named paths even when other changes are already staged. Git hooks run as usual; the command never passes `--no-verify`.
5. It never pushes and never runs `git push`. Output: the branch, whether it was created, the commit SHA, the committed files, and the line "not pushed". JSON: `{"branch", "created_branch", "commit", "files", "pushed": false}`.
6. Nothing to commit under the paths: exit 0 with "nothing to commit", no branch created.
7. Skills: gin-qa `cases`, `e2e`, `tests`, `run`, and `setup` replace "Do not commit; the user reviews and commits" with: after the user reviews, ask whether to save the work, and only on their yes run `gin commit <the folders and files the skill wrote> -m "<message naming the capability and the skill>"`, then report the branch and that it is not pushed. gin-ba `capture` and `mockup` add the same optional step for the dated asset folder.
8. Docs: `docs/reference/cli.md` documents `gin commit`; `docs/guides/qa.md` and `docs/guides/ba.md` (and `.vi.md`) say how to save work with it and that push and pull requests remain manual.

## User Stories

### US-1: Save test cases without git knowledge
As a tester, I want to save the cases and tests the skill wrote with one confirmation, so that nothing else from my working tree and nothing on `master` gets committed.

Acceptance criteria:
- On a feature branch, `gin commit qa/cases/catalog -m "..."` commits exactly the files under `qa/cases/catalog`, even with another file already staged.
- On `master`, the same command creates `gin/qa-cases-catalog-<date>`, commits there, and `master` is unchanged.
- An existing branch name gets a numeric suffix.
- The command never pushes, and its output says "not pushed".

### US-2: Mistakes are refused, not committed
As a tester or BA, I want a wrong command to change nothing, so that I cannot make my repository worse.

Acceptance criteria:
- A path outside the repository, paths in two repositories, a detached `HEAD`, or an empty message exits 2 and leaves the branch, index, and history unchanged.
- An ignored file under a named folder is not committed.
- With no change under the paths, the command exits 0, says "nothing to commit", and creates no branch.

### US-3: Skills offer to save
As a BA or tester using gin-qa or gin-ba skills, I want the skill to offer to save my output after I review it, so that I do not run git myself.

Acceptance criteria:
- gin-qa `cases`, `e2e`, `tests`, `run`, `setup` and gin-ba `capture`, `mockup` ask before saving and run `gin commit` only on a yes.
- gin-qa `report` still says not to commit the report.

## Errors and compatibility

- A new command only; no existing command changes.
- A pre-commit hook failure makes `gin commit` exit with the hook's status and message; a branch it created stays, with nothing committed.
- Skill files stay within the gin-qa budget (6,000 characters) and the gin-ba budget.

## Testing

- A new test module with real git repositories: scoped commit with other staged changes, new and deleted files, ignored files excluded, branch creation on `master` and on a workspace entry's `default_branch`, name suffixes, refusals (outside path, two repositories, detached `HEAD`, empty message) leave state unchanged, nothing to commit, no push (no `push` in the git calls; a remote stays unchanged), JSON output.
- Skill packaging and budget tests for gin-qa and gin-ba; `gin docs check` on the changed docs; full suite `python3 -m pytest -n auto` passes.

## Open Technical Questions
