# Per-entry checks, rule packs, and shape in a workspace

Epic: gin-workflow-ws-entry-rules
Status: draft for user review.

## Goal and scope

Inside a workspace child, or a worktree of one, `gin evidence`, `gin rules`, `gin setup doctor`, `gin state`, and the execute and worktrees skills use the current entry's `verify.checks`, rule packs, and shape instead of the parent's.

In scope: `workflow_core` (`verification.py`, `rules.py`, `rules_checks.py`, `setup_service.py`, `lifecycle_cli.py`, `workspace.py`, `schemas.py`); the `execute` and `worktrees` skills; `docs/guides/workspace.md`, `docs/reference/config.md`, `docs/reference/cli.md`; tests.

Out of scope: `java` and `spring` rule packs and tech-doc route scouting for Spring, JAX-RS, Struts, and JSP (split into a follow-up epic, added to the roadmap with `/gin:roadmap`); team init per child (`gin-workflow-ws-child-setup`); `project.packages` inside a child.

Confirmed understanding (no epic comments, no prep tasks): git hooks and `gin quick-check` already use the child entry's checks through `workspace.locate`. `gin evidence run/check` resolve the default `--repository` to the parent (`verification.py:93`), so `run` checks the parent's tree and `check` from a child cannot find the record the hook wrote. `gin rules` uses the parent's `rules.packs` and parent-relative paths, so root-anchored globs (`app/**`) miss child files. `gin setup doctor` scopes `verify_commands` and rules to the parent. `gin state` reports the parent's `project.shape` in a child, and the execute skill reads it; the entry's checks are not in `gin state`. The user chose to split the Java and JSP part into its own epic.

Comments considered: 0

## Requirements

1. One resolver: commands below resolve the current checkout with `workspace.locate(<cwd or --repository>)`; `Located.entry` is the current entry, `None` in the parent or outside a workspace. An explicit `--repository` keeps its meaning (taken as given). Outside a workspace and in the parent, behaviour is unchanged.
2. `gin evidence run` and `gin evidence check`: in a child or its worktree, they check the clean tree of that checkout, run the entry's `verify.checks` through the existing hook path, and record and look up the result in the parent's event log, as git hooks do; `check` from a child finds the record a child pre-push hook wrote.
3. `gin state --format json`: the `workspace` object gains `current`: `{"path", "shape", "checks"}` of the current entry (`checks` the entry's `verify.checks` mapping), or `null` in the parent. Existing keys, including `project.*` and `workspace.current_repo`, do not change.
4. Rule packs per entry: a `workspace.repos` entry accepts an optional `rules: {packs: [<name>...]}`. In a child, `gin rules --files` enables the parent's packs plus the entry's `rules.packs`, reads project rules from the child checkout, and matches globs against paths relative to the child checkout. An unknown pack name in an entry warns like the root `rules.packs` does.
5. `gin setup doctor`: run from a child, its `verify_commands`, rules doctor (tool checks, conflict warnings), and hook findings use the current entry and its checkout. The workspace section, which reports every entry, also proposes, per entry, the packs `propose_packs` detects in that child's checkout that its `rules.packs` does not list.
6. Skills: the execute skill reads the shape appendix for `workspace.current.shape` when it is set, else `project.shape`; the worktrees skill's baseline runs `workspace.current.checks` when set, else the configured verify commands. Both stay within their skill budgets.
7. Docs: `docs/reference/config.md` documents the entry's `rules.packs`; `docs/reference/cli.md` documents `workspace.current` and the child behaviour of `evidence`, `rules`, and `setup doctor`; `docs/guides/workspace.md` describes per-entry checks, packs, and shape.

## User Stories

### US-1: Evidence from a child repository
As a developer in a workspace child, I want `gin evidence run` and `check` to use my repository's checks and tree, so that the evidence matches what the pre-push hook ran.

Acceptance criteria:
- From a child, `gin evidence run` runs the entry's `verify.checks` and records the child's tree.
- From the child's linked worktree, `gin evidence check` exits 0 after a passing run there.
- From the parent, both behave as today.

### US-2: Rules for the stack of the child
As a developer in a frontend child, I want `gin rules` to apply the packs of that child, so that the rules match its stack.

Acceptance criteria:
- With `rules: {packs: [react, nextjs]}` on the entry, `gin rules --files app/page.tsx` run in the child includes the `nextjs` and `react` packs.
- The same command in a child without `rules.packs` uses only the parent's packs.
- `gin setup doctor` run in the parent proposes `react` for a child whose `package.json` depends on `react` and whose entry does not list it.

### US-3: The right shape and checks in the lifecycle
As an agent executing a track in a child worktree, I want `gin state` to name the entry's shape and checks, so that I read the right shape appendix and run the right baseline.

Acceptance criteria:
- `gin state --format json` in a backend child reports `workspace.current.shape` `backend` and its `checks`; in the parent `workspace.current` is `null`.
- `project.*` keys are identical from the parent, a child, and its worktree.
- The execute and worktrees skills name `workspace.current.shape` and `workspace.current.checks`.

## Errors and compatibility

- `gin state` JSON only gains `workspace.current`; gin-console parses no removed or renamed key.
- The entry `rules` field is optional; existing workspace manifests stay valid without a schema version change.
- A command run with an explicit `--repository` behaves as before.

## Testing

- `tests/workflow_core/test_hooks.py` or a new workspace evidence test: `evidence run`/`check` from parent, child, and child worktree.
- `tests/workflow_core/test_workspace_cli_resolution.py`: `workspace.current` from parent, child, worktree; `project.*` still identical.
- `tests/workflow_core/test_rules.py`: `gin rules --files` from a child with and without entry packs; root-anchored glob matches.
- `tests/workflow_core/test_workspace_cli.py`: doctor from a child scopes checks and rules; pack proposals per entry.
- Schema test for the entry `rules.packs`; skill budget tests; full suite `python3 -m pytest -n auto` passes.

## Open Technical Questions
