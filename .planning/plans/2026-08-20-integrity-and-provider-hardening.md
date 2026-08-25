# Plan: Integrity and Provider Hardening

> **For agentic workers:** Execute this plan through Gin Workflow orchestration and one Beads-backed worker per track. Every worker must use the methodology required by its assigned skill, preserve the declared file scope, and stop for review at the track acceptance gate.

**Goal:** Make review approval, worker results, verification evidence, provider routing, and task closure refer to one replayable workflow attempt and source snapshot while keeping installed/generated artifacts outside source control.

**Architecture:** Introduce a provider-neutral acceptance identity, then make Git checkpoints, review events, worker results, evidence completeness, and task closure consume it. Deliver the change through versioned compatibility readers and explicit migrations, with provider-specific behavior isolated behind capability contracts.

**Tech Stack:** Python 3 standard library, Git plumbing, JSON/JSONL, YAML, `unittest`, shell and PowerShell installers, Beads-compatible task CLIs.

**Spec:** `.planning/specs/2026-08-20-integrity-and-provider-hardening-design.md`

## Global Constraints

- Do not edit or delete installed plugin caches, including `~/.codex/plugins/cache/`.
- Repository source of truth remains `plugins/gin-workflow/src/`, tests, docs, marketplace metadata, and installers.
- Keep `.agent-workflow/config.yaml`; remove generated/runtime/backups and harness-installation roots from Git tracking without deleting local copies.
- Legacy ledger/evidence records remain readable but cannot satisfy current integrity gates when required identity is missing.
- Protected scope changes and data-moving task sync require a fresh typed approval and matching persisted audit event.
- Portable plans and worker requests contain logical provider roles and reasoning tiers only; never concrete provider or model names.
- New workflow, schema, setup-CLI, and launcher version is `2.3`; new plugin release version is `1.1.0`.
- No commit or push is authorized by this plan.

---

## Objective

Produce a versioned, backward-readable release that closes all reported review, checkpoint, lease, Antigravity, evidence, assignment-validation, task-provider, repository-hygiene, and use-case documentation gaps. Completion requires fail-closed identity correlation, non-invasive checkpoint replay, atomic ownership, provider-capability diagnostics, and verified installer/package boundaries.

## Model Guidance

- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for implementation tracks involving Git object construction, concurrency, migration, approval integrity, or cross-provider state correlation.

## Requirement Analysis

- **Problem statement:** Current lifecycle components can approve an empty scope hash, checkpoint the wrong working-tree state, start review without documented lease acquisition, reject valid untracked source, treat stale evidence as complete, accept unauditable worker test reports, delay route validation until dispatch, reject usable default-model Antigravity installations, and bypass task-provider contracts for required durable operations.
- **Success criteria:** All thirteen acceptance criteria in the confirmed design spec have an implementation track and executable verification gate below.
- **Constraints:** Preserve legacy read compatibility; avoid mutating the user's current branch/index during checkpointing; keep source, runtime evidence, and task ownership separate; use configured capability providers; preserve conservative Git authority.
- **Non-goals:** Rewriting the lifecycle from scratch, silently repairing Beads data, selecting machine-local models in the plan, editing installed caches, or changing `.beads/`/`.planning/` ownership.

## Approach Options

### Option 1: Versioned shared identity with dependent provider upgrades

- **Summary:** Add one canonical identity model and migrate each provider boundary to consume it in dependency order.
- **Pros:** End-to-end correlation is explicit, legacy behavior is contained, and each track has an independent test/review gate.
- **Cons:** Several public contracts change and require coordinated schema/version work.

### Option 2: Independent defect patches

- **Summary:** Fix each observed file without a shared acceptance identity.
- **Pros:** Smaller individual diffs.
- **Cons:** Review, worker, evidence, and task providers can continue disagreeing about the current source snapshot; stale-evidence gaps remain likely.

### Option 3: New lifecycle subsystem

- **Summary:** Replace review/evidence/task integrations with a new unified implementation.
- **Pros:** Clean-slate boundaries.
- **Cons:** Excessive migration and regression risk; duplicates working provider and ledger infrastructure.

### Recommended Approach

- **Selected option:** Option 1.
- **Reasoning:** It is the smallest approach that makes source replay and acceptance correlation coherent across every affected capability while retaining existing adapters and legacy readers.

## Scope

- **In scope:** Shared identity, Git checkpoint/ref creation, ledger init/approval/leases, worker provenance, evidence correlation, plan/route validation, Antigravity provider-default mode, task-provider parity/preflight/sync, version migration, repository ignore cleanup, installers, README/canonical references/use-case guides, and integration/security review.
- **Out of scope:** User cache mutation, automatic backend recovery, production data sync without approval, concrete model selection in portable artifacts, unrelated refactoring, commits, and pushes.

## Execution Strategy

```yaml
execution_strategy:
  mode: worker
  workers:
    mode: parallel
  rationale: Nine specialized tracks are required; checkpoint and routing work can proceed independently after the identity foundation, while explicit dependencies serialize shared contracts, ledger transitions, release packaging, documentation, and final review.
```

## Tasks

### Track 1: Acceptance Identity and Versioned Schema Foundation

- **Dependencies:** none
- **Files:**
  - Create: `plugins/gin-workflow/src/scripts/workflow_core/identity.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/__init__.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/schemas.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/models.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/configuration.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/migrations.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/cli.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`
  - Test: `tests/workflow_core/test_identity.py`
  - Test: `tests/workflow_core/test_migrations.py`
  - Test: `tests/workflow_core/test_configuration.py`
- **Provider role:** `backend`
- **Reasoning:** `high`
- **Model class:** `high_reasoning`
- **Interfaces:**
  - Produces `RepositorySnapshot(repository_id, source_scope_hash, source_tree_hash, checkpoint_sha, checkpoint_ref)`.
  - Produces `AcceptanceIdentity(workflow_id, attempt_id, task_id, repositories)` with `to_dict()`, `from_mapping()`, and exact-match validation.
  - Produces the registered `2.2 -> 2.3` configuration migration and version constants consumed by later tracks.
- **Acceptance criteria:** Canonical identities reject empty/duplicate repository entries, serialize deterministically, round-trip losslessly, and compare all identity fields; 2.2 configurations migrate to 2.3 through the existing backup/approval path.
- **Estimated complexity:** high

- [ ] **Step 1: Add failing identity tests.** Define tests that construct one- and multi-repository identities, reject blank IDs/hashes, reject duplicate repository IDs, verify deterministic ordering, and prove that changing scope hash, tree hash, checkpoint SHA, workflow, attempt, or task causes mismatch.
- [ ] **Step 2: Run the identity tests and confirm the missing module failure.**

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_identity -v
  ```

- [ ] **Step 3: Implement the immutable identity types.** Use frozen dataclasses and this public shape:

  ```python
  @dataclass(frozen=True)
  class RepositorySnapshot:
      repository_id: str
      source_scope_hash: str
      source_tree_hash: str
      checkpoint_sha: str
      checkpoint_ref: str

  @dataclass(frozen=True)
  class AcceptanceIdentity:
      workflow_id: str
      attempt_id: str
      task_id: str
      repositories: Sequence[RepositorySnapshot]

      def to_dict(self) -> dict[str, object]: return {"workflow_id": self.workflow_id, "attempt_id": self.attempt_id, "task_id": self.task_id, "repositories": [asdict(item) for item in self.repositories]}
      @classmethod
      def from_mapping(cls, value: Mapping[str, object]) -> "AcceptanceIdentity": return cls(str(value["workflow_id"]), str(value["attempt_id"]), str(value["task_id"]), tuple(RepositorySnapshot(**dict(item)) for item in value["repositories"]))
      def require_exact_match(self, other: "AcceptanceIdentity") -> None:
          for field_name in ("workflow_id", "attempt_id", "task_id", "repositories"):
              if getattr(self, field_name) != getattr(other, field_name):
                  raise ValueError(f"acceptance identity mismatch: {field_name}")
  ```

  Validation must identify the first mismatched field without including secrets or absolute paths.
- [ ] **Step 4: Add the 2.3 migration and version-channel tests.** Extend migration/configuration tests to prove a 2.2 portable config upgrades all three version fields to 2.3, dry-run does not write, backup precedes mutation, and unsupported version jumps fail closed.
- [ ] **Step 5: Update core version constants and exports.** Set workflow/schema/setup CLI model defaults and CLI version to `2.3`, register the migration, and export identity types from `workflow_core`.
- [ ] **Step 6: Run the focused core suite.**

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_identity tests.workflow_core.test_migrations tests.workflow_core.test_configuration tests.workflow_core.test_setup_cli -v
  ```

### Track 2: Non-Invasive Git Checkpoints and Ledger Initialization

- **Dependencies:** Track 1
- **Files:**
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/source_identity.py`
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/git_adapter.py`
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/projections.py`
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/schema.py`
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/renderer.py`
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/cli.py`
  - Modify: `plugins/gin-workflow/src/scripts/review-ledger.py`
  - Test: `tests/review_ledger/test_source_identity.py`
  - Test: `tests/review_ledger/test_git_adapter.py`
  - Test: `tests/review_ledger/test_cli.py`
  - Test: `tests/review_ledger/test_integration.py`
- **Provider role:** `backend`
- **Reasoning:** `high`
- **Model class:** `high_reasoning`
- **Interfaces:**
  - Produces `SourceCheckpoint(repository_id, checkpoint_sha, checkpoint_ref, source_scope_hash, source_tree_hash)`.
  - Produces `create_source_checkpoint(repo_path, scope, task_id, base_ref, review_ref) -> SourceCheckpoint` without branch/index mutation.
  - Extends CLI `init` with repeatable included/excluded/generated path arguments and repository paths.
- **Acceptance criteria:** Checkpoints include ordinary in-scope untracked source, exclude generated/artifact paths, preserve the user's branch/index, encode submodule gitlinks, reject ambiguous nested repositories, and initialize ledger hashes automatically.
- **Estimated complexity:** high

- [ ] **Step 1: Replace branch-switch expectations with failing non-invasive checkpoint tests.** Capture `HEAD`, branch, `git status --porcelain`, and `git diff --cached` before checkpoint; assert they are unchanged afterward while the dedicated ref resolves to a tree containing modified and new in-scope source.
- [ ] **Step 2: Add generated, submodule, and nested-repository fixtures.** Prove excluded/generated files are absent, submodules appear as mode `160000`, an explicitly declared nested repository is separate, and an undeclared overlapping repository fails with `GitAdapterError`.
- [ ] **Step 3: Implement canonical path and tree helpers.** Parse `git ls-files --stage`, `git status --porcelain=v1 -z`, and object metadata without shell interpolation. Normalize paths relative to the resolved repository root and reject traversal.
- [ ] **Step 4: Implement the temporary-index checkpoint.** Use a temporary `GIT_INDEX_FILE`, `git read-tree <base>`, explicit path updates, `git write-tree`, `git commit-tree`, and `git update-ref <review-ref> <commit>`. Never call checkout/switch or mutate the real index.
- [ ] **Step 5: Extend ledger projections and CLI initialization.** Persist canonical scope plus repository path identity, base SHA, checkpoint ref/SHA, scope hash, and tree hash. Keep legacy fields readable and mark missing identity explicitly.
- [ ] **Step 6: Run focused review-ledger tests.**

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.review_ledger.test_source_identity tests.review_ledger.test_git_adapter tests.review_ledger.test_cli tests.review_ledger.test_integration -v
  ```

### Track 3: Atomic Review Lease and Approval Replay

- **Dependencies:** Track 1, Track 2
- **Files:**
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/lease.py`
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/cli.py`
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/projections.py`
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/events.py`
  - Modify: `plugins/gin-workflow/src/scripts/review_ledger/renderer.py`
  - Modify: `plugins/gin-workflow/src/scripts/review-ledger.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/contracts.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/review.py`
  - Test: `tests/review_ledger/test_lease.py`
  - Test: `tests/review_ledger/test_events.py`
  - Test: `tests/review_ledger/test_integration.py`
  - Test: `tests/workflow_providers/test_contracts.py`
- **Provider role:** `backend`
- **Reasoning:** `high`
- **Model class:** `high_reasoning`
- **Interfaces:**
  - Produces `ReviewLease(lease_id, actor_id, expires_at, ledger_revision)` in `ReviewStatus`.
  - Produces `start_review(task_id, actor_id, requested_lease_id=None, ttl_seconds=600)` as one transactional mutation.
  - Makes `ReviewOutcomeRequest` carry the accepted `AcceptanceIdentity` and expected ledger revision.
- **Acceptance criteria:** Concurrent starts yield one owner; same-reviewer retry renews idempotently; live conflicting ownership rejects without mutation; expiry takeover is auditable; approvals persist and replay real scope/tree/checkpoint identity.
- **Estimated complexity:** high

- [ ] **Step 1: Add failing lease race and transaction tests.** Use multiple processes against one ledger to prove exactly one acquisition succeeds, JSON/Markdown projections remain valid, and a failed batch leaves byte-identical files.
- [ ] **Step 2: Add retry, conflict, renewal, expiry-takeover, and revision tests.** Assert event order `lease-acquired|lease-renewed|lease-broken -> review-started`, returned lease metadata, and rejection on mismatched actor/revision.
- [ ] **Step 3: Centralize transactional mutation.** Hold one stable sidecar lock while loading, validating all events, applying them to a temporary projection, rendering both outputs, fsyncing, and atomically replacing both files.
- [ ] **Step 4: Implement atomic `start_review`.** Generate a lease ID when absent, default TTL to 600 seconds, renew same actor idempotently, record explicit expired takeover, and return current revision.
- [ ] **Step 5: Replace empty approval hashes in the provider.** Reload checkpoint refs, recompute scope/tree hashes from Git objects, require exact identity match, and populate `source_scope_hash`, repository snapshot records, terminal findings, workflow/attempt/task/reviewer IDs, and approval event identity.
- [ ] **Step 6: Add legacy fail-closed tests.** Load old ledgers successfully but reject their approval as verification evidence until checkpoint and re-review produce complete identity.
- [ ] **Step 7: Run lease, ledger, and review-provider suites.**

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.review_ledger.test_lease tests.review_ledger.test_events tests.review_ledger.test_integration tests.workflow_providers.test_contracts -v
  ```

### Track 4: Worker Test Provenance and Correlated Evidence

- **Dependencies:** Track 1, Track 3
- **Files:**
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/contracts.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/worker_dispatch.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/evidence.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/fakes.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/review_coordinator.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/worker_scheduler.py`
  - Test: `tests/workflow_providers/test_worker_dispatch.py`
  - Test: `tests/workflow_providers/test_evidence.py`
  - Test: `tests/workflow_core/test_review_coordinator.py`
  - Test: `tests/workflow_core/test_worker_scheduler.py`
- **Provider role:** `backend`
- **Reasoning:** `high`
- **Model class:** `high_reasoning`
- **Interfaces:**
  - Produces `WorkerTestResult(argv, exit_code, started_at, finished_at, workspace_id, repository_id, attempt_id, source_tree_hash)`.
  - Adds `acceptance_identity` to `WorkerRequest`, `WorkerResult`, `EvidenceRecord`, and `EvidenceQuery`.
  - Changes `completeness(task_id, acceptance_identity)` to require one coherent evidence set.
- **Acceptance criteria:** Invalid exit codes/timestamps/workspace/tree identity fail at normalization; evidence from different attempts or trees never combines; accepted evidence follows attempt/test-checkpoint/review/verification ordering.
- **Estimated complexity:** high

- [ ] **Step 1: Add failing worker-result semantic tests.** Cover non-list argv, secret-like argv redaction, non-integer exit code, `passed` with nonzero exit, reversed timestamps, wrong workspace/repository/attempt/tree, and mismatch between result and request identity.
- [ ] **Step 2: Implement immutable structured test results.** Normalize argv as a sanitized tuple, require UTC RFC3339 timestamps, derive success from `exit_code == 0`, and reject absolute workspace paths/environment payloads.
- [ ] **Step 3: Version worker request/result serialization.** Include acceptance identity in portable payloads without concrete provider/model aliases. Ensure native adapter output normalization produces `invalid_result_contract` before evidence recording on any mismatch.
- [ ] **Step 4: Add failing coherent-set evidence tests.** Record individually successful categories across different attempts, repositories, tree hashes, scope hashes, and event times; assert completeness remains false with precise mismatch diagnostics.
- [ ] **Step 5: Implement identity-aware evidence storage and queries.** Keep version-1 records readable, serialize version-2.3 identity, filter candidate sets by exact identity, validate event ordering, and return the selected coherent evidence set.
- [ ] **Step 6: Update fakes and coordinator/scheduler propagation.** Require the same contract in tests and production paths so fakes cannot bypass provenance checks.
- [ ] **Step 7: Run worker/evidence suites.**

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_providers.test_worker_dispatch tests.workflow_providers.test_evidence tests.workflow_core.test_review_coordinator tests.workflow_core.test_worker_scheduler -v
  ```

### Track 5: Early Assignment Validation and Antigravity Provider-Default Mode

- **Dependencies:** Track 1
- **Files:**
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/assignments.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/provider_config.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/native_cli.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/antigravity_worker.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/registry.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/routed_worker.py`
  - Test: `tests/workflow_core/test_assignments.py`
  - Test: `tests/workflow_core/test_provider_config.py`
  - Test: `tests/workflow_providers/test_worker_adapters.py`
  - Test: `tests/workflow_providers/test_registry.py`
  - Test: `tests/workflow_providers/test_routed_worker.py`
- **Provider role:** `backend`
- **Reasoning:** `medium`
- **Model class:** `standard_impl`
- **Interfaces:**
  - Produces `validate_plan_assignments(tasks, config) -> Sequence[AssignmentValidationError]` for portable role/tier validation.
  - Produces `resolve_all_assignments(requests, config, local) -> Sequence[AssignmentManifest]` with no writes.
  - Extends `NativeHealth` with explicit-selection capability and supports the machine-local sentinel `provider_default`.
- **Acceptance criteria:** Every plan task validates before approval; every local route resolves before orchestration mutation; Antigravity without `--model` is degraded/eligible only for explicit `provider_default`; runtime evidence records the limitation.
- **Estimated complexity:** medium

- [ ] **Step 1: Add aggregate plan-validation tests.** Supply multiple invalid roles and tiers and assert all task-specific diagnostics are returned in deterministic task order.
- [ ] **Step 2: Add atomic resolution tests.** Mix valid and unresolved machine-local routes and prove no assignment manifest is written when any request fails.
- [ ] **Step 3: Implement batch validators.** Keep `AssignmentRequest` validation, add pure collection-level functions, and make plan/orchestration callers validate the full batch before `write_assignment_manifest` or task-provider calls.
- [ ] **Step 4: Add Antigravity default-mode tests.** Probe help without `--model`, assert degraded availability, build argv without `--model`, require local `provider_default`, reject a concrete model, and verify same-tier fallback.
- [ ] **Step 5: Implement capability-aware invocation.** Carry `explicit_model_selection: bool` and `selection_mode: explicit|provider_default` through health/routing evidence. Do not claim a concrete model when default mode is used.
- [ ] **Step 6: Run assignment and routing suites.**

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_core.test_assignments tests.workflow_core.test_provider_config tests.workflow_providers.test_worker_adapters tests.workflow_providers.test_registry tests.workflow_providers.test_routed_worker -v
  ```

### Track 6: Task-Provider Parity, Preflight, and Guarded Sync

- **Dependencies:** Track 1, Track 4, Track 5
- **Files:**
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/contracts.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/task_tracking.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/fakes.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_providers/registry.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/router.py`
  - Modify: `plugins/gin-workflow/src/scripts/workflow_core/approvals.py`
  - Test: `tests/workflow_providers/test_contracts.py`
  - Test: `tests/workflow_providers/test_registry.py`
  - Test: `tests/workflow_core/test_router.py`
  - Create: `tests/workflow_providers/test_task_tracking_compatibility.py`
- **Provider role:** `backend`
- **Reasoning:** `high`
- **Model class:** `high_reasoning`
- **Interfaces:**
  - Extends `TaskCreateRequest`/`TaskRecord` with notes and acceptance criteria.
  - Produces `TaskClosureRequest(task_id, closure_reason, acceptance_evidence)`.
  - Produces dependency/readiness records plus `TaskPreflight` and `TaskSyncRequest(mode, dry_run)`.
  - Extends `TaskTrackingProvider` with close, dependency, readiness, preflight, and sync methods.
- **Acceptance criteria:** Workers never bypass the provider for notes/evidence/closure; dependency readiness is provider-owned; `bd`/`br` capability/drift failures stop before mutation; data-moving sync requires `data_move` approval and persisted audit reread.
- **Estimated complexity:** high

- [ ] **Step 1: Add contract tests for notes, acceptance, closure, dependencies, readiness, preflight, and sync.** Assert unsupported fields remain invalid and every mutation is idempotent by operation/key/request fingerprint.
- [ ] **Step 2: Build fake `bd` and `br` executable fixtures.** Fixtures expose distinct version/help/subcommand responses, JSON shapes, readiness states, and the reported `br sync --flush-only` failure without touching real task data.
- [ ] **Step 3: Implement read-only capability discovery.** Resolve executable family, parse version, probe relevant subcommand help, and return a typed capability set plus backend health/drift diagnostics. Cache only within one provider instance and re-run preflight before mutation.
- [ ] **Step 4: Implement provider-neutral operations.** Map proven capabilities to CLI argv arrays without shell use; normalize task, dependency, readiness, and closure results; fail unavailable before mutation when capability or backend health is insufficient.
- [ ] **Step 5: Implement guarded sync.** Dry-run returns the proposed operation and affected backend without mutation. Flush/pull/push-like data movement requires a matching `ApprovalRequest(action=DATA_MOVE)`, fresh `ApprovalDecision`, and revalidated `approval.recorded` event from `WorkflowEventStore`.
- [ ] **Step 6: Integrate orchestration and worker closure paths.** Require preflight before the first task mutation, create dependencies through the provider, use provider readiness for dispatch, persist outcome notes/acceptance evidence, and close only after coherent evidence completeness.
- [ ] **Step 7: Run task-provider and approval suites.**

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_providers.test_contracts tests.workflow_providers.test_task_tracking_compatibility tests.workflow_providers.test_registry tests.workflow_core.test_router -v
  ```

### Track 7: Release Versioning, Repository Hygiene, and Installer Packaging

- **Dependencies:** Track 2, Track 3, Track 4, Track 5, Track 6
- **Files:**
  - Modify: `.gitignore`
  - Modify: `.agent-workflow/.gitignore`
  - Remove from Git tracking only: `.codex/**`
  - Remove from Git tracking only: `.agent-workflow/generated/**`
  - Remove from Git tracking only: `.agent-workflow/runtime/**`
  - Remove from Git tracking only: `.agent-workflow/backups/**`
  - Modify: `plugins/gin-workflow/plugin.meta.json`
  - Modify: `plugins/gin-workflow/src/examples/config.full.yaml`
  - Modify: `plugins/gin-workflow/src/examples/providers.local.example.yaml`
  - Modify: `install.sh`
  - Modify: `install.ps1`
  - Modify: `tests/install_smoke_test.sh`
  - Modify: `tests/install_smoke_test.ps1`
  - Modify: `tests/workflow_providers/test_harness_packaging.py`
- **Provider role:** `general`
- **Reasoning:** `medium`
- **Model class:** `standard_impl`
- **Interfaces:**
  - Publishes workflow/launcher `2.3` and plugin `1.1.0` from repository source.
  - Establishes root ignore rules for harness installations and generated workflow output while preserving marketplace metadata and portable config.
- **Acceptance criteria:** Installed/generated roots are untracked and ignored without local deletion; source/package metadata remains tracked; Unix and PowerShell installers build from source into temporary destinations and report version 2.3/1.1.0 consistently.
- **Estimated complexity:** medium

- [ ] **Step 1: Add repository-boundary assertions to packaging tests.** Assert root `/.codex/`, `/.claude/`, `/.agents/`, workflow generated/runtime/backups, and `plugins/*/dist/` are ignored; assert plugin source, `.claude-plugin/`, `.agent-workflow/config.yaml`, docs, and installers are not ignored.
- [ ] **Step 2: Update ignore rules.** Add root-anchored installation patterns and generated workflow subdirectories. Keep local copies by removing tracked entries from the index only during execution; do not run filesystem deletion commands.
- [ ] **Step 3: Update release metadata and examples.** Set plugin metadata to 1.1.0 and all supported workflow/schema/setup/launcher examples to 2.3.
- [ ] **Step 4: Update installer smoke expectations.** Verify dry-run, local install, managed launcher upgrade, project-level install, source-to-dist copying, and cache-independent temporary installation on Unix and PowerShell.
- [ ] **Step 5: Run packaging and installer checks.**

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_providers.test_harness_packaging -v
  bash tests/install_smoke_test.sh
  pwsh -NoProfile -File tests/install_smoke_test.ps1
  ```

  If PowerShell 7 is unavailable, record that as an unrun gate in handoff; do not report it as passing.

### Track 8: Canonical Documentation and Workflow Use Cases

- **Dependencies:** Track 7
- **Files:**
  - Modify: `README.md`
  - Modify: `docs/agent-task-lifecycle.md`
  - Modify: `docs/orchestration-state-model.md`
  - Modify: `docs/setup-system.md`
  - Modify: `docs/capability-provider-contracts.md`
  - Modify: `docs/context-and-evidence-policy.md`
  - Modify: `docs/verification-and-handoff-workflow.md`
  - Modify: `docs/provider-routing.md`
  - Create: `docs/use-cases/README.md`
  - Create: `docs/use-cases/large-task.md`
  - Create: `docs/use-cases/resume-in-progress.md`
  - Create: `docs/use-cases/quick-debug.md`
  - Modify corresponding packaged sources under: `plugins/gin-workflow/src/references/`
  - Test: `tests/workflow_providers/test_harness_packaging.py`
- **Provider role:** `docs`
- **Reasoning:** `low`
- **Model class:** `cheap_simple`
- **Interfaces:**
  - Publishes one canonical explanation of identity, checkpoint, lease, evidence, provider-default routing, task preflight/sync, and lifecycle gates.
  - Publishes scenario guides linked from README and packaged consistently by installers.
- **Acceptance criteria:** README and all canonical/packaged references describe implemented behavior without cache paths or manual provider bypasses; all four use-case pages contain prerequisites, flow, gates, example, common failures, and safe recovery.
- **Estimated complexity:** medium

- [ ] **Step 1: Update canonical policy documents from implemented contracts.** Document exact ownership, fail-closed identity correlation, lease transaction behavior, provider-default routing, task preflight, and approval-gated data movement.
- [ ] **Step 2: Add README workflow selection.** Keep the overview concise, link canonical policies, and add a Common Use Cases table pointing to the new guides.
- [ ] **Step 3: Write the large-task guide.** Show setup prerequisite, `$gin-workflow:discuss`, `$gin-workflow:plan`, orchestration, dependency-aware execution, review, verification, and ship with a realistic multi-track example.
- [ ] **Step 4: Write the resume-in-progress guide.** Show config/evidence recovery, `$gin-workflow:progress`, `$gin-workflow:workflow`, ready/blocked/review-pending decisions, and stale runtime-state handling without treating worktree existence as progress.
- [ ] **Step 5: Write the quick-debug guide.** Show bounded requirement confirmation, systematic diagnosis, minimal approved plan, implementation, focused regression test, review/verification, and safe escalation when scope grows.
- [ ] **Step 6: Synchronize packaged reference sources and verify links.** Copy only canonical content intended for installation, keep source ownership explicit, and run packaging tests plus a repository-local Markdown link checker if available.

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests.workflow_providers.test_harness_packaging -v
  rg -n '~/.codex/plugins/cache|source_scope_hash: ""|manual.*bd' README.md docs plugins/gin-workflow/src/references
  ```

  Expected result: no documentation instructs direct cache editing, persists an empty approval hash, or requires provider bypass for supported task operations.

### Track 9: End-to-End Verification and Independent Integrity Review

- **Dependencies:** Track 3, Track 4, Track 5, Track 6, Track 7, Track 8
- **Files:**
  - Modify only if a regression test reveals a defect within an owning track's declared files; route substantive fixes back to that track.
  - Test: `tests/workflow_core/test_end_to_end.py`
  - Test: all suites listed below
- **Provider role:** `review`
- **Reasoning:** `high`
- **Model class:** `high_reasoning`
- **Interfaces:**
  - Consumes every preceding track's public contracts and acceptance evidence.
  - Produces structured findings and a terminal review decision bound to the final source identity.
- **Acceptance criteria:** Full suites pass; an end-to-end scenario proves plan validation, task preflight, worker provenance, non-invasive checkpoint, leased review, hash-bound approval, coherent evidence completeness, and guarded closure; independent review has no unresolved critical/important finding.
- **Estimated complexity:** high

- [ ] **Step 1: Add the cross-capability end-to-end scenario.** Use temporary repositories and fake native/task CLIs to execute one workflow attempt from validated plan metadata through task closure, asserting the same acceptance identity at every boundary.
- [ ] **Step 2: Add adversarial variants.** Change one field at a time—scope hash, tree hash, checkpoint ref, attempt, task, workspace, review event, test exit code, timestamp, lease, task backend health—and assert the lifecycle stops before approval, completeness, or closure.
- [ ] **Step 3: Run all Python tests.**

  ```bash
  PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest discover -s tests -p 'test_*.py' -v
  ```

- [ ] **Step 4: Run installer suites.**

  ```bash
  bash tests/install_smoke_test.sh
  pwsh -NoProfile -File tests/install_smoke_test.ps1
  ```

- [ ] **Step 5: Run repository and syntax checks.**

  ```bash
  python3 -m compileall -q plugins/gin-workflow/src/scripts
  git diff --check
  git status --short
  ```

- [ ] **Step 6: Perform independent review.** Review approval hashes, checkpoint object replay, lock/atomic-write behavior, legacy fail-closed semantics, secret redaction, data-move approvals, repository ignore boundaries, and documentation consistency. Record every finding through the review capability and repeat review after fixes.

## Integration

- **Branch:** `feature/integrity-provider-hardening`
- **Merge strategy:** `parallel-then-merge`
- Merge Track 1 first. Tracks 2 and 5 may then proceed in parallel. Merge Track 2 before Track 3; merge Track 3 before Track 4; merge Track 4 before Track 6. Merge Tracks 3–6 before release Track 7, documentation Track 8, and final review Track 9.
- Resolve shared-file conflicts by preserving the later track's required interface while retaining all earlier tests; never discard an acceptance-identity field to simplify a merge.

## Validation

- [ ] Identity and 2.3 migration tests pass.
- [ ] Review-ledger checkpoint, initialization, lease, concurrency, approval, submodule, nested-repository, and legacy tests pass.
- [ ] Worker-result and coherent evidence tests pass, including adversarial identity mismatches.
- [ ] Plan assignment and Antigravity provider-default routing tests pass.
- [ ] Task-provider `bd`/`br` compatibility, readiness, closure, preflight, dry-run, and guarded sync tests pass.
- [ ] Full Python test discovery passes.
- [ ] Unix installer smoke tests pass.
- [ ] PowerShell installer smoke tests pass, or their absence is explicitly reported as unrun.
- [ ] Python compilation and `git diff --check` pass.
- [ ] Git status confirms cache/install/generated outputs are ignored and local installed caches were untouched.
- [ ] Independent integrity review reaches a terminal decision with no unresolved critical or important findings.

## Risks and Mitigations

- **Temporary-index checkpoint errors:** Verify resulting Git objects and real-index invariance in isolated repositories before accepting the track.
- **Over-permissive legacy readers:** Model missing identity explicitly and test that it never satisfies approval/completeness.
- **Locking races:** Use process-level contention tests and stable sidecar locks; never validate outside the transaction that writes.
- **Evidence leakage:** Sanitize argv, persist stable IDs instead of absolute paths, and reject environment/credential payloads.
- **Provider capability guessing:** Probe executable/version/help before mutation and use only proven operations.
- **Parallel shared-file conflicts:** Enforce the dependency/merge order above; Tracks 3, 4, and 6 serialize changes to `contracts.py`.
- **Installer removal mistakes:** Remove generated paths from Git tracking only and assert source/metadata remain tracked before handoff.
- **Documentation drift:** Update canonical docs first, package their reference sources in the same track, and validate links/content during packaging tests.

## Notes

- The plan is Beads-ready but does not itself create durable execution tasks.
- Model classes guide effort; provider roles and reasoning tiers are portable routing metadata.
- Concrete providers/models are resolved only during orchestration from machine-local configuration.
- Track workers must use TDD for behavior changes and the repository verification-and-handoff checklist before reporting completion.
