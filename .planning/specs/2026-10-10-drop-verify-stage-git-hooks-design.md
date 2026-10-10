# Drop the verify stage; enforce quality in git hooks

Status: draft for user review (revision 5, trimmed after over-engineering review).

## Goal and scope

The `verify` stage makes the agent re-run the whole quality suite, validate every review
ledger and re-read the spec line by line. Its evidence is pinned to the branch tip and its
gate (`verification_passed`) is a Safety gate only a human can waive. In an autonomous
`/goal` over an epic, any later commit (even `chore(review)`) returns the gate to unmet, so
the agent re-verifies in a loop and burns tokens. `ship` then re-runs the tests twice more.

Goal: remove the stage and gate; the mechanical checks move into git hooks, which spend no
agent tokens. A goal over an epic reaches `ship` and presents its options without looping
(the merge still needs the user's explicit approval). CI/CD stays the backstop for large
projects; the plugin does not read CI results.

Two tracks:
- **A. Hooks** (additive, shippable alone): `hooks install|run`, `setup doctor` check,
  `--no-verify` block.
- **B. Remove verify:** stage and gate removal, leaner `ship`, team approval moved to
  `ship`, docs, tests, `dist/*`.

Out of scope: CI integration; a `verify.mode` key; migrating old events; review-ledger
logic and its FSM actions, `verify.checks`, `verify-bundle` (kept); a `ship-check` command,
hook-run evidence events, or any new state machine; bug `gin-workflow-il4`.

## Requirements

Stage and gate (B)
- R1. Stages are `discuss, plan, orchestrate, execute, ship`. The router goes from satisfied
  `implementation_complete` straight to `ship`.
- R2. Removed: the `verify` stage, `skills/verify`, `/gin-workflow:verify`, the
  `verification_passed` gate and its Safety waiver, `record verification-passed`, the
  `verification.passed` event, `model_tiers.verify`, and the `verify` usage-attribution
  stage. Old events stay in the store and are ignored (usage attribution still reads them).
  Kept: `verify_commands`, `verify.checks`, every review-ledger verification action.
- R3. `record verification-passed` and `unblock --gate verification_passed` exit 2 with a
  message pointing to the hooks. A config still naming `verification_passed` loads with a
  deprecation warning; `team.approvals.verification_passed` maps to `team.approvals.ship`
  with a warning. `examples/config.full.yaml` is updated.

Hooks (A)
- R4. `gin-workflow hooks install` generalises `team_init.install_hook()` (today hard-coded
  to `commit-msg`) and reuses `active_hooks_dir()`: writes marker-tagged `pre-commit` and
  `pre-push` shims calling `gin-workflow hooks run <hook>`; idempotent; never overwrites a
  hook it did not write (reports `occupied` and prints how to chain the call); honors an
  existing `core.hooksPath`; shims written into the versioned `.githooks` are committed by
  `/setup`. A `core.hooksPath` directory that does not exist is reported, not created
  (this intentionally changes the current `commit-msg` install). `/setup` calls it. If
  `gin-workflow` is not on PATH the shim fails closed with an install message.
- R5. `setup doctor` reports hooks that are missing, occupied, or not on the active hooks
  path (this repo's `core.hooksPath` points at a missing `.beads/hooks`).
- R6. `hooks run pre-commit` runs the `lint` and `typecheck` entries of
  `project.verify_commands` on the working tree.
- R7. `hooks run pre-push` reads pushed refs from stdin, skips deletes and tags, and tests
  only when a pushed local sha is the checked-out HEAD (otherwise it prints that nothing
  was tested). It runs the remaining `verify_commands` allowed by rigor (easy: test;
  standard: + build; strict: + e2e); per-package `verify.checks` run in the package
  directory.
- R8. Commands run in order and stop at the first failure, printing that command's output
  and exiting non-zero. Empty `verify_commands` prints a notice and exits 0. `hooks run`
  removes `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_PREFIX`,
  `GIT_OBJECT_DIRECTORY`, `GIT_COMMON_DIR` before running the commands. The hook never
  calls an agent or retries.
- R9. `scripts/safety-check.sh` blocks `--no-verify` on `git commit`, `push` and `merge`
  (one regex, best-effort).

Ship (B)
- R10. `ship` no longer runs tests before or after the merge, and does not require a push
  (Merge locally, Keep, Discard, and repos with no remote keep working). Instead, before
  presenting options it runs as plain steps: with `project.review_ledger` on,
  `review-ledger.py validate --in-history` and `render --check` for each closed track of
  the epic, and rejects changes after the newest approved commit unless they only touch
  spec artifacts or `.planning/reviews/` (the existing allowed prefixes plus that one); with
  `project.layout: sdd`, `specs lint` and `specs trace`. Any failure stops `ship` and
  reports to the user, as `execute` does on a blocker; ship does not retry.
- R11. A commit made after the last track closes returns no gate to unmet.
- R12. When `team.approvals.ship` has roles (same `has_policy` test `team.py` applies today to
  `verification_passed`), `ship` offers only "push and create a PR" and "keep" and requires
  the PR approved at HEAD before merge, via the existing host check (`verification_passed`
  becomes `ship` in `team.py`). Without roles, and in solo mode, nothing changes.
- R13. The per-track review checklist includes the spec/plan requirements the track
  delivers.

Docs and consistency
- R14. No remaining mention of the removed tokens (`verification_passed`,
  `verification-passed` as a gate, `skills/verify`, `/gin-workflow:verify`,
  `model_tiers.verify`, the `verify` routing stage), excluding `dist/*` (regenerated) and the
  kept ledger FSM names. The word `verify` stays valid in `verify_commands`, `verify.checks`,
  `verify-finding`. Files to touch: `workflow_core/{router,lifecycle_cli,waivers,schemas,
  configuration,team,usage_attribution,budget,setup_service,cli}.py`, `skills/{verify,ship,
  workflow,execute,gin-team,gin-sdd,team-setup,gin-debugging,telegram-notify,gin-worktrees,
  report}`, `agents/qa-agent.md`, `plan/plan-schema.md`, `references/stage-contract.md`,
  plugin and marketplace manifests, `README.md`, `docs/getting-started.md`, `docs/{concepts,
  reference,guides,starters,interactive,presentations}`, `examples/config.full.yaml`,
  `tests/install_smoke_test.sh`, and the tests that reference them.

## User Stories

### US-1: Finish an epic unattended
As a developer running `/goal` over a whole epic, I want the lifecycle to reach `ship`
without a verify stage, so that the goal does not loop on a gate it cannot satisfy.

Acceptance criteria:
- `gin-workflow state` with every epic child closed routes to `ship`.
- No lifecycle command asks for `verification_passed` or a waiver.
- A `chore(review)` commit after the last track closes does not block `ship`.

### US-2: Cheap commits, strict pushes
As a developer, I want fast checks on commit and the full suite on push, so that quality is
enforced without agent tokens or slow commits.

Acceptance criteria:
- A failing lint blocks `git commit`; a failing test blocks `git push`.
- The first failing command's output is shown and later commands do not run.
- With no `verify_commands`, hooks exit 0 with a notice.
- Pushing a tag or deleting a branch runs no tests.

### US-3: Safe hook installation
As a maintainer, I want `hooks install` to leave my existing hooks alone, so that adopting it
never breaks my setup.

Acceptance criteria:
- Re-running `hooks install` changes nothing.
- A foreign `pre-commit`/`pre-push` or a missing `core.hooksPath` directory is reported, not
  overwritten or created.
- `setup doctor` flags missing or occupied hooks.
- `git commit --no-verify` is blocked by `safety-check.sh`.

### US-4: Ship without duplicate test runs
As a developer, I want `ship` to stop re-running the suite, so that shipping costs no extra
test time or tokens.

Acceptance criteria:
- `ship` runs no test command.
- With the ledger on, code changed after the last approved track stops `ship` with a report.
- A repo with no remote can still Merge locally.

### US-5: Team approval at ship
As a team lead, I want PR approval enforced at ship, so that removing verify does not remove
the reviewer gate.

Acceptance criteria:
- When `team.approvals.ship` has roles, merge is refused until the PR is approved at HEAD,
  and local merge is not offered.
- Solo mode and teams without `ship` roles are unchanged.

## Errors and compatibility

- Hook failure: non-zero exit with the failing command's output; fix and retry.
- Old `verification.passed` events are ignored; their absence never blocks anything.
- Hooks outside a versioned `.githooks` are not versioned; a fresh clone needs `/setup` or
  `hooks install`. Accepted: nothing at ship proves the hooks ran; CI is the backstop.
- A failing ship check stops and reports; it records no state and routes nowhere.

## Testing

Test first, red then green.
- Router: satisfied `implementation_complete` routes to `ship`; no `verify` stage.
- `hooks run`: first-failure stop, empty config, tag/delete skip, `GIT_*` stripped.
- `hooks install`: shims created, idempotent, foreign hook kept, `core.hooksPath` honored,
  missing directory reported.
- R3 exit codes and config mapping; team `ship` approval; `safety-check.sh` blocks
  `--no-verify`.
- Ship skill text: no test-run step; ledger check allows `.planning/reviews/` commits and
  rejects other post-approval changes.
- Token-budget, docs-coverage, manifest and packaging tests; full
  `python3 -m unittest discover -s tests` green; `dist/*` regenerated.
