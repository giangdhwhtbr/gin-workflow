# Drop the verify stage; enforce quality in git hooks

Status: draft for user review.

## Goal and scope

The `verify` stage makes the agent re-run the whole quality suite, validate every
review ledger and re-read the spec line by line. Its evidence is pinned to the
branch tip, and its gate (`verification_passed`) is a Safety gate that only a human
can waive. In an autonomous `/goal` over a whole epic, any later commit (even a
`chore(review)` one) returns the gate to unmet, so the agent re-verifies in a loop and
burns tokens. `ship` then re-runs the tests twice more (before and after merge).

Goal: remove the stage and gate, and move the mechanical checks into git hooks that
run without an agent. A goal over an epic must be able to reach `shipped` unattended.

In scope: `gin-workflow hooks install|run`, removal of the `verify` stage and the
`verification_passed` gate, a leaner `ship`, docs, tests, regenerated `dist/*`.

Out of scope: reading CI/CD results or calling `gh`; new config keys or a
`verify.mode`; migrating old `verification.passed` events; changes to the review
ledger logic; bug `gin-workflow-il4`.

## Requirements

- R1. Lifecycle stages are `discuss, plan, orchestrate, execute, ship`. The router
  goes from satisfied `implementation_complete` straight to `ship`.
- R2. `verification_passed`, the `verify` stage, `verification.passed` events and the
  Safety waiver for that gate are removed. Old events are ignored.
- R3. `gin-workflow hooks install` writes `pre-commit` and `pre-push` hooks that call
  `gin-workflow hooks run <hook>`. It is idempotent, never overwrites a hook it did
  not write, and prints how to wire the call when `core.hooksPath` or another tool
  manages hooks. `/setup` calls it.
- R4. `hooks run pre-commit` runs the `lint` and `typecheck` entries of
  `project.verify_commands`. `hooks run pre-push` runs the remaining entries allowed
  by the project rigor (easy: test; standard: + build; strict: + e2e) and
  `review-ledger.py validate` for the closed track beads of the current epic.
- R5. Commands run in order and stop at the first failure, printing that command's
  output and exiting non-zero. Empty `verify_commands` prints a notice and exits 0.
  Hooks never call an agent or the network, and never retry.
- R6. `ship` runs no tests. It requires `implementation_complete` and a pushed branch
  (upstream equals HEAD, so `pre-push` ran). Pushing the merged base branch re-runs
  `pre-push`.
- R7. `record verification-passed` and `unblock --gate verification_passed` fail with
  a clear message pointing to the hooks (exit 2).
- R8. Spec/plan line-by-line checking moves into the per-track review checklist.
- R9. Docs, skills, `stage-contract.md` and tests no longer mention the verify stage;
  `dist/*` is regenerated, not hand-edited.

## User Stories

### US-1: Finish an epic unattended
As a developer running `/goal` over a whole epic, I want the lifecycle to reach
`shipped` without a verify stage, so that the goal does not loop on a gate it cannot
satisfy.

Acceptance criteria:
- `gin-workflow state` with every epic child closed routes to `ship`.
- No lifecycle command asks for `verification_passed` or a waiver.
- A commit made after the last track closes does not return any gate to unmet.

### US-2: Cheap commits, strict pushes
As a developer, I want fast checks on commit and the full suite on push, so that
quality is enforced without agent tokens or slow commits.

Acceptance criteria:
- A failing lint blocks `git commit`; a failing test blocks `git push`.
- The first failing command's output is shown and later commands do not run.
- With no `verify_commands`, hooks exit 0 with a notice.

### US-3: Safe hook installation
As a maintainer, I want `hooks install` to leave my existing hooks alone, so that
adopting it never breaks my setup.

Acceptance criteria:
- Re-running `hooks install` changes nothing.
- A pre-existing foreign hook is not overwritten; instructions are printed instead.
- `/setup` installs the hooks in a repository that has none.

### US-4: Ship without duplicate test runs
As a developer, I want `ship` to stop re-running the suite, so that shipping costs no
extra test time or tokens.

Acceptance criteria:
- `ship` runs no test command before or after the merge.
- `ship` refuses when the branch is not pushed or HEAD differs from upstream.
- Pushing the merged base branch triggers `pre-push`.

## Errors and compatibility

- Hook failure: non-zero exit with the failing command's output; the agent fixes the
  cause and retries. `--no-verify` stays forbidden.
- Ledger invalid in `pre-push`: fail naming the bead; only closed track beads of the
  current epic are checked, so unrelated branches are unaffected.
- Old `verification.passed` events stay in the store and are ignored. A config that
  still lists `verification_passed` loads with a deprecation warning.
- Existing skills or scripts calling `record verification-passed` get a clear error,
  not a silent success.
- This repository has no hooks or test CI today; `/setup` must be re-run here for the
  hooks to take effect.

## Testing

Test first, red then green.
- Router: satisfied `implementation_complete` routes to `ship`; no `verify` stage.
- `hooks run`: stops at the first failing command; empty config exits 0; invalid
  ledger fails `pre-push`; lint/typecheck only in `pre-commit`.
- `hooks install`: creates both hooks, idempotent, preserves foreign hooks.
- `record verification-passed` and `unblock --gate verification_passed` exit 2.
- `ship` skill text has no test-run step; docs coverage and token budget tests pass.
- Full `python3 -m unittest discover -s tests` is green.
