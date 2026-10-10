# Drop the verify stage; enforce quality in git hooks and a mechanical ship-check

Status: draft for user review (revision 2, after independent Opus review).

## Goal and scope

The `verify` stage makes the agent re-run the whole quality suite, validate every
review ledger and re-read the spec line by line. Its evidence is pinned to the branch
tip, and its gate (`verification_passed`) is a Safety gate that only a human can waive.
In an autonomous `/goal` over a whole epic, any later commit (even a `chore(review)`
one) returns the gate to unmet, so the agent re-verifies in a loop and burns tokens.
`ship` then re-runs the tests twice more (before and after merge).

Goal: remove the stage and gate; move mechanical checks into git hooks and one
deterministic `ship-check` command, neither of which spends agent tokens. A goal over an
epic must reach `shipped` unattended.

Delivered as three tracks so the safe additions land first:
- **A. Hooks:** `gin-workflow hooks install|run`, `setup doctor` hook check, blocking
  `--no-verify` in `safety-check.sh`. Additive only.
- **B. Remove verify:** stage, gate, `ship-check`, leaner `ship`, docs, tests, `dist/*`.
- **C. Team mode:** move PR approval from the verify gate to `ship`.

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
  `verification_passed` or `team.approvals.verification_passed` loads with a deprecation
  warning (schemas accept the key, ignore it).

Hooks (track A)
- R4. `gin-workflow hooks install` reuses `team_init.active_hooks_dir()` and
  `install_hook()`: writes marker-tagged `pre-commit` and `pre-push` shims that call
  `gin-workflow hooks run <hook>`, is idempotent, and never overwrites a hook it did not
  write (reports `occupied` and prints how to chain the call). It honors an existing
  `core.hooksPath`. `/setup` calls it. If `gin-workflow` is not on PATH the shim fails
  closed with an install message. Hooks apply in linked worktrees (shared hooks dir).
- R5. `setup doctor` reports hooks that are missing, occupied, or not on the active hooks
  path.
- R6. `hooks run pre-commit` runs the `lint` and `typecheck` entries of
  `project.verify_commands`. It operates on the working tree and says so; it does not
  isolate staged content.
- R7. `hooks run pre-push` reads the pushed refs from stdin, skips deletes and tags, and
  runs only when a pushed local sha is the checked-out HEAD. It runs the remaining
  `verify_commands` allowed by rigor (easy: test; standard: + build; strict: + e2e;
  per-package `verify.checks` are honored in a monorepo). On success it records a local
  event `hooks.pre_push.passed` with the HEAD sha.
- R8. Commands run in order and stop at the first failure, printing that command's output
  and exiting non-zero. Empty `verify_commands` prints a notice and exits 0. The hook
  itself never calls an agent or retries; the configured commands may use whatever
  resources they need (e.g. e2e services).
- R9. `scripts/safety-check.sh` blocks `git commit/push --no-verify`, `-n`, and
  `-c core.hooksPath=`.

Ship (track B)
- R10. New `gin-workflow ship-check` (deterministic, no agent, no network):
  1. If `project.review_ledger` is on: for each closed track bead of the epic being
     shipped, `review-ledger.py validate` (`--in-history` for every track but the last on
     the branch) and `render --check`.
  2. Reject code changed after the last approved track: `git log -m --name-only` since the
     last approved commit may touch only non-source prefixes (the existing spec
     prefixes plus `.planning/reviews/`).
  3. With `project.layout: sdd`, `specs lint` and `specs trace`.
  4. Pre-push evidence: if a `hooks.pre_push.passed` event has sha equal to HEAD, pass;
     otherwise run `hooks run pre-push` once.
  The epic is resolved from the branch being shipped; it runs before ledger cleanup.
- R11. `ship` runs `ship-check` instead of re-running tests, runs no test after the
  merge, and does not require a push (Merge locally, Keep and Discard keep working,
  including repos with no remote). A failing `ship-check` stops ship with its output.
- R12. A commit made after the last track closes returns no gate to unmet. At worst it
  makes the pre-push event stale, which `ship-check` refreshes with one script run.

Team mode (track C)
- R13. With `team.enabled`, `ship` requires the PR approved at HEAD, reusing the existing
  `team.authorize_record` / host check from `team.py`. The config key becomes
  `team.approvals.ship`; the old key warns as deprecated. Solo mode is unchanged.

Review checklist
- R14. The per-track review checklist includes the spec/plan requirements the track
  delivers. Epic-level coverage is left to `specs trace` (SDD) and to R10.

Docs and consistency
- R15. No remaining mention of the removed tokens in R2 (excluding `dist/*`, which is
  regenerated, and old event names in migration notes). Touch every reference found:
  `workflow_core/{router,lifecycle_cli,waivers,schemas,configuration,team,usage_attribution,budget,setup_service,cli}.py`,
  `skills/{verify,ship,workflow,execute,gin-team,gin-sdd,team-setup,gin-debugging,telegram-notify,gin-worktrees,report}`,
  `plan/plan-schema.md`, `references/stage-contract.md`, plugin and marketplace manifests,
  `README.md`, `docs/{concepts,reference,guides,starters,interactive,presentations}`,
  and the tests that reference them.

## User Stories

### US-1: Finish an epic unattended
As a developer running `/goal` over a whole epic, I want the lifecycle to reach `shipped`
without a verify stage, so that the goal does not loop on a gate it cannot satisfy.

Acceptance criteria:
- `gin-workflow state` with every epic child closed routes to `ship`.
- No lifecycle command asks for `verification_passed` or a waiver.
- A `chore(review)` commit after the last track closes leaves `ship-check` passing.

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
- A foreign `pre-commit`/`pre-push` or an unwritable `core.hooksPath` is reported, not overwritten.
- `setup doctor` flags missing or occupied hooks.
- `git commit --no-verify` is blocked by `safety-check.sh`.

### US-4: Ship without duplicate test runs
As a developer, I want `ship` to stop re-running the suite, so that shipping costs no
extra test time or tokens.

Acceptance criteria:
- `ship` runs no test command itself; at most it runs `hooks run pre-push` once when the
  recorded sha is not HEAD.
- Code changed after the last approved track makes `ship-check` fail.
- A repo with no remote can still Merge locally.

### US-5: Team approval at ship
As a team lead, I want PR approval enforced at ship, so that removing verify does not
remove the reviewer gate.

Acceptance criteria:
- With `team.enabled`, `ship` is refused until the PR is approved at HEAD.
- Solo mode behavior is unchanged.

## Errors and compatibility

- Hook failure: non-zero exit with the failing command's output; the agent fixes the cause
  and retries. `--no-verify` is blocked (R9).
- Old `verification.passed` events are ignored; their absence never blocks anything.
  Historical usage reports keep their old `verify` rows (attribution reads, not writes).
- A repository whose `core.hooksPath` points at a missing directory (this repo: `.beads/hooks`)
  gets `occupied`/missing guidance from `hooks install` and `setup doctor`, not a silent no-op.
- Hooks are not versioned; a fresh clone needs `/setup` or `hooks install`. `ship-check`
  covers the gap by re-running `pre-push` when no matching event exists.

## Testing

Test first, red then green.
- Router: satisfied `implementation_complete` routes to `ship`; no `verify` stage.
- `hooks run`: first-failure stop, empty config, tag/delete skip, event written on pass.
- `hooks install`: shims created, idempotent, foreign hook kept, `core.hooksPath` honored.
- `ship-check`: stale/absent event reruns pre-push; code after last approval fails;
  `chore(review)` commit passes; ledger and SDD checks gated by config; multi-track
  `--in-history`.
- R3 exit codes; team `ship` approval; `safety-check.sh` blocks `--no-verify`.
- Token-budget, docs-coverage, manifest and packaging tests; full
  `python3 -m unittest discover -s tests` green; `dist/*` regenerated.
