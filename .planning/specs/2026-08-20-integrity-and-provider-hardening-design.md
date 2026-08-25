# Integrity and Provider Hardening Design

Date: 2026-08-20
Status: Confirmed requirement

## Objective

Harden Gin Workflow so review approval, worker results, verification evidence, provider routing, and durable task closure all refer to one replayable source snapshot and workflow attempt. Resolve the reported review-ledger, Antigravity, evidence, assignment-validation, and task-provider defects as one versioned program without editing installed plugin caches.

## Scope

This program covers:

1. Persisting real review scope and repository tree hashes at approval.
2. Supporting Antigravity CLIs that use a provider-default model and do not expose `--model`.
3. Making `start-review` acquire or renew its reviewer lease atomically.
4. Extending ledger initialization with repository paths, source scope, and automatic snapshot hashing.
5. Checkpointing ordinary in-scope untracked source without changing the user's branch or index, including explicit nested-repository and submodule handling.
6. Correlating test, repository, review, and worker evidence with the current workflow attempt and source identity.
7. Validating every plan task's provider role and reasoning tier before durable orchestration mutations.
8. Extending the task-provider contract with notes, acceptance criteria, closure reason, dependency readiness, preflight, and guarded sync operations.
9. Validating worker test semantics, exit codes, timestamps, workspace identity, and tree hashes.
10. Detecting `bd`/`br` compatibility and backend drift before task mutation, with a safe explicit recovery path.
11. Removing installed/generated harness output from source control and documenting practical workflow use cases.

Direct modification or deletion of files under user plugin caches or other installed locations is out of scope. Commit and push are also out of scope without separate authorization.

## Architectural Identity

The shared acceptance identity is:

`workflow_id + attempt_id + task_id + repository_id + source_scope_hash + source_tree_hash`

Multi-repository work has one repository identity entry per declared repository. Every test record, repository checkpoint, terminal review approval, evidence record, and task-closure decision must match the appropriate acceptance identity. A scope or source change creates a new identity and invalidates approval and completeness derived from the previous identity.

Ownership remains separated:

- The approved plan owns decomposition, source scope, and validation intent.
- The review ledger owns review scope, snapshot references, leases, findings, and approval events.
- Git checkpoint objects and dedicated Gin review refs own replayable source snapshots.
- The evidence provider owns correlated acceptance evidence.
- The task-tracking provider, backed by Beads in this repository, owns task identity, dependencies, readiness, progress, and closure.

## Review Initialization and Source Checkpointing

`review-ledger init` accepts repository ID, repository role, repository path, included paths, excluded artifact paths, generated artifact paths, base ref or SHA, and an optional review ref. It canonicalizes paths relative to each repository root, rejects traversal and ambiguous nested-repository ownership, computes the source-scope hash, and initializes repository identity records.

Checkpointing uses a temporary Git index. It starts from the selected base tree, overlays all in-scope working-tree changes, includes ordinary in-scope untracked source, excludes declared generated and artifact paths, and writes an immutable tree and checkpoint commit behind a dedicated Gin review ref. It does not switch branches, modify the user's index, or add a commit to the current branch.

Submodules are represented by their gitlink commit. A nested repository that must be reviewed independently is declared as a separate repository record. Repository tree hashes are computed from checkpoint objects, not from mutable working-tree state.

## Approval Integrity

Before recording `review-approved`, the review provider reloads the ledger and checkpoint refs, recomputes the canonical source-scope hash and every repository tree hash, and verifies that they match the reviewed snapshots. The approval event persists:

- source-scope hash;
- repository IDs and roles;
- checkpoint refs and commit SHAs;
- per-repository source tree hashes;
- terminal finding IDs;
- workflow, attempt, task, reviewer, and event identity.

Missing, malformed, stale, or mismatched identity fails closed. Legacy ledgers remain readable, but an approval lacking the required identity cannot satisfy current verification until a new checkpoint and review are completed.

## Review Lease and Transaction Semantics

All review-ledger mutation goes through one lock-protected transactional service shared by the CLI and provider facade. A batch validates every transition before atomically replacing the JSON ledger and Markdown projection; partial batch state is never visible.

`start-review` performs lease and state transition atomically:

- with no active lease, it acquires a lease and starts review;
- a retry by the same reviewer renews the lease idempotently;
- another reviewer holding a live lease causes rejection with no mutation;
- an expired lease produces a takeover event before a new lease is acquired;
- the result returns lease ID, expiry, and ledger revision.

Subsequent writes require matching lease ID, actor, and expected revision. Lease TTL is configurable with the current ten-minute behavior as the default. A scope change remains a protected action, invalidates prior checkpoints, approvals, and acceptance evidence, and requires a new attempt identity and review cycle.

## Worker Result and Evidence Provenance

Worker results use a versioned contract. Each reported test contains sanitized structured argv, exit code, start and finish timestamps, workspace ID, repository ID, workflow attempt ID, and source tree hash. Portable evidence does not include absolute local paths, environment dumps, credentials, or secret values. A test is successful only when its schema is valid and its exit code is zero.

The overall worker result must match the request's task, workflow attempt, workspace, and source identity. Shape or identity mismatches return `invalid_result_contract`, and no acceptance evidence is recorded from an invalid result.

Evidence completeness selects one coherent acceptance set rather than independently finding any successful record in each category:

- test evidence passed on the selected tree hash;
- repository evidence identifies the same checkpoint, scope hash, and tree hash;
- review evidence references the terminal approval event for that checkpoint and hashes;
- all records share workflow, attempt, task, and repository identity;
- event times follow a valid attempt, test/checkpoint, approval, and verification sequence.

Older evidence remains queryable for audit but cannot be mixed with current evidence to satisfy completeness.

## Plan Validation and Provider Routing

Plans remain portable and declare only a logical provider role and reasoning tier per task. Planning validates every task against the portable configured roles and supported logical tiers, reports all task-specific errors, and rejects an invalid plan.

Before task creation, orchestration resolves every task against machine-local provider mappings and current capabilities. Resolution is stage-atomic: any unresolved assignment stops orchestration before any durable task mutation.

An Antigravity CLI without `--model` is degraded but available. It may be selected only when machine-local configuration explicitly maps the relevant tier to `provider_default`. The invocation omits `--model`, and runtime evidence records the requested tier, provider-default selection, unavailable explicit selection, and an unknown concrete model unless the CLI reports it. A route configured with a concrete model is ineligible when the CLI cannot select it; normal same-tier fallback applies.

## Task-Tracking Provider Contract

The provider-neutral task contract adds:

- notes and acceptance criteria on create and update;
- explicit close with closure reason and acceptance evidence reference;
- dependency add, remove, and query operations;
- dependency-derived readiness and blocker reporting;
- read-only preflight diagnostics;
- explicit sync planning and execution with dry-run support.

Preflight runs before every mutation and identifies the installed task CLI family (`bd` or `br`), version, supported operations, backend health, and detectable data drift. An unsupported or unhealthy state fails before mutation with actionable recovery guidance.

Adapters use only capabilities proven for the installed CLI. They do not silently translate an unsupported operation or repair repository data. Sync that moves data is explicit and requires a fresh `data_move` approval and matching durable audit evidence. Task closure is allowed only when acceptance evidence is complete and the closure reason is persisted.

## Compatibility and Migration

Readers remain compatible with legacy ledger and evidence schemas. New writes use a versioned schema containing the shared identity. Legacy records that lack required integrity fields are marked insufficient for approval or completeness rather than being guessed or silently upgraded.

Schema, workflow, setup-CLI, plugin, and installer compatibility channels are updated together where required. Migration is explicit, previewable, backed up according to setup policy, and tested. It never rewrites user plugin caches or performs implicit task-provider recovery.

## Repository and Installation Boundary

The repository source of truth is the plugin source under `plugins/gin-workflow/src/`, project documentation, tests, marketplace metadata, and installation scripts.

Root project-installation outputs `/.codex/`, `/.claude/`, and `/.agents/` are removed from tracking and ignored. `plugins/*/dist/` remains ignored. `.claude-plugin/` marketplace metadata remains tracked.

`.agent-workflow/config.yaml` remains tracked as portable repository configuration. `.agent-workflow/generated/`, `.agent-workflow/runtime/`, `.agent-workflow/backups/`, and `.agent-workflow/providers.local.yaml` are ignored and removed from tracking without deleting the local copies. This program does not change `.beads/` or `.planning/` ownership.

Installers build and install from repository source. Verification uses temporary installation destinations. No implementation step directly edits or removes content in `~/.codex/plugins/cache`, other user-level plugin installations, or equivalent harness-managed directories.

## Documentation and Use Cases

Canonical lifecycle, provider, evidence, setup, and handoff documents are updated with the new contracts. Packaged plugin reference sources that reproduce canonical policy are updated and checked for drift; installed cache copies are never edited directly.

`README.md` gains a concise workflow overview and a Common Use Cases index. Detailed guides live under `docs/use-cases/`:

- `README.md`: scenario-selection table and prerequisites;
- `large-task.md`: discovery, decomposition, planning, orchestration, execution, verification, and shipping;
- `resume-in-progress.md`: recovering durable context, using progress/workflow routing, and handling ready, blocked, or review-pending work;
- `quick-debug.md`: bounded defect confirmation, systematic diagnosis, minimal planning, implementation, tests, and verification.

Each guide includes when to use the flow, prerequisites, commands or skills, state and evidence gates, a realistic example, common failures, and safe recovery. README, canonical docs, and installed references must not contradict each other.

## Error Handling

Integrity and compatibility errors fail closed before protected or durable mutation. Provider unavailability is distinct from invalid input or integrity mismatch. Diagnostics name the task, repository, expected identity, observed identity, failed capability, and safe next action without leaking secrets or private reasoning.

Atomic operations use stable locks and idempotency identities. Crashes cannot expose partially updated ledger projections, partially created orchestration state, or evidence records derived from rejected worker results.

## Verification Strategy

Verification includes:

- unit tests for canonical hashes, identity matching, schema readers, result validation, routing policy, and task contracts;
- ledger integration tests for initialization, untracked source, temporary-index checkpoints, submodule gitlinks, nested repositories, scope changes, approval replay, and legacy behavior;
- concurrency tests for lease acquire, renew, conflict, expiry takeover, revision checks, and atomic batch failure;
- evidence tests proving stale or cross-attempt records cannot satisfy completeness;
- provider tests for Antigravity explicit-model and provider-default modes;
- plan/orchestration tests proving all assignments validate before task mutation;
- `bd` and `br` capability fixtures for preflight, drift, readiness, closure, dry-run sync, and safe failures;
- Unix and PowerShell installer smoke tests using temporary destinations;
- repository checks proving generated install/runtime directories are ignored while source, docs, metadata, and installers remain tracked;
- documentation link and canonical-reference drift checks where supported.

## Acceptance Criteria

The program is accepted when:

1. Every new review approval contains a real canonical scope hash and replayable repository checkpoint/tree hashes.
2. Approval and verification reject missing or mismatched source identity.
3. `start-review` provides the documented atomic lease ownership guarantee.
4. Ordinary in-scope untracked source can be checkpointed without modifying the user's branch or index.
5. Antigravity provider-default execution works only when explicitly allowed and records its limitation.
6. Evidence completeness cannot be satisfied by stale, cross-attempt, or cross-tree records.
7. Invalid test semantics, exit codes, timestamps, workspace identity, or tree identity are rejected at the worker boundary.
8. Invalid roles or tiers cannot survive planning, and unresolved routes cannot cause partial orchestration.
9. Workers can persist notes and acceptance evidence, and task readiness/closure operate through the provider contract.
10. Task-provider incompatibility or drift is detected before mutation, and data-moving sync remains approval-gated.
11. Legacy data is readable but cannot bypass new integrity gates.
12. Installed/generated folders are not tracked, local installed caches are untouched, and installer smoke tests pass.
13. README, canonical documents, plugin references, and the three requested use-case guides describe the implemented behavior consistently.

## Risks and Mitigations

- Git plumbing differences can corrupt snapshot assumptions. Use isolated temporary-index integration tests and verify produced objects through Git itself.
- Legacy compatibility can accidentally become permissive. Represent missing identity explicitly and keep acceptance gates fail closed.
- Multi-repository identity can become ambiguous. Require explicit repository records and reject overlapping ownership.
- Evidence schemas can leak local or secret data. Store stable workspace/repository IDs and sanitized argv only.
- Task CLI differences can invite unsafe command guessing. Discover and record capabilities before mutation and keep recovery explicit.
- Documentation copies can drift. Define canonical ownership, update packaged references in the same release, and test links/drift where practical.
