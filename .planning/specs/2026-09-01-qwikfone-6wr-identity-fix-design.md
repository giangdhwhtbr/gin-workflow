# Design Specification: Fix Identity Loss in gin-workflow Review Ledger Checkpoint Refreshes

**Topic**: `qwikfone-6wr` — Review Ledger Identity Preservation  
**Target Repository**: `gin-workflow`  
**Date**: 2026-09-01  
**Status**: Draft for User Review  

---

## 1. Overview & Objective

When refreshing a review-ledger checkpoint on an active task/bead (e.g. after applying code review fixes), `gin-workflow` creates new `source-checkpoint-created` and `review-approved` ledger events. Previously, these refreshed events preserved source tree hashes but omitted the `AcceptanceIdentity` fields (`workflow_id`, `attempt_id`, `task_id`).

Under Schema-2.3 evidence completeness rules, `CompositeEvidenceAuthority` requires `workflow_id` and `attempt_id`. Missing these identity fields flags valid verification evidence as incomplete/legacy, blocking `/ship` unless a manual safety waiver is recorded.

This specification details the technical fix within `gin-workflow` to automatically inherit or explicitly attach `AcceptanceIdentity` during review-ledger checkpoint refreshes and approvals.

---

## 2. Component Boundaries & Data Flow

```
[ Developer / Agent CLI ]
          │
          ▼
[ gin-workflow review-ledger CLI ]
          │
          ▼
[ Identity Resolution Layer ]
  ├── Check explicit flags (workflow_id, attempt_id)
  └── Fallback: Query ledger history for latest complete AcceptanceIdentity
          │
          ▼
[ Event Store / Review Ledger ]
  └── Write source-checkpoint-created & review-approved with full AcceptanceIdentity
          │
          ▼
[ CompositeEvidenceAuthority ]
  └── Schema-2.3 validation passes with complete identity (0 legacy flags)
```

---

## 3. Detailed Changes

### 3.1 Review Ledger Identity Resolution Logic
- Location: `gin-workflow/plugins/gin-workflow/src/scripts/review_ledger/`
- When generating `source-checkpoint-created` or `review-approved` events:
  1. Inspect incoming invocation arguments for explicit `workflow_id`, `attempt_id`, and `task_id`.
  2. If any identity field is missing, search the active task's existing ledger history for the most recent complete `AcceptanceIdentity`.
  3. Merge the resolved identity fields into the new event payload.
  4. Perform strict validation: if `task_id` mismatches between current invocation and ledger history, fail closed with an explicit error.
  5. Preserve legacy ledgers (which genuinely lack historical identity) unchanged without corrupting historical records.

### 3.2 Evidence Authority Compatibility
- Ensure `CompositeEvidenceAuthority` resolves both `repository` and `review` evidence cleanly for refreshed checkpoints without falling back to legacy compatibility modes.

---

## 4. Verification & Testing Plan

1. **Focused Identity Suite**:
   - Run unit tests verifying `AcceptanceIdentity` resolution under explicit, inherited, and mismatched scenarios.
2. **End-to-End Refresh & Re-review Cycle Test**:
   - Execute test sequence: `review` -> record finding -> apply fix -> `checkpoint` refresh (without flags) -> `re-review` -> `verify` -> `approve`.
   - Assert `checkpoint_sha`, `source_tree_hash`, `workflow_id`, and `attempt_id` are present in all emitted events.
   - Validate `CompositeEvidenceAuthority` returns 0 identity completeness errors.
3. **Regression Suite**:
   - Run full `review-ledger` (128 tests) and `workflow-core` (171 tests) test suites.

---

## 5. Risk Assessment & Mitigations

- **Risk**: Overwriting a legacy ledger entry that intentionally lacks identity.
  - *Mitigation*: Fallback inheritance only applies to active task ledgers with prior identity records. Historical no-identity ledgers remain unchanged.
- **Risk**: Mismatched task IDs when inheriting identity.
  - *Mitigation*: Strict equality check on `task_id`; mismatched IDs trigger an explicit error and stop event generation.
