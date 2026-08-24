# Resume In-Progress Work

Use this flow when a session, provider process, or machine ended before the
workflow reached a durable terminal state.

## Prerequisites

- The repository and harness are identified, but a worktree is optional.
- `.agent-workflow/generated/effective-config.yaml` and its provenance are
  available, or setup diagnosis can explain why they are missing.
- Durable task state, approved plan, review ledger, and evidence index can be
  queried through their owning capabilities.
- You know the workflow/task identity if an acceptance attempt already exists.

## Flow

1. Run `$gin-workflow:progress` to read durable task status, dependencies,
   readiness, blockers, review state, and available evidence.
2. Inspect that durable state: determine whether implementation is complete,
   whether review is pending, and whether the acceptance identity/checkpoint
   evidence is coherent. Do not infer progress from a worktree or branch.
3. If review is pending, coordinate the provider-backed review capability and
   obtain terminal approval evidence before invoking `$gin-workflow:workflow`.
   If review is not pending, continue to workflow routing.
4. Invoke `$gin-workflow:workflow` to route exactly one implemented lifecycle
   stage. The router mechanically selects `verify` after
   `implementation_complete` regardless of review state; it does not inspect or
   invent a review gate. For a task that is not implementation-complete, follow
   the returned `execute`, `progress`, or other implemented stage as applicable.
5. Run `$gin-workflow:verify` after routing. The verify wrapper and evidence checks
   fail closed without terminal review approval, so missing review
   evidence remains a verification blocker even when the router selected
   `verify`. Ship only when the durable gates pass.

## State and evidence gates

`progress` consults the Beads/task capability for active, ready, blocked, or
closed state before any routing decision. The generated effective config selects capabilities;
the plan selects approved scope; the review ledger selects findings/lease state;
evidence links worker result, Git checkpoint, terminal review, and verification
under the exact workflow/attempt/task identity. A present branch or worktree is
disposable metadata and is never proof that execution is active or complete.
Stale leases, stale approvals, changed repository snapshots, or missing evidence
hold verification. The router mechanically selects `verify` after
`implementation_complete` regardless of review state; the verify wrapper and
evidence checks fail closed without terminal review approval.

## Realistic example

A laptop lost power after the exporter worker finished but before review. The
next session sees the worktree directory but does not treat that as status.
`progress` reports the Bead open and review-pending, while the evidence query
finds the worker result and checkpoint but no terminal review approval. The
coordinator invokes the review capability before workflow; the reviewer acquires
a fresh lease, verifies the exact snapshot, and records approval. After that
review evidence is durable, invoking `workflow` selects `verify`, and the verify
wrapper can pass against the coherent identity and evidence before ship.

## Common failures

- Generated config is absent or incompatible: setup is required before routing.
- The task is blocked by an unmet dependency or provider outage: execution is
  not retried by guessing from local files.
- Review lease is active for another actor, expired with a revision mismatch, or
  the source scope changed: review cannot write with the old lease/checkpoint.
- Evidence references another attempt, has empty hashes, or lacks passed
  verification: completeness stays false.

## Safe recovery

Keep the durable task open and use progress/workflow again after resolving the
reported blocker. Use setup's approved migration/rollback for configuration;
use the task capability for dependency/readiness changes; use review capability
for lease renewal/takeover; create a fresh checkpoint and evidence attempt when
source identity changed. If scope expands, return to discuss and plan. Do not
remove a worktree to mark completion, edit runtime cache files, or bypass the
provider contract with manual backend commands.
