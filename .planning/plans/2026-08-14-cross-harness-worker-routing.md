# Plan: Cross-Harness Worker Routing

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` for inline implementation. Use `superpowers:subagent-driven-development` only when the user explicitly authorizes subagent dispatch. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one main harness plan and review while policy-routed, locally authenticated Claude, Codex, and Antigravity workers implement tasks with configured reasoning-to-model mappings, circuit-breaker fallback, and review revision loops.

**Architecture:** Keep plans provider-neutral by assigning `provider_role` and `reasoning`; resolve those fields through portable routing policy and a gitignored machine-local provider map. A routed dispatcher checks model-scoped circuit state, native CLI health, and concurrency before delegating to existing worker lifecycle normalization, while a review coordinator returns structured findings to the implementation route.

**Tech Stack:** Python 3 standard library, PyYAML, jsonschema, unittest, existing workflow core/provider contracts, native `claude`, `codex`, and `agy` CLIs.

## Global Constraints

- Advance `schema_version`, `workflow_version`, and `setup_cli_version` together from `2.1` to `2.2`.
- Keep provider commands and concrete model identifiers out of portable effective config, plans, Beads, worker payloads, exported bundles, and knowledge capture.
- Store executable and reasoning-to-model mappings only in `.agent-workflow/providers.local.yaml`; gitignore it and exclude it from bundles.
- Use existing native CLI login sessions; do not add API-key storage, cloud SDK clients, or daemon services.
- Preserve requested reasoning across fallback; never silently downgrade `high` to `medium` or `low`.
- Keep Beads authoritative for task status, plans authoritative for approved scope/guidance, review ledger authoritative for findings, and runtime files supplemental.
- Keep one isolated workspace and one durable task claim per worker.
- Do not hand-edit generated `plugins/gin-workflow/dist/` or installed `.codex/` assets.
- Commit and push remain separate actions; implementation commits are authorized by the user, but push is not.

---

## Objective

Implement the approved design in `docs/superpowers/specs/2026-08-14-cross-harness-worker-routing-design.md` so setup collects routing parameters, plans describe role/reasoning requirements, orchestration previews concrete assignments, execution selects healthy native workers with circuit-breaker fallback, and review findings return to the responsible implementation route.

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
- `override_rule`: Use `high_reasoning` for schema/migration, circuit-breaker concurrency, native process safety, and review-state coordination. Use `standard_impl` for focused adapters and examples after contracts are fixed.

## Requirement Analysis

- **Problem statement**: v2.1 has native adapter shells and one-dispatcher scheduling but cannot configure or route different tasks across Claude, Codex, and Antigravity, cannot map reasoning tiers to concrete local models, cannot trip model-scoped circuit breakers, and cannot automatically return review findings to the implementation worker.
- **Success criteria**:
  - Setup previews and atomically writes complete portable routing plus local provider configuration.
  - Plans carry configurable `provider_role` and `reasoning`; orchestration produces a concrete assignment preview.
  - Runtime selects a healthy provider/model, queues on concurrency saturation, and performs same-tier fallback when circuit/health failures occur.
  - Native adapters invoke supported non-interactive CLI forms and normalize provider failures without leaking prompt, credentials, or full commands.
  - Review findings use fresh context, return to the original route when possible, and stop after three cycles for human decision.
  - Full examples, migration, packaging, and end-to-end fake CLI tests remain synchronized with production loaders.
- **Constraints**: The deterministic setup CLI must remain non-interactive; the setup skill asks questions. Exact remaining vendor quota is not queried. Antigravity model selection must be capability-checked because the installed `agy` help may omit `--model` even when release notes advertise it.
- **Non-goals**: live cost optimization, vendor billing APIs, remote worker services, credential management, automatic reasoning downgrade, or replacement of Beads/review ledger.

## Approach Options

### Option 1: Static role mapping

- **Summary**: Resolve every role to one fixed native provider and use one simple fallback.
- **Pros**: Small implementation.
- **Cons**: Cannot safely handle per-model quota, multiple fallbacks, review affinity, or capacity policy.

### Option 2: Policy-based routed dispatcher

- **Summary**: Resolve role/reasoning through config, then select candidates using breaker, health, concurrency, queue, and fallback policy.
- **Pros**: Meets the approved behavior while retaining provider-neutral lifecycle contracts and auditable decisions.
- **Cons**: Adds versioned config, runtime state, native process, and coordination code.

### Option 3: Dynamic cost/quota optimizer

- **Summary**: Score providers using live quota, pricing, quality, and latency data.
- **Pros**: Potentially maximizes subscription utilization.
- **Cons**: Requires unstable vendor telemetry and materially expands scope.

### Recommended Approach

- **Selected option**: Option 2.
- **Reasoning**: It satisfies deterministic routing and fallback without depending on vendor billing APIs, and leaves a clean extension point for future scoring.

## Scope

- **In scope**: v2.2 config/migration, local provider config, setup questionnaire contract, assignment resolution, routed dispatch, circuit breaker, native CLI runners, registry integration, review coordinator, examples/docs, packaging and tests.
- **Out of scope**: release publishing, push, real paid model invocations in tests, querying remaining quota, and changing unrelated lifecycle methodology.

## File Structure

| Path | Responsibility |
| --- | --- |
| `workflow_core/provider_config.py` | Parse/validate gitignored executable and model mappings. |
| `workflow_core/assignments.py` | Provider-role/reasoning models, candidate resolution, assignment manifests. |
| `workflow_providers/circuit_breaker.py` | Atomic provider+model breaker state and transitions. |
| `workflow_providers/native_cli.py` | Process runner, capability/health checks, redaction, failure classification. |
| `workflow_providers/routed_worker.py` | Candidate selection, queue/fallback, actual-route evidence, adapter delegation. |
| `workflow_core/review_coordinator.py` | Review request, finding/revision affinity, cycle limits, closure gate. |
| `examples/config.full.yaml` | Schema-tested portable routing example. |
| `examples/providers.local.example.yaml` | Schema-tested local native-provider example. |

## Public Interfaces

```python
@dataclass(frozen=True)
class ProviderModelConfig:
    provider: str
    executable: str
    models: Mapping[str, str]

@dataclass(frozen=True)
class AssignmentRequest:
    task_id: str
    provider_role: str
    reasoning: str
    main_harness: str

@dataclass(frozen=True)
class RouteCandidate:
    provider: str
    model: str
    fallback: bool

def load_provider_local_config(repository: Path) -> Mapping[str, ProviderModelConfig]: ...
def resolve_assignment(request: AssignmentRequest, config: EffectiveConfig,
                       local: Mapping[str, ProviderModelConfig]) -> tuple[RouteCandidate, ...]: ...
```

```python
class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"

class FailureKind(str, Enum):
    QUOTA = "quota"
    RATE_LIMIT = "rate_limit"
    AUTH = "auth"
    SERVICE = "service"
    TIMEOUT = "timeout"
    CLI_CRASH = "cli_crash"
    TASK = "task"
    INVALID_RESULT = "invalid_result"

class RoutedWorkerDispatcher:
    def dispatch(self, request: WorkerRequest) -> WorkerReceipt: ...
    def collect_result(self, worker_id: str, timeout: float | None = None) -> WorkerResult: ...

@dataclass(frozen=True)
class RoutedWorkerReceipt(WorkerReceipt):
    provider_name: str = ""
    model_alias: str = ""
```

## Tasks

### Track 1: Add v2.2 routing and machine-local provider configuration

- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/provider_config.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/configuration.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/schemas.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/setup_service.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/cli.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/migrations.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/bundles.py`
  - Modify `.gitignore`
  - Create `tests/workflow_core/test_provider_config.py`
  - Modify `tests/workflow_core/test_configuration.py`
  - Modify `tests/workflow_core/test_setup_cli.py`
  - Modify `tests/workflow_core/test_migrations.py`
  - Modify `tests/workflow_core/test_bundles.py`
- **Model class**: `high_reasoning`
- **Produces**: `ProviderModelConfig`, `ProviderLocalConfigError`, `load_provider_local_config(repository)`, `validate_provider_local_config(value)`, v2.2 routing schema and 2.1→2.2 migration.
- **Acceptance criteria**:
  - Portable config validates roles, ordered preferred/fallback providers, concurrency, queue, worker, breaker, and review policy.
  - Local config requires an executable plus exactly `low`, `medium`, and `high` non-empty aliases for every enabled provider.
  - `init/configure --dry-run` returns both complete portable and local proposals without writing; approved calls stage every file before mutation.
  - `--set KEY=VALUE` addresses portable config and repeatable `--provider-set KEY=VALUE` addresses machine-local provider config; `init`, `configure`, and `update` preserve those namespaces in dry-run and approved calls.
  - `.agent-workflow/providers.local.yaml` is gitignored and excluded from bundle export.
  - Migration backs up 2.1 config, advances all three version channels, and does not invent cross-harness mappings.
- [ ] **Step 1: Write failing local-config and v2.2 schema tests**

```python
def test_local_provider_config_requires_all_reasoning_tiers(self):
    with self.assertRaisesRegex(ProviderLocalConfigError, "missing model tier: high"):
        validate_provider_local_config({
            "schema_version": "2.2",
            "providers": {"claude": {"executable": "claude", "models": {"low": "haiku", "medium": "sonnet"}}},
        })

def test_update_dry_run_previews_portable_and_local_assignments(self):
    result = run_setup("update", "--set", "routing.roles.backend.preferred=[claude]", "--provider-set", "providers.claude.models.high=opus", "--dry-run")
    self.assertEqual("migration_available", result["status"])
    self.assertIn("routing", result["configuration"])
    self.assertEqual("opus", result["provider_configuration"]["providers"]["claude"]["models"]["high"])

def test_portable_config_rejects_fallback_to_unknown_provider(self):
    config = routing_config(fallback=["missing-provider"])
    with self.assertRaisesRegex(ConfigValidationError, "unknown routing provider"):
        validate_portable_config(config)
```

- [ ] **Step 2: Run focused tests and confirm failures**

Run: `python3 -m unittest tests.workflow_core.test_provider_config tests.workflow_core.test_configuration -v`

Expected: import/schema failures for the new local config and routing fields.

- [ ] **Step 3: Implement local config models, routing schema, and cross-layer validation**

```python
def load_provider_local_config(repository: Path) -> Mapping[str, ProviderModelConfig]:
    path = repository.resolve() / ".agent-workflow/providers.local.yaml"
    loaded = _read_yaml(path)
    validate_provider_local_config(loaded)
    return {
        name: ProviderModelConfig(name, entry["executable"], dict(entry["models"]))
        for name, entry in loaded["providers"].items()
    }
```

- [ ] **Step 4: Add setup dry-run/atomic-write and migration tests, then implement them**

Run: `python3 -m unittest tests.workflow_core.test_setup_cli tests.workflow_core.test_migrations tests.workflow_core.test_bundles -v`

Expected after implementation: setup previews both config layers, approved setup writes atomically, 2.1 migration is reversible, and bundles omit local config.

- [ ] **Step 5: Commit Track 1**

```bash
git add .gitignore plugins/gin-workflow/src/scripts/workflow_core tests/workflow_core
git commit -m "feat: add v2.2 routed provider configuration"
```

### Track 2: Add plan guidance, assignment resolution, and preview manifests

- **Dependencies**: Track 1
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/assignments.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_providers/worker_dispatch.py`
  - Modify `plugins/gin-workflow/src/skills/writing-plans/plan-schema.md`
  - Modify `plugins/gin-workflow/src/skills/writing-plans/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/plan/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/orchestrate/SKILL.md`
  - Create `tests/workflow_core/test_assignments.py`
  - Modify `tests/workflow_providers/test_worker_dispatch.py`
- **Model class**: `high_reasoning`
- **Consumes**: Track 1 `ProviderModelConfig` and v2.2 routing config.
- **Produces**: `AssignmentRequest`, `RouteCandidate`, `AssignmentManifest`, `resolve_assignment`, `write_assignment_manifest`; `WorkerRequest.provider_role` plus `reasoning` while retaining a compatibility `model_tier` property.
- **Acceptance criteria**:
  - Plan schema requires `provider_role` and `reasoning` for implementation/review tracks and defines low/medium/high selection guidance.
  - Role resolution preserves preferred/fallback order, expands `main_harness`, deduplicates candidates, and rejects missing mappings.
  - Assignment preview records requested role/tier and concrete candidate aliases under runtime only.
  - Worker payload contains role/reasoning but no concrete provider/model.
- [ ] **Step 1: Write failing assignment-order and payload-boundary tests**

```python
def test_resolver_expands_main_harness_and_preserves_same_tier(self):
    routes = resolve_assignment(
        AssignmentRequest("api", "backend", "high", "codex"), effective, local
    )
    self.assertEqual(
        (("claude", "opus", False), ("codex", "reasoning", True)),
        tuple((r.provider, r.model, r.fallback) for r in routes),
    )

def test_worker_payload_excludes_resolved_provider_and_model(self):
    payload = request(provider_role="backend", reasoning="high").to_payload()
    self.assertNotIn("provider", payload)
    self.assertNotIn("model", payload)
```

- [ ] **Step 2: Run focused tests and confirm failures**

Run: `python3 -m unittest tests.workflow_core.test_assignments tests.workflow_providers.test_worker_dispatch -v`

- [ ] **Step 3: Implement immutable assignment models, resolver, and atomic manifest writer**

```python
def resolve_assignment(request, config, local):
    role = config["routing"]["roles"][request.provider_role]
    names = _ordered_unique((*role["preferred"], *role.get("fallback", ())))
    return tuple(_candidate(name, request, local, index >= len(role["preferred"])) for index, name in enumerate(names))
```

- [ ] **Step 4: Update planning/orchestration skill contracts and run schema text tests**

Run: `python3 -m unittest tests.workflow_core.test_assignments -v`

Expected: manifests are deterministic and plans remain provider-neutral.

- [ ] **Step 5: Commit Track 2**

```bash
git add plugins/gin-workflow/src/scripts/workflow_core/assignments.py plugins/gin-workflow/src/scripts/workflow_providers/worker_dispatch.py plugins/gin-workflow/src/skills tests/workflow_core/test_assignments.py tests/workflow_providers/test_worker_dispatch.py
git commit -m "feat: resolve plan roles into worker assignments"
```

### Track 3: Implement circuit breaker and safe native CLI runners

- **Dependencies**: Track 1
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/circuit_breaker.py`
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/native_cli.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_providers/claude_worker.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_providers/codex_worker.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_providers/antigravity_worker.py`
  - Create `tests/workflow_providers/test_circuit_breaker.py`
  - Create `tests/workflow_providers/test_native_cli.py`
  - Modify `tests/workflow_providers/test_worker_adapters.py`
- **Model class**: `high_reasoning`
- **Produces**: `CircuitBreakerStore`, `CircuitDecision`, `FailureKind`, `NativeCliRunner`, provider-specific argv builders and health/capability checks.
- **Acceptance criteria**:
  - Breaker is keyed by provider/model, persists atomically, uses injectable clock, and fails safe as open after corrupt-state recovery.
  - Quota/rate/auth/service/timeout/crash failures count; task/test/review/invalid-result failures do not.
  - Native invocations are argument arrays with bounded stdin, captured JSON/JSONL output, explicit cwd/timeout, sanitized environment, and no shell.
  - Claude builder uses `claude -p --model <alias> --output-format json --permission-mode acceptEdits`.
  - Codex builder uses `codex exec --model <alias> --json --ephemeral -C <workspace> -` with workspace-write sandbox and non-interactive approval policy.
  - Antigravity builder uses `agy --print --model <alias> --sandbox`; health returns unavailable when installed capability detection cannot verify explicit model selection.
- [ ] **Step 1: Write breaker transition and failure-classification tests with a fake clock**

```python
def test_quota_failure_opens_only_the_selected_model(self):
    store.record_failure("claude", "opus", FailureKind.QUOTA, now=clock.now())
    self.assertEqual(CircuitState.OPEN, store.state("claude", "opus").state)
    self.assertEqual(CircuitState.CLOSED, store.state("claude", "sonnet").state)

def test_task_failure_does_not_trip_breaker(self):
    store.record_failure("claude", "opus", FailureKind.TASK, now=clock.now())
    self.assertEqual(CircuitState.CLOSED, store.state("claude", "opus").state)
```

- [ ] **Step 2: Implement atomic breaker state and run tests**

Run: `python3 -m unittest tests.workflow_providers.test_circuit_breaker -v`

- [ ] **Step 3: Write fake-executable tests for argv, redaction, timeout, cancellation, malformed output, and classified stderr**

```python
def test_claude_argv_selects_model_without_shell(self):
    invocation = build_claude_invocation("claude", "opus", workspace)
    self.assertEqual("claude", invocation.argv[0])
    self.assertEqual("opus", invocation.argv[invocation.argv.index("--model") + 1])
    self.assertFalse(invocation.shell)
```

- [ ] **Step 4: Implement process runner and provider builders; run adapter tests**

Run: `python3 -m unittest tests.workflow_providers.test_native_cli tests.workflow_providers.test_worker_adapters -v`

- [ ] **Step 5: Commit Track 3**

```bash
git add plugins/gin-workflow/src/scripts/workflow_providers tests/workflow_providers
git commit -m "feat: add native workers and model circuit breakers"
```

### Track 4: Route scheduled tasks across providers with capacity and fallback

- **Dependencies**: Tracks 2-3
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/routed_worker.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_providers/registry.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_providers/__init__.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_core/worker_scheduler.py`
  - Modify `plugins/gin-workflow/src/skills/worker-dispatch/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/worker-dispatch/references/worker-lifecycle.md`
  - Create `tests/workflow_providers/test_routed_worker.py`
  - Modify `tests/workflow_providers/test_registry.py`
  - Modify `tests/workflow_core/test_worker_scheduler.py`
- **Model class**: `high_reasoning`
- **Consumes**: assignment candidates, circuit decisions, native adapters, event/evidence stores.
- **Produces**: `RoutedWorkerDispatcher` compatible with scheduler dispatch/status/collect/cancel, per-provider semaphores, queue timeout, actual-route receipts/evidence.
- **Acceptance criteria**:
  - Registry builds routed worker capability only from `EffectiveConfig` plus explicit `ProviderLocalConfig` injection.
  - Open circuits and unhealthy adapters are skipped; unavailable events precede fallback assignment.
  - Full concurrency waits up to `max_wait_seconds` and does not mutate breaker state.
  - Fallback selects the next same-tier candidate and records provider/model alias, reason, and fallback flag.
  - No usable route returns a blocked normalized result and leaves Beads open.
- [ ] **Step 1: Write failing route-order, open-circuit, queue, and all-unavailable tests**

```python
def test_open_primary_routes_to_main_harness_same_tier(self):
    breaker.open("claude", "opus", reason="quota")
    receipt = router.dispatch(request(provider_role="backend", reasoning="high"))
    self.assertEqual(
        ("codex", "reasoning", True),
        (receipt.provider_name, receipt.model_alias, receipt.fallback_used),
    )

def test_saturated_provider_waits_before_fallback_without_opening_breaker(self):
    first = router.dispatch(request(task_id="one"))
    second = router.dispatch(request(task_id="two"))
    self.assertTrue(second.fallback_used)
    self.assertEqual(CircuitState.CLOSED, breaker.state("claude", "opus").state)
```

- [ ] **Step 2: Run focused tests and confirm failures**

Run: `python3 -m unittest tests.workflow_providers.test_routed_worker tests.workflow_core.test_worker_scheduler -v`

- [ ] **Step 3: Implement routed lifecycle delegation, semaphores, queue deadline, and evidence**

```python
class RoutedWorkerDispatcher:
    def dispatch(self, request):
        for candidate in self.resolver(request):
            if self.breakers.allow(candidate) and self._acquire(candidate.provider):
                return self._dispatch_candidate(candidate, request)
        return self._blocked_receipt(request, "worker_routes_unavailable")
```

- [ ] **Step 4: Register capability and run scheduler/registry/provider tests**

Run: `python3 -m unittest tests.workflow_providers.test_routed_worker tests.workflow_providers.test_registry tests.workflow_core.test_worker_scheduler -v`

- [ ] **Step 5: Commit Track 4**

```bash
git add plugins/gin-workflow/src/scripts/workflow_providers plugins/gin-workflow/src/scripts/workflow_core/worker_scheduler.py plugins/gin-workflow/src/skills/worker-dispatch tests/workflow_providers tests/workflow_core/test_worker_scheduler.py
git commit -m "feat: route workers with capacity-aware fallback"
```

### Track 5: Coordinate independent review and revision affinity

- **Dependencies**: Track 4
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_core/review_coordinator.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_providers/contracts.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_providers/review.py`
  - Modify `plugins/gin-workflow/src/skills/cross-agent-code-review/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/requesting-code-review/SKILL.md`
  - Modify `plugins/gin-workflow/src/skills/receiving-code-review/SKILL.md`
  - Create `tests/workflow_core/test_review_coordinator.py`
  - Modify `tests/workflow_providers/test_contracts.py`
- **Model class**: `high_reasoning`
- **Produces**: `ReviewCycle`, `RevisionRequest`, `ReviewCoordinator.request_review`, `ReviewCoordinator.route_revision`, structured finding retrieval and human-decision result.
- **Acceptance criteria**:
  - Implementation result does not close Beads before terminal review and acceptance evidence.
  - Review context contains only approved scope, diff, criteria, tests, and evidence.
  - Independent review rejects the implementation provider unless policy explicitly permits self-review fallback.
  - Findings return with sticky route affinity; open/unavailable original route uses same-role/same-tier fallback.
  - Each revision has a stable identity; the fourth request after three unresolved cycles becomes human decision.
- [ ] **Step 1: Write failing independent-review, affinity, fallback, and cycle-limit tests**

```python
def test_finding_returns_to_original_route(self):
    revision = coordinator.route_revision(cycle_with_original("claude", "opus"), findings)
    self.assertEqual(("claude", "opus"), (revision.provider, revision.model))

def test_fourth_unresolved_cycle_requires_human_decision(self):
    result = coordinator.next_cycle(task_id="api", completed_cycles=3, unresolved=("F-1",))
    self.assertEqual("human_decision_required", result.status)
```

- [ ] **Step 2: Run focused tests and confirm failures**

Run: `python3 -m unittest tests.workflow_core.test_review_coordinator tests.workflow_providers.test_contracts -v`

- [ ] **Step 3: Extend review contracts and implement coordinator state transitions**

```python
@dataclass(frozen=True)
class RevisionRequest:
    task_id: str
    revision_identity: str
    findings: tuple[ReviewFinding, ...]
    provider_role: str
    reasoning: str
    preferred_route: tuple[str, str]
```

- [ ] **Step 4: Update review skills and run ledger/review tests**

Run: `python3 -m unittest discover -s tests/review_ledger -p 'test_*.py' -v`

Expected: existing ledger FSM remains valid and coordinator tests pass.

- [ ] **Step 5: Commit Track 5**

```bash
git add plugins/gin-workflow/src/scripts/workflow_core/review_coordinator.py plugins/gin-workflow/src/scripts/workflow_providers plugins/gin-workflow/src/skills tests/workflow_core/test_review_coordinator.py tests/workflow_providers/test_contracts.py
git commit -m "feat: coordinate routed review revisions"
```

### Track 6: Add setup questionnaire guidance, examples, and user documentation

- **Dependencies**: Tracks 1-5
- **Files**:
  - Create `plugins/gin-workflow/src/examples/config.full.yaml`
  - Create `plugins/gin-workflow/src/examples/providers.local.example.yaml`
  - Modify `plugins/gin-workflow/src/skills/setup/SKILL.md`
  - Modify `plugins/gin-workflow/src/commands/setup.md`
  - Modify `plugins/gin-workflow/src/references/setup-system.md`
  - Modify `plugins/gin-workflow/src/references/capability-provider-contracts.md`
  - Modify `plugins/gin-workflow/src/references/context-and-evidence-policy.md`
  - Modify `docs/setup-system.md`
  - Modify `docs/capability-provider-contracts.md`
  - Modify `docs/context-and-evidence-policy.md`
  - Create `docs/provider-routing.md`
  - Modify `docs/huong-dan-workflow-v2.1.md`
  - Modify `README.md`
  - Create `tests/workflow_core/test_config_examples.py`
- **Model class**: `cheap_simple`
- **Acceptance criteria**:
  - Setup skill asks the approved nine question groups one at a time, feeds exact assignments to dry-run, displays both proposed config layers, and requires approval.
  - Examples load with production validators and demonstrate Claude backend, Antigravity frontend, Codex review, main-harness fallback, circuit breaker, concurrency, and review limits.
  - Docs explain provider roles, reasoning tiers, model aliases, CLI prerequisites, health checks, dry-run/configure/update/rollback, failure classes, blocked tasks, and privacy boundaries.
- [ ] **Step 1: Write failing example-loader tests**

```python
def test_full_examples_validate_with_production_loaders(self):
    validate_portable_config(load_yaml(EXAMPLES / "config.full.yaml"))
    validate_provider_local_config(load_yaml(EXAMPLES / "providers.local.example.yaml"))
```

- [ ] **Step 2: Add examples and documentation, then run validators**

Run: `python3 -m unittest tests.workflow_core.test_config_examples -v`

- [ ] **Step 3: Verify source/reference parity and setup question coverage**

Run: `python3 -m unittest tests.workflow_core.test_setup_cli tests.workflow_core.test_config_examples -v`

- [ ] **Step 4: Commit Track 6**

```bash
git add plugins/gin-workflow/src/examples plugins/gin-workflow/src/skills/setup plugins/gin-workflow/src/commands/setup.md plugins/gin-workflow/src/references docs README.md tests/workflow_core/test_config_examples.py
git commit -m "docs: explain routed native worker setup"
```

### Track 7: Add end-to-end, packaging, and regression verification

- **Dependencies**: Tracks 1-6
- **Files**:
  - Modify `tests/workflow_core/test_end_to_end.py`
  - Modify `tests/workflow_providers/test_harness_packaging.py`
  - Modify `tests/install_smoke_test.sh`
  - Modify `install.sh` only if packaging tests expose missing examples/modules
- **Model class**: `high_reasoning`
- **Acceptance criteria**:
  - Fake native CLI end-to-end test covers Claude/Opus backend, Antigravity/Flash frontend, Claude quota failure, Codex high fallback, Codex review finding, revision, approval, evidence completion, and Bead closure gate.
  - No test invokes a paid model or uses real credentials.
  - Plugin packaging includes every new core/provider module, skill/reference, and example for Claude, Codex, and Antigravity.
  - Existing setup, provider, workflow, review ledger, installer, and security tests pass.
- [ ] **Step 1: Write the failing fake-CLI end-to-end scenario**

```python
def test_cross_harness_fallback_review_and_revision(self):
    outcome = scenario.run()
    self.assertEqual("codex", outcome.backend.actual_provider)
    self.assertEqual("antigravity", outcome.frontend.actual_provider)
    self.assertEqual("open", outcome.breakers[("claude", "opus")])
    self.assertEqual("approved", outcome.review.state)
    self.assertTrue(outcome.evidence_complete)
```

- [ ] **Step 2: Run the new scenario and fix only integration defects**

Run: `python3 -m unittest tests.workflow_core.test_end_to_end -v`

- [ ] **Step 3: Run all Python tests**

Run: `python3 -m unittest discover -s tests -p 'test_*.py' -v`

Expected: all tests pass with no real native model invocation.

- [ ] **Step 4: Run installer and packaging smoke tests**

Run: `bash tests/install_smoke_test.sh`

Expected: all three harness packages contain new routing modules, skills, references, and examples.

- [ ] **Step 5: Run repository health and handoff checks**

Run: `bd doctor --check=conventions`

Run: `git status --short`

Expected: no unexpected files; only planned implementation/config/tracking changes remain.

- [ ] **Step 6: Commit Track 7**

```bash
git add tests install.sh
git commit -m "test: verify cross-harness routed workflow"
```

## Integration

- **Branch**: current feature branch; do not create or switch worktrees until execution starts under `using-git-worktrees` policy.
- **Merge strategy**: sequential for Tracks 1→2/3→4→5; Track 6 follows stable contracts; Track 7 integrates all work.
- **Commit policy**: one reviewed commit per track as listed; do not push without separate authorization.

## Validation

- [ ] `python3 -m unittest tests.workflow_core.test_provider_config tests.workflow_core.test_configuration tests.workflow_core.test_setup_cli tests.workflow_core.test_migrations tests.workflow_core.test_bundles -v`
- [ ] `python3 -m unittest tests.workflow_core.test_assignments tests.workflow_providers.test_worker_dispatch -v`
- [ ] `python3 -m unittest tests.workflow_providers.test_circuit_breaker tests.workflow_providers.test_native_cli tests.workflow_providers.test_worker_adapters -v`
- [ ] `python3 -m unittest tests.workflow_providers.test_routed_worker tests.workflow_providers.test_registry tests.workflow_core.test_worker_scheduler -v`
- [ ] `python3 -m unittest tests.workflow_core.test_review_coordinator tests.workflow_providers.test_contracts -v`
- [ ] `python3 -m unittest tests.workflow_core.test_config_examples tests.workflow_core.test_end_to_end -v`
- [ ] `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- [ ] `bash tests/install_smoke_test.sh`
- [ ] `bd doctor --check=conventions`
- [ ] `git status --short`

## Risks and Mitigations

- **Native CLI drift**: detect versions/capabilities and mark unsupported adapters unavailable; never guess flags or silently use a default model.
- **Quota classification drift**: keep classification provider-specific and covered by captured fake stderr fixtures; unknown failures do not mutate quota breaker state.
- **Deadlock under concurrency**: use per-provider bounded semaphores, monotonic deadlines, and release in `finally`; cover cancellation and queue expiry.
- **Stale assignment preview**: re-resolve at dispatch and record preview-versus-actual evidence.
- **Local config leakage**: explicit bundle denylist, gitignore, redacted diagnostics, and regression searches for known fixture secrets.
- **Review loops**: stable revision identities, maximum three cycles, then human-decision state.
- **Migration partial writes**: stage portable config, local config, effective config, provenance, and backup before atomic replacement.

## Notes

- Model guidance in this plan is planning metadata, not Beads state.
- Provider role and reasoning are durable plan guidance; concrete provider/model resolution remains runtime/local state.
- `standard_impl` remains the implicit worker model class for implementing this plan, while runtime feature semantics use the separate `low|medium|high` reasoning vocabulary defined by the approved design.
