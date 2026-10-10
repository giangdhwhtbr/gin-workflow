# Drop the verify stage; enforce quality in git hooks and a mechanical ship-check

Status: draft for user review (revision 4, after three independent Opus reviews).

## Goal and scope

The `verify` stage makes the agent re-run the whole quality suite, validate every
review ledger and re-read the spec line by line. Its evidence is pinned to the branch
tip, and its gate (`verification_passed`) is a Safety gate that only a human can waive.
In an autonomous `/goal` over a whole epic, any later commit (even a `chore(review)`
one) returns the gate to unmet, so the agent re-verifies in a loop and burns tokens.
`ship` then re-runs the tests twice more (before and after merge).

Goal: remove the stage and gate; move mechanical checks into git hooks and one
deterministic `ship-check` command, neither of which spends agent tokens. A goal over an
epic must reach `ship`, present its options, and never loop on a gate it cannot satisfy
(the merge itself still needs the user's explicit approval).

Delivered as two tracks so the safe additions land first:
- **A. Hooks:** `gin-workflow hooks install|run`, `setup doctor` hook check, blocking
  `--no-verify` in `safety-check.sh`. Additive only; shippable alone.
- **B. Remove verify:** stage, gate, `ship-check`, leaner `ship`, team-mode approval moved
  to `ship` (must land with the gate removal so team mode never ships unapproved), docs,
  tests, `dist/*`.

Out of scope: reading CI/CD results or calling `gh` for CI; a `verify.mode` key;
migrating old `verification.passed` events; review-ledger logic and its FSM actions
(`verify-finding`, `verification-*`, `ready-to-ship`), `verify.checks` config, `verify-bundle`
(all kept); bug `gin-workflow-il4`.

## Requirements

Stage and gate
- R1. Stages are `discuss, plan, orchestrate, execute, ship`. The router goes from
  satisfied `implementation_complete` straight to `ship`.
- R2. Removed: the `verify` stage, `skills/verify`, `/gin-workflow:verify`, the
  `verification_passed` gate and its Safety waiver, `record verification-passed`, the
  `verification.passed` event, `model_tiers.verify`, and the `verify` usage-attribution
  stage. Old events stay in the store and are ignored. Kept: `verify_commands`,
  `verify.checks`, and every review-ledger verification action.
- R3. `record verification-passed` and `unblock --gate verification_passed` exit 2 with a
  message pointing to the hooks and `ship-check`. A config still naming
  `verification_passed` loads with a deprecation warning. `team.approvals.verification_passed`
  is mapped to `team.approvals.ship` with a deprecation warning, so a team keeps its roles.
  `examples/config.full.yaml` is updated.

Hooks (track A)
- R4. `gin-workflow hooks install` generalises `team_init.install_hook()` (today hard-coded
  to `commit-msg`) and reuses `active_hooks_dir()`: writes marker-tagged `pre-commit` and
  `pre-push` shims that call `gin-workflow hooks run <hook>`, is idempotent, and never
  overwrites a hook it did not write (reports `occupied` and prints how to chain the
  call; for `.beads/hooks` it prints the chaining line for bd's own hooks). It honors an
  existing `core.hooksPath`; shims written into the versioned `.githooks` are committed
  by `/setup` (an untracked shim would dirty review checkpoints). A `core.hooksPath`
  directory that does not exist is reported and not created; this intentionally changes
  the current `commit-msg` install, which creates it. `/setup` calls it. If `gin-workflow` is not on PATH the shim fails
  closed with an install message. Hooks apply in linked worktrees (shared hooks dir).
- R5. `setup doctor` reports hooks that are missing, occupied, or not on the active hooks
  path.
- R6. `hooks run pre-commit` runs the `lint` and `typecheck` entries of
  `project.verify_commands`. It operates on the working tree and says so; it does not
  isolate staged content.
- R7. `hooks run pre-push` reads the pushed refs from stdin, skips deletes and tags, and
  runs only when a pushed local sha is the checked-out HEAD; otherwise it prints a notice
  that nothing was tested (`ship-check` covers that case). `hooks run pre-push --head`
  (also used when stdin is empty) tests HEAD directly; `ship-check` uses it. It runs the remaining
  `verify_commands` allowed by rigor (easy: test; standard: + build; strict: + e2e;
  per-package `verify.checks` run in the package directory, for packages touched since the
  merge-base with the base branch, falling back to all packages; the chosen package set is
  part of `commands_hash`). `--head` also runs the `lint` and `typecheck` entries. A push
  is skipped when an event already matches `<sha>:<commands_hash>`. On success, and only if
  `git status --porcelain --untracked-files=no` is empty, it records an event
  `hooks.pre_push.passed` with `workflow_id: git-hooks`, payload `{sha, rigor,
  commands_hash}` and `idempotency_key=<sha>:<commands_hash>`, written only when
  `.agent-workflow/runtime/` already exists (no new runtime dirs in consumer repos).
  A changed command set changes `commands_hash` and invalidates the evidence.
- R7a. `hooks run` removes `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_PREFIX`,
  `GIT_OBJECT_DIRECTORY` and `GIT_COMMON_DIR` from the environment before running the
  commands.
- R8. Commands run in order and stop at the first failure, printing that command's output
  and exiting non-zero. Empty `verify_commands` prints a notice and exits 0. The hook
  itself never calls an agent or retries; the configured commands may use whatever
  resources they need (e.g. e2e services).
- R9. `scripts/safety-check.sh` finds the git subcommand after global options and blocks:
  `--no-verify` on `commit`, `push` and `merge`; `-n` (alone or bundled, e.g. `-nm`) only
  on `commit`; `-c core.hooksPath`, `--config-env` naming `core.hooksPath`, and
  `git config core.hooksPath`. It tokenizes the command with `shlex` after splitting `&&`, `;`, `|`, `bash -c` and `env X=`
  prefixes, treats unambiguous long-option prefixes (`--no-verif`) as the option, and also
  blocks `GIT_CONFIG_PARAMETERS`/`GIT_CONFIG_COUNT`. It allows `git push -n` and
  `git commit -m "fix -n flag"`. It is a best-effort guard that exists only on harnesses
  with a PreToolUse hook.

Ship (track B)
- R10. New `gin-workflow ship-check` (deterministic, no agent, no network):
  0. Fail when `git status --porcelain --untracked-files=no` is non-empty.
  1. If `project.review_ledger` is on: for each closed track bead of the epic,
     `review-ledger.py validate --in-history` (every track, the last included) and
     `render --check`.
  2. If the ledger is on, reject code changed after the newest approved commit. Per track the
     approved commit is the newest commit, walking back from HEAD, whose source hash equals
     the approval (`review_ledger/git_adapter.find_reviewed_commit` semantics). A path
     changed after it counts as source only if the ledger's own scope predicate
     (`is_path_in_scope`, `included_paths`, excluded/generated paths) says so; spec
     prefixes, `.planning/reviews/` and the legacy `.planning/<bead>/` ledger path never
     count. A merge of the base into the branch after approval fails by design.
  3. With `project.layout: sdd`, `specs lint` and `specs trace`, with the SDD rigor
     semantics (a missing REQ is only a warning at easy).
  4. Pre-push evidence: if a `hooks.pre_push.passed` event matches HEAD sha and current
     `commands_hash`, pass; otherwise run `hooks run pre-push --head` once, which fails
     the check if any command fails.
  Usage: `ship-check --workflow-id <id>` (default as `state`); the epic comes from the
  recorded `orchestration.ready` event and tracks from `bd list --parent <epic> --all`.
  A standalone bead (an epic with no children) is its own single track. It runs before
  ledger cleanup and before the SDD archive commit. It makes no network calls.
- R10a. Termination. `ship-check` records `ship_check.passed` or `ship_check.failed`
  (`{sha, commands_hash, reason}`) in the event store. While the latest `ship_check` event
  for the current HEAD is `failed`, `state` returns `hold` with the printed remedy, never
  `ship` again; a new HEAD allows one retry. After two failed ship-checks for one epic,
  `state` holds until a human clears it. `ship-check` never reopens beads on its own; the
  remedy text names the fix: a failing test, ledger or SDD check -> fix and commit; code
  changed after approval -> reopen the last approved track (the bead with the newest
  approval) with `bd reopen` and run it through review again, which the user or agent
  does explicitly. A flaky or environment failure holds and is not reopened.
- R11. `ship` runs `ship-check` instead of re-running tests, runs no test after the
  merge, and does not require a push (Merge locally, Keep and Discard keep working,
  including repos with no remote). A failing `ship-check` stops ship with its output.
- R12. A commit made after the last track closes returns no gate to unmet. At worst it
  makes the pre-push event stale, which `ship-check` refreshes with one script run.

Team mode (track B)
- R13. When `team.approvals.ship` has roles (the same `has_policy` test `team.py` applies
  today to `verification_passed`), `ship` offers only "push and create a PR" and "keep"
  (no local merge), opens or reuses the PR, and `record ship-approved` checks the PR
  approved at HEAD through the existing host check (`verification_passed` becomes `ship`
  in `team.py:12,319,401,403`). While `has_policy("ship")`, `shipped` is derived only when
  an `ship.approved` event exists at the merged commit or an ancestor. Without roles, and
  in solo mode, nothing changes. `ship-check` itself stays offline.

Review checklist
- R14. The per-track review checklist includes the spec/plan requirements the track
  delivers. Epic-level coverage is left to `specs trace` (SDD) and to R10.

Docs and consistency
- R15. No remaining mention of the removed tokens in R2 (excluding `dist/*`, which is
  regenerated, and old event names in migration notes). Touch every reference found:
  `workflow_core/{router,lifecycle_cli,waivers,schemas,configuration,team,usage_attribution,budget,setup_service,cli}.py`,
  `skills/{verify,ship,workflow,execute,gin-team,gin-sdd,team-setup,gin-debugging,telegram-notify,gin-worktrees,report}`,
  `plan/plan-schema.md`, `references/stage-contract.md`, plugin and marketplace manifests,
  `README.md`, `docs/getting-started.md`, `docs/{concepts,reference,guides,starters,interactive,presentations}`,
  `examples/config.full.yaml`, `agents/qa-agent.md`, `tests/install_smoke_test.sh`, and the tests that reference
  them. The check uses an explicit regex list of removed tokens (`verification_passed`,
  `verification-passed` as a gate, `skills/verify`, `/gin-workflow:verify`, `model_tiers.verify`,
  the `verify` stage in routing); the word `verify` stays valid in `verify_commands`,
  `verify.checks`, `verify-finding`, and `usage_attribution` must still read old events.
  The ledger FSM names in `review_ledger/schema.py` and `cli.py`
  (`verification-passed` etc.) are kept and excluded from the "no remaining mention" check.

## User Stories

### US-1: Finish an epic unattended
As a developer running `/goal` over a whole epic, I want the lifecycle to reach `shipped`
without a verify stage, so that the goal does not loop on a gate it cannot satisfy.

Acceptance criteria:
- `gin-workflow state` with every epic child closed routes to `ship`.
- No lifecycle command asks for `verification_passed` or a waiver.
- A `chore(review)` commit after the last track closes leaves `ship-check` passing.
- After a `ship-check` failure the next `state` call does not route `ship` unchanged.

### US-2: Cheap commits, strict pushes
As a developer, I want fast checks on commit and the full suite on push, so that quality
is enforced without agent tokens or slow commits.

Acceptance criteria:
- A failing lint blocks `git commit`; a failing test blocks `git push`.
- The first failing command's output is shown and later commands do not run.
- With no `verify_commands`, hooks exit 0 with a notice.
- Pushing a tag or deleting a branch runs no tests.

### US-3: Safe hook installation
As a maintainer, I want `hooks install` to leave my existing hooks alone, so that adopting
it never breaks my setup.

Acceptance criteria:
- Re-running `hooks install` changes nothing.
- A foreign `pre-commit`/`pre-push` or a missing `core.hooksPath` directory is reported, not overwritten.
- `setup doctor` flags missing or occupied hooks.
- `git commit --no-verify` is blocked by `safety-check.sh`.

### US-4: Ship without duplicate test runs
As a developer, I want `ship` to stop re-running the suite, so that shipping costs no
extra test time or tokens.

Acceptance criteria:
- `ship` runs no test command itself; at most it runs `hooks run pre-push` once when the
  recorded sha is not HEAD.
- With the ledger on, code changed after the last approved track makes `ship-check` fail.
- A repo with no remote can still Merge locally.

### US-5: Team approval at ship
As a team lead, I want PR approval enforced at ship, so that removing verify does not
remove the reviewer gate.

Acceptance criteria:
- When `team.approvals.ship` has roles, merge is refused until the PR is approved at HEAD,
  and local merge is not offered.
- Solo mode and teams without `ship` roles are unchanged.

## Errors and compatibility

- Hook failure: non-zero exit with the failing command's output; the agent fixes the cause
  and retries. `--no-verify` is blocked (R9).
- Old `verification.passed` events are ignored; their absence never blocks anything.
  Historical usage reports keep their old `verify` rows (attribution reads, not writes).
- A repository whose `core.hooksPath` points at a missing directory (this repo: `.beads/hooks`)
  gets `occupied`/missing guidance from `hooks install` and `setup doctor`, not a silent no-op.
- Hooks outside a versioned `.githooks` are not versioned; a fresh clone needs `/setup` or
  `hooks install`. `ship-check` covers the gap by running `hooks run pre-push --head`
  (lint, typecheck and tests) when no matching event exists.

## Testing

Test first, red then green.
- `ship-check` run with empty stdin and a failing test must fail (not pass).
- Termination: after a failed `ship-check`, same HEAD -> `state` returns `hold`; new HEAD
  allows one retry; a second failure holds for a human; a flaky failure is not reopened.
- Ledger scope: a track with `included_paths`, an out-of-scope commit after approval and a
  clean re-approval does not loop (passes or holds).
- Team: with `ship` roles, `shipped` is not derived without `ship.approved`.
- `hooks run` strips `GIT_*` variables; a dirty tree records no event.
- Router: satisfied `implementation_complete` routes to `ship`; no `verify` stage.
- `hooks run`: first-failure stop, empty config, tag/delete skip, event written on pass.
- `hooks install`: shims created, idempotent, foreign hook kept, `core.hooksPath` honored.
- `ship-check`: stale/absent event reruns pre-push; code after last approval fails;
  `chore(review)` commit passes; ledger and SDD checks gated by config; multi-track
  `--in-history`.
- R3 exit codes; team `ship` approval; `safety-check.sh` blocks `--no-verify` and allows
  `git push -n` and `git commit -m "fix -n flag"`.
- Token-budget, docs-coverage, manifest and packaging tests; full
  `python3 -m unittest discover -s tests` green; `dist/*` regenerated.
