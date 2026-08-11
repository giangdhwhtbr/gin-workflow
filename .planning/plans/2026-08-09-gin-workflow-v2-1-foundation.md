# Plan: Gin Workflow v2.1 Foundation, Setup, and Multi-Agent Orchestration

## Objective

Evolve `gin-workflow` from Markdown-driven, directly coupled lifecycle guidance into a deterministic v2.1 workflow system with an idempotent setup CLI, a resolved effective configuration, portable capability contracts, a `/workflow` router, bounded stage and worker context, and provider-neutral multi-agent dispatch.

## Model Guidance

- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `high_reasoning`
  - `implement`: `standard_impl`
  - `verify`: `high_reasoning`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for cross-layer contract changes, migration semantics, and concurrency/error-path review. Use `standard_impl` for focused provider and CLI tasks.

## Requirement Analysis

- **Problem statement**: The current plugin has lifecycle commands and useful Beads/review helpers, but lifecycle skills directly prescribe Beads, Telegram, Obsidian, and worker behavior. Configuration is not resolved once, setup is not a first-class lifecycle, worker dispatch has no stable provider contract, and current context loading is not expressed as a bounded manifest.
- **Success criteria**:
  - A versioned `gin-workflow` CLI implements deterministic `/setup` operations and manages `.agent-workflow/` without overwriting user-authored input.
  - `/setup init` is idempotent; resolver precedence produces `.agent-workflow/generated/effective-config.yaml` and provenance atomically.
  - Lifecycle wrappers consume only the generated effective configuration, resolve named artifacts, emit events, enforce transition/approval checks, and use capability contracts rather than provider-specific calls.
  - `/workflow` selects exactly one valid next lifecycle stage.
  - Worker dispatch is a separate capability with native harness adapters plus sequential fallback, bounded manifests, a validated result contract, and idempotent lifecycle events.
  - Providers are replaceable and all supported providers pass shared contract tests.
  - Existing plan and Beads locations are preserved; no migration moves user data or silently upgrades workflow versions.
  - Tests cover setup/migration, configuration provenance, lifecycle routing, providers, isolation, result validation, retries, partial failure, cancellation, and concurrent updates.
- **Constraints**:
  - Source of truth for plugin content remains `plugins/gin-workflow/src/`; generated `plugins/gin-workflow/dist/` and installed `.codex/` copies are never hand-edited.
  - The CLI uses Python 3 with the available `PyYAML` and `jsonschema` libraries; startup must produce an actionable diagnostic if either is unavailable rather than parsing YAML unsafely.
  - Portable configuration contains only logical model tiers, capability selections, artifact names, policy, and secret references—never model identifiers, commands, credentials, or provider implementation detail.
  - Beads remains the durable owner of task identity, dependency, readiness, blocker, and closure state. Runtime event/manifest/result files are supplemental evidence/cache only.
  - Existing Telegram integrations are reused through the notifications capability; no new Telegram API client, polling service, credential flow, or approval channel is created.
  - Commit, push, upgrades, data moves, disabling isolation, current-branch worker execution, scope change, and production-impacting parallel work remain explicit-approval actions.
- **Non-goals**:
  - Do not create a second implementation, TDD, debugging, planning, review, or sub-agent-development methodology.
  - Do not invent cloud SDKs, daemons, or network worker services for any harness.
  - Do not migrate existing plans, Beads data, Obsidian data, review ledgers, or worktrees automatically.
  - Do not implement provider-specific model mappings in the portable configuration schema.

## Approach Options

### Option 1: Markdown-only coordination rules

- Summary: Extend current skills and commands with the new conventions, without a CLI or executable provider contracts.
- Pros: Smallest source diff and no Python runtime additions.
- Cons: Cannot deterministically resolve configuration, validate schemas, model retries/idempotency, run provider contract tests, or guarantee safe setup/migration behavior.

### Option 2: Small Python core with Markdown lifecycle wrappers (selected)

- Summary: Add a focused, dependency-light Python core for configuration, artifacts, events, contracts, setup and providers. Keep Markdown commands/skills as interaction and methodology-routing layers.
- Pros: Separates user interaction from deterministic operations; supports unit/contract testing and all required safety properties while preserving multi-harness plugin packaging.
- Cons: Adds a packaged CLI and a small Python module tree that installer and smoke tests must cover.

### Option 3: Independent implementation per harness

- Summary: Implement setup, lifecycle routing, dispatch, and state separately in Claude, Codex, and Antigravity assets.
- Pros: Maximum immediate harness customization.
- Cons: Duplicates policy, drifts over time, makes parity testing difficult, and violates the portable-policy/provider-boundary requirement.

### Recommended Approach

- **Selected option**: Option 2.
- **Reasoning**: A portable executable core gives configuration, validation, migration, event, and concurrency behavior one deterministic implementation. Thin skills preserve existing platform-native UX and delegate methodology to existing `superpowers:*` skills rather than copying them.

## Scope

- **In scope**:
  - `.agent-workflow/` config, generated, runtime, archive, and state layout.
  - Bundled, versioned `gin-workflow` setup CLI and installer launcher registration.
  - Setup, workflow, context-manager, approval-manager, evidence-manager, and worker-dispatch skills.
  - Capability contracts and provider adapters for task tracking, worker dispatch, knowledge, workspace isolation, review, evidence, and notifications.
  - Effective-config-only lifecycle routing and migration of existing lifecycle skill/command language away from direct external calls.
  - Worker lifecycle/result contracts, native adapter normalization, sequential fallback, and deterministic test doubles.
  - Canonical documentation, source references, plan schema, packaging, and tests.
- **Out of scope**:
  - Publishing a marketplace release, installing dependencies globally without a user action, or forcing repository-wide setup during plugin installation.
  - Replacing the existing review-ledger domain model; it becomes a review provider implementation behind the new contract.
  - Removing legacy helpers before their capability-backed replacements and regression coverage exist.

## File Structure

| Path | Responsibility |
| --- | --- |
| `plugins/gin-workflow/src/scripts/gin-workflow` | Executable CLI entrypoint shipped with the plugin. |
| `plugins/gin-workflow/src/scripts/workflow_core/` | Pure portable core: config, schemas, paths/artifacts, atomic writes, setup state, events, manifests, approvals, and workflow router. |
| `plugins/gin-workflow/src/scripts/workflow_providers/` | Provider protocols, deterministic fakes, and Beads/harness/knowledge/workspace/review/evidence/notification adapters. |
| `plugins/gin-workflow/src/skills/{setup,workflow,context-manager,approval-manager,evidence-manager,worker-dispatch}/` | Thin interaction/policy wrappers and normative references. |
| `plugins/gin-workflow/src/commands/{setup,workflow}.md` | Optional aliases for the new lifecycle wrappers. |
| `plugins/gin-workflow/src/commands/*.md`, `src/skills/*/SKILL.md` | Existing lifecycle wrappers migrated to effective-config/capability boundaries. |
| `plugins/gin-workflow/src/references/` and `docs/` | Canonical lifecycle/state/setup/provider/evidence documentation. |
| `tests/workflow_core/`, `tests/workflow_providers/` | Unit, integration, contract, and concurrency tests; existing review-ledger tests remain intact. |
| `install.sh`, `tests/install_smoke_test.sh`, `README.md` | Packaged CLI installation, three-harness smoke coverage, and user-facing documentation. |

## Public Contracts

```python
class Provider(Protocol):
    name: str
    def health(self, request: HealthRequest) -> HealthResult: ...

class WorkerDispatchProvider(Provider, Protocol):
    def dispatch(self, request: WorkerRequest) -> DispatchReceipt: ...
    def cancel(self, worker_id: str) -> None: ...
    def status(self, worker_id: str) -> WorkerStatus: ...
    def collect_result(self, worker_id: str) -> WorkerResult: ...

def resolve_effective_config(repository: Path, overrides: CommandOverrides) -> ResolvedConfig: ...
def resolve_artifact(config: EffectiveConfig, name: str) -> Path: ...
def create_context_manifest(stage: str, request: ContextRequest) -> ContextManifest: ...
def route_next_stage(state: WorkflowState, config: EffectiveConfig) -> LifecycleStage: ...
```

`WorkerResult` must contain `status`, `task_id`, `summary`, `changed_files`, `commits`, `tests`, `evidence`, and `blockers`; `knowledge_candidates` is optional but normalized to an empty list. Validation failure emits `worker.failed` with reason `invalid_result_contract`.

## Tasks

### Track 1: Build portable workflow core, schemas, and artifact registry

- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/__init__.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/models.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/configuration.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/schemas.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/artifacts.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/atomic.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/events.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/manifests.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/approvals.py`
  - Create `tests/workflow_core/test_configuration.py`
  - Create `tests/workflow_core/test_artifacts.py`
  - Create `tests/workflow_core/test_events.py`
  - Create `tests/workflow_core/test_manifests.py`
- **Model class**: `high_reasoning`
- **Interfaces**:
  - Produces immutable `EffectiveConfig`, `ConfigProvenance`, `ArtifactRegistry`, `WorkflowEvent`, and `ContextManifest` models consumed by every later track.
  - Defines built-in → user profile → organization profile → repository → harness → local → command override precedence and records each resolved field's source.
- **Acceptance criteria**:
  - The resolver writes only `.agent-workflow/generated/effective-config.yaml` and `config-provenance.yaml` through temp-file + fsync + replace semantics; failed validation leaves prior generated output intact.
  - Portable configuration validation rejects provider commands, model names, literal secret-like values, and unknown schema versions; secret references match `secret_ref` syntax and are never resolved into output.
  - `resolve_artifact` returns configured existing paths for plans, beads, worktrees, knowledge, evidence, and runtime; no call moves, creates, or infers a legacy artifact location.
  - Every manifest supports required/conditional/discoverable/reference/prohibited entries, redacts secret/private-reasoning/unrelated-task/history content, and is serializable without parent context.
  - Event append uses stable `event_id` de-duplication and exclusive/atomic write behavior so concurrent writers cannot corrupt JSONL or add duplicate completion events.
- **Validation**:
  - `python3 -m unittest tests.workflow_core.test_configuration tests.workflow_core.test_artifacts tests.workflow_core.test_events tests.workflow_core.test_manifests -v`

### Track 2: Deliver the idempotent setup CLI and safe launcher installation

- **Dependencies**: Track 1
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/gin-workflow`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/cli.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/migrations.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/bundles.py`
  - Modify `install.sh`
  - Modify `tests/install_smoke_test.sh`
  - Create `tests/workflow_core/test_setup_cli.py`
  - Create `tests/workflow_core/test_migrations.py`
  - Create `tests/workflow_core/test_bundles.py`
- **Model class**: `high_reasoning`
- **Interfaces**:
  - Provides `gin-workflow setup detect|init|configure|refresh|update|doctor|status|diff|rollback|export-bundle|verify-bundle` with `--dry-run`, `--format json`, `--repository`, `--harness`, and `--non-interactive`.
  - `SetupService` uses Track 1's resolver and atomic store; it returns structured command results so skills never parse human output.
- **Acceptance criteria**:
  - `init` creates the documented `.agent-workflow/` tree and minimal human-authored config only when absent; a second identical call makes no content changes and returns `already_initialized`.
  - `configure` is approval-gated for user-authored writes; `refresh` regenerates generated files; `doctor/status/diff/verify-bundle` are read-only; `update` only proposes/applies explicit versioned migrations with backup; `rollback` requires a validated explicit backup target.
  - Bundles include generated/config provenance and declared references without literal secrets, runtime secrets, or archives; verification detects hash/schema mismatch.
  - `install.sh` copies/links the executable and registers a versioned user launcher on `PATH` without replacing a different workflow version silently. Dry-run explains each proposed action.
  - Missing `yaml` or `jsonschema` produces a non-zero structured diagnostic with remediation, never a partial setup write.
- **Validation**:
  - `python3 -m unittest tests.workflow_core.test_setup_cli tests.workflow_core.test_migrations tests.workflow_core.test_bundles -v`
  - `bash tests/install_smoke_test.sh`

### Track 3: Define capability contracts and replaceable provider implementations

- **Dependencies**: Tracks 1-2
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/__init__.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/contracts.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/registry.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/task_tracking.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/knowledge.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/workspace.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/review.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/evidence.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/notifications.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/fakes.py`
  - Create `tests/workflow_providers/test_contracts.py`
  - Create `tests/workflow_providers/test_registry.py`
  - Create `tests/workflow_providers/test_evidence.py`
- **Model class**: `high_reasoning`
- **Interfaces**:
  - Defines provider-neutral `create/read/update`, `search/propose`, `create/isolate/cleanup`, `request/status`, `record/query`, and `notify` contracts as applicable.
  - Exposes `ProviderRegistry.from_effective_config(config)` and makes every provider supply health and capability metadata.
- **Acceptance criteria**:
  - Beads calls exist only inside the task-tracking provider; worktree commands only inside workspace provider; existing review-ledger only behind review provider; existing Telegram integration only behind notifications provider; Obsidian/repository fallback only behind knowledge provider.
  - Knowledge provider accepts candidates and policy decisions rather than worker-initiated permanent writes.
  - Evidence provider writes a configured evidence index plus tests/reviews/repository records and can answer whether required acceptance evidence is complete.
  - Shared contract tests execute against each real adapter and fake provider, asserting normalized success, unavailable, invalid request, and idempotent behavior.
- **Validation**:
  - `python3 -m unittest tests.workflow_providers.test_contracts tests.workflow_providers.test_registry tests.workflow_providers.test_evidence -v`

### Track 4: Add setup/workflow/context/approval/evidence coordination wrappers and migrate lifecycle boundaries

- **Dependencies**: Tracks 1-3
- **Files**:
  - Create `plugins/gin-workflow/src/commands/setup.md`
  - Create `plugins/gin-workflow/src/commands/workflow.md`
  - Create `plugins/gin-workflow/src/skills/setup/SKILL.md`
  - Create `plugins/gin-workflow/src/skills/workflow/SKILL.md`
  - Create `plugins/gin-workflow/src/skills/context-manager/SKILL.md`
  - Create `plugins/gin-workflow/src/skills/approval-manager/SKILL.md`
  - Create `plugins/gin-workflow/src/skills/evidence-manager/SKILL.md`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/router.py`
  - Create `tests/workflow_core/test_router.py`
  - Modify `plugins/gin-workflow/src/commands/discuss.md`
  - Modify `plugins/gin-workflow/src/commands/plan.md`
  - Modify `plugins/gin-workflow/src/commands/orchestrate.md`
  - Modify `plugins/gin-workflow/src/commands/execute.md`
  - Modify `plugins/gin-workflow/src/commands/verify.md`
  - Modify `plugins/gin-workflow/src/commands/ship.md`
  - Modify `plugins/gin-workflow/src/commands/progress.md`
  - Modify matching lifecycle `plugins/gin-workflow/src/skills/*/SKILL.md` files
- **Model class**: `high_reasoning`
- **Interfaces**:
  - `route_next_stage(state, config)` returns one of `discuss`, `plan`, `orchestrate`, `execute`, `verify`, `ship`, or `progress` with a transition decision/evidence.
  - Every wrapper receives `EffectiveConfig`, `ArtifactRegistry`, a stage-specific `ContextManifest`, and `ApprovalDecision` before calling a provider or a methodology skill.
- **Acceptance criteria**:
  - `/setup` documents exactly the CLI subcommands and keeps user interaction/approval in the skill, while deterministic work is delegated to CLI.
  - `/workflow` never combines multiple lifecycle actions; it routes only after checking state and guards.
  - Lifecycle source text contains no direct `bd`, Telegram API, Obsidian, worktree command, or harness worker invocation instructions. It names the corresponding capability instead.
  - Every stage's manifest limits required context and makes related symbols/tests/knowledge discoverable on demand; review manifests exclude private reasoning and self-assessment/persuasive summaries.
  - Isolation disablement, current-branch execution, execution-strategy/scope changes, and production-impacting parallel work require native-harness approval plus a durable audit event; notifications remain optional and provider-backed.
- **Validation**:
  - `python3 -m unittest tests.workflow_core.test_router -v`
  - `rg -n "bd |telegram\.sh|api\.telegram|obsidian|worktree-create|invoke_subagent" plugins/gin-workflow/src/commands plugins/gin-workflow/src/skills` is reviewed to confirm remaining hits are provider/legacy-reference docs only, not lifecycle instructions.

### Track 5: Implement first-class worker dispatch and harness-native adapters

- **Dependencies**: Tracks 1-4
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/worker_dispatch.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/claude_worker.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/codex_worker.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/antigravity_worker.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/sequential_worker.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_core/worker_scheduler.py`
  - Create `plugins/gin-workflow/src/skills/worker-dispatch/SKILL.md`
  - Create `plugins/gin-workflow/src/skills/worker-dispatch/references/worker-lifecycle.md`
  - Create `plugins/gin-workflow/src/skills/worker-dispatch/references/delegation-policy.md`
  - Create `plugins/gin-workflow/src/skills/worker-dispatch/references/result-contract.md`
  - Create `tests/workflow_providers/test_worker_dispatch.py`
  - Create `tests/workflow_providers/test_worker_adapters.py`
  - Create `tests/workflow_core/test_worker_scheduler.py`
- **Model class**: `high_reasoning`
- **Interfaces**:
  - Implements `dispatch(request)`, `cancel(worker_id)`, `status(worker_id)`, and `collect_result(worker_id)` for all worker providers.
  - `WorkerRequest` holds objective, constraints, generated manifest, isolation policy, expected output, task id, workflow id, retry identity, and model tier—not parent context or provider model names.
- **Acceptance criteria**:
  - Plans use `execution_strategy.mode`, `execution_strategy.workers.mode`, and rationale. Orchestrate selects direct mode for small/sequential/one-agent/≤3-task work and worker mode only for the stated parallel/long-running/specialized/review conditions.
  - Dispatcher emits requested, assigned, started, context_loaded, progress_updated, completed, failed, and cancelled events. Repeated worker update/completion events are idempotent.
  - Worker calls delegate coding workflow to `subagent-driven-development`; the wrapper never repeats implementation, TDD, debugging, planning, or review methodology.
  - Native adapters detect harness support and normalize requests/results; unavailable adapters emit `worker.unavailable` then activate configured sequential fallback without cloud SDKs or daemon processes.
  - Context unavailable fails with `context_unavailable`; invalid/missing result fields fail with `invalid_result_contract`; timeout/retry/partial failure preserve completed results and never rerun a completed worker.
  - Parallel scheduling enforces `max_parallel_workers`, workspace isolation, and one task/worker claim; concurrent state updates do not corrupt runtime event records or task-tracking operations.
- **Validation**:
  - `python3 -m unittest tests.workflow_providers.test_worker_dispatch tests.workflow_providers.test_worker_adapters tests.workflow_core.test_worker_scheduler -v`

### Track 6: Update plan schema, canonical docs, migration guidance, and user documentation

- **Dependencies**: Tracks 2-5
- **Files**:
  - Modify `plugins/gin-workflow/src/skills/writing-plans/plan-schema.md`
  - Modify `plugins/gin-workflow/src/skills/writing-plans/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/bead-orchestrator/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/bead-worker/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/dispatching-parallel-agents/SKILL.md`
  - Modify `docs/agent-task-lifecycle.md`
  - Modify `docs/orchestration-state-model.md`
  - Create `docs/setup-system.md`
  - Create `docs/capability-provider-contracts.md`
  - Create `docs/context-and-evidence-policy.md`
  - Modify `plugins/gin-workflow/src/references/orchestration-state-model.md`
  - Create or update matching source references for new canonical docs
  - Modify `README.md`
  - Modify `AGENTS.md`
- **Model class**: `standard_impl`
- **Interfaces**:
  - The plan schema exports the exact v2.1 `execution_strategy` shape used by Track 5.
  - Canonical docs state authoritative ownership and point to the CLI/contract entry points rather than duplicating provider command syntax.
- **Acceptance criteria**:
  - Docs make `.agent-workflow/generated/effective-config.yaml` the sole lifecycle configuration input, while preserving Beads/plan/runtime ownership distinctions.
  - Migration guidance documents schema/workflow/setup CLI versions, development → preview → stable channels, pinning, explicit approval, backup/rollback, and no automatic artifact movement.
  - README lists `/setup` and `/workflow`, explains setup-before-lifecycle behavior, and distinguishes plugin installation from repository initialization.
  - Worker context/result/event, fresh review context, knowledge proposal, evidence index, secret reference, and no-duplicate-methodology rules are documented once canonically and linked from skills.
- **Validation**:
  - `rg -n "worker_strategy|\.gin-workflow|direct Beads|direct Telegram" README.md docs plugins/gin-workflow/src` is reviewed and obsolete v1 architectural instructions are removed or explicitly marked migration-only.
  - Markdown links in edited commands, skills, docs, and references resolve within the packaged source tree.

### Track 7: Run end-to-end regression and packaging verification

- **Dependencies**: Tracks 1-6
- **Files**:
  - Modify `tests/install_smoke_test.sh`
  - Create `tests/workflow_core/test_end_to_end.py`
  - Create `tests/workflow_providers/test_harness_packaging.py`
  - Modify `README.md` only if exact verification commands need documenting
- **Model class**: `high_reasoning`
- **Interfaces**:
  - Uses fake providers and a temporary repository to exercise setup → effective config → workflow route → planned/orchestrated worker lifecycle → evidence verification without requiring real harness sessions.
- **Acceptance criteria**:
  - End-to-end test proves setup idempotency, no-secret artifact serialization, effective-config-only lifecycle call, direct route, parallel route, unavailable-to-sequential fallback, partial worker completion preservation, and verification evidence gating.
  - Installer smoke tests confirm CLI, all new skills/commands/references, and provider scripts are included in Claude, Codex, and Antigravity output layouts.
  - Existing `tests/review_ledger` suite and installation tests pass unchanged except for intentional packaging assertions.
  - Final evidence records exact test commands/output and `git status`; Beads orchestration occurs only after this plan receives approval.
- **Validation**:
  - `python3 -m unittest discover -s tests -p 'test_*.py' -v`
  - `bash tests/install_smoke_test.sh`
  - `git status --short`

## Integration

- **Branch**: create only after user authorizes implementation; use a dedicated branch/worktree when worker mode is selected.
- **Merge strategy**: sequential foundation (Tracks 1-2), parallel-capable provider and wrapper work after Track 2 (Tracks 3-4), then worker dispatch (Track 5), documentation (Track 6), and final integration verification (Track 7). Do not run tracks in parallel against overlapping lifecycle or installer files.

## Validation

- [ ] Setup commands satisfy idempotency, dry-run, JSON output, validation, migration, backup/rollback, and bundle requirements.
- [ ] The effective config and provenance are generated atomically with documented precedence; lifecycle code consumes no unresolved config.
- [ ] Every capability provider passes shared contract tests and lifecycle source uses contracts instead of external APIs/CLIs.
- [ ] `/workflow` enforces legal transitions and delegates to exactly one stage.
- [ ] Stage/worker/reviewer manifests exclude secrets, unrelated state, private reasoning, and unrelated history.
- [ ] Worker adapters, scheduling, fallback, retries, cancellation, partial failure, duplicate completion, and concurrent updates pass deterministic tests.
- [ ] Evidence gating, knowledge proposal policy, review fresh-context policy, version pinning, and safe migration behavior are covered.
- [ ] Source packaging and all existing review-ledger/install regressions pass for Claude, Codex, and Antigravity layouts.

## Risks and Mitigations

- **Provider API variation**: Native adapters expose only normalized dispatch/cancel/status/collect semantics, return unavailable when a harness cannot perform an operation, and use sequential fallback rather than emulating an undocumented API.
- **Configuration corruption or secret leakage**: Validate before write, use atomic replace/backups, store provenance as source labels rather than secret values, and apply manifest/event redaction centrally.
- **State ownership drift**: Keep task status in Beads, approved decomposition in plan files, and runtime files supplemental; contract tests reject lifecycle direct provider operations.
- **Parallel races**: Use idempotency keys, per-worker/task ownership, atomic event persistence, and preserve terminal successful results on retry/failure paths.
- **Breaking existing installs**: Package source assets through the existing installer, add launcher behavior behind explicit install/update actions, and use three-harness smoke tests before release.

## Notes

- Model guidance is planning metadata, not Beads state.
- `subagent-driven-development` remains the sole reusable worker-execution methodology. `worker-dispatch` supplies policy, bounded context, provider routing, and result collection only.
- No commit or push is authorized by this plan; approval to implement does not imply delivery authorization.
