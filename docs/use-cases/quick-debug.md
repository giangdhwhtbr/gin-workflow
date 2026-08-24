# Quick Debug: Bounded Defect

Use this flow for a small, reproducible defect where diagnosis and the fix can
remain within a narrow approved scope.

## Prerequisites

- A concrete symptom, reproduction, expected behavior, and affected repository
  path are available.
- Setup and generated effective config are valid.
- The suspected scope and a focused regression command are bounded.
- The user can confirm the minimal change and its acceptance criteria.

## Flow

1. Start a bounded requirement discussion (the `discuss` skill) and confirm the
   symptom, expected result, non-goals, and scope.
2. Diagnose systematically with repository evidence and the smallest useful
   reproduction; stop if the cause is not isolated.
3. Create a minimal approved plan with `$gin-workflow:plan`, one focused track,
   and an explicit regression test.
4. Run `$gin-workflow:orchestrate` to create the Bead, validate assignment,
   dependency, and readiness state, and establish `orchestration_ready` before
   any implementation mutation.
5. Execute the approved change through `$gin-workflow:execute` with bounded
   context and the configured provider route.
6. Run the focused regression plus directly affected checks.
7. Request review, then run `$gin-workflow:verify`; ship only after review,
   evidence, and handoff gates pass.
8. If diagnosis expands the scope, pause and return to discuss/plan instead of
   silently broadening the patch.

## State and evidence gates

Requirement confirmation and plan approval precede implementation. The worker
result must match the task/attempt identity and approved file scope. The focused
regression is recorded as worker evidence; review approval must be terminal and
verification must pass against the same repository checkpoint. Router holds when
capability/config/approval/evidence gates are missing. A worktree, local cache,
or passing ad-hoc command alone cannot close the task.

## Realistic example

A CSV download returns HTTP 200 with an empty body only when a filter is active.
Diagnosis traces the serializer and reproduces the missing stream flush. The
minimal plan changes the serializer and adds one regression test. Orchestration
creates the Bead, reports it ready with `orchestration_ready`, and only then does
execute run that track. The regression passes, review confirms no filter or API
scope expansion, and verify records the same checkpoint identity before ship.

## Common failures

- The symptom is not reproducible or has multiple plausible causes: diagnosis is
  unbounded and the plan must not be guessed.
- The proposed fix touches files outside approved scope: stop and re-discuss.
- Focused regression passes but identity/checkpoint/review evidence is missing:
  verification remains blocked.
- Provider health, lease, task preflight, or approval fails: the mutation is not
  retried through a bypass.

## Safe recovery

Capture the reproduction and blocker, keep the task open, and return to discuss
when requirements or scope change. Use configured same-tier routing for provider
failure, the review capability for lease conflicts, and the evidence/verify
capabilities for stale or mismatched records. Expand regression coverage only
through an approved plan update. Never edit a cache, write an empty hash, or
bypass task-tracking capability with an unmanaged backend invocation.
