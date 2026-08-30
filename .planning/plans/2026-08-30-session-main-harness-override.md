# Plan: In-Session Main Harness Override

## Objective
Allow users to temporarily override the `main_harness` for the active session (e.g., when the primary harness like Codex runs out of quota) without altering the permanent repository configuration (`.agent-workflow/config.yaml` or `.agent-workflow/generated/effective-config.yaml`).

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
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- **Problem Statement**: The configured `harness` in `effective-config.yaml` is immutable after setup. If the primary harness hits quota during a session, switching to another harness (e.g. `claude` or `antigravity`) currently requires running `setup`, which mutates the repository's configuration on disk.
- **Success Criteria**:
  1. Users can activate a session-level override via CLI (`gin-workflow setup harness-override --harness <name>`) or environment variable (`GIN_WORKFLOW_HARNESS_OVERRIDE`).
  2. `load_effective_config()` dynamically applies the session override to `EffectiveConfig["harness"]` in memory.
  3. Disk configuration (`config.yaml` and `effective-config.yaml`) remains untouched.
  4. Routing candidates with `"main_harness"` resolve to the overridden harness.
  5. The override is visibly acknowledged in state inspect outputs and audit event logs.
  6. A reset command (`gin-workflow setup harness-override --reset`) clears the override.
- **Constraints**:
  - Overridden harness must be a valid, supported provider (`claude`, `codex`, `antigravity`).
  - No secret keys, credentials, or concrete model names may be recorded in portable config.
- **Non-Goals**:
  - Permanent configuration edits (that remains under `gin-workflow setup configure`).

## Approach Options
### Option 1: Env Var + Gitignored Runtime Override File Layer in `load_effective_config()`
- **Summary**: `load_effective_config()` checks for `GIN_WORKFLOW_HARNESS_OVERRIDE` or `.agent-workflow/runtime/session-harness.override`. If present, it validates the candidate harness name and overrides `config["harness"]` in memory when constructing `EffectiveConfig`.
- **Pros**:
  - Surgical and clean.
  - Zero disk mutations to repository `config.yaml` or `effective-config.yaml`.
  - Works seamlessly across CLI invocations and subagents reading the same runtime dir / env.
  - Easy to clear or inspect via helper command.
- **Cons**: None.

### Recommended Approach
- **Selected option**: Option 1 (Env Var + Gitignored Runtime File Layer in `load_effective_config()`).

## Scope
- **In scope**:
  - Runtime override resolution logic in `workflow_core/configuration.py`.
  - CLI subcommand and setup service action `harness-override` in `setup_service.py` & `cli.py`.
  - `AssignmentRequest` candidate resolution verifying `"main_harness"` maps to the temporary harness.
  - Audit logging / status visibility in `lifecycle_cli.py`.
  - Comprehensive unit tests and documentation updates.
- **Out of scope**:
  - Modifying permanent configuration files (`.agent-workflow/config.yaml`).

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Linear implementation across configuration loader, setup service CLI, lifecycle state visibility, and tests.
```

## Tasks

### Track 1: Runtime Harness Override Loader & Resolution
- **Dependencies**: none
- **Files**:
  - [configuration.py](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/workflow_core/configuration.py)
  - [models.py](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/workflow_core/models.py)
- **Provider role**: `general`
- **Reasoning**: `medium`
- **Acceptance criteria**:
  - `load_effective_config()` checks `GIN_WORKFLOW_HARNESS_OVERRIDE` env var and `.agent-workflow/runtime/session-harness.override`.
  - If set, validates that the override harness is a supported provider (`claude`, `codex`, `antigravity`).
  - Sets `config["harness"]` to the override harness and populates `config["_session_harness_override"]` metadata.
  - `effective-config.yaml` on disk remains unmodified.
- **Estimated complexity**: medium

### Track 2: Setup Service & CLI Helper Command
- **Dependencies**: Track 1
- **Files**:
  - [setup_service.py](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/workflow_core/setup_service.py)
  - [cli.py](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/workflow_core/cli.py)
- **Provider role**: `general`
- **Reasoning**: `medium`
- **Acceptance criteria**:
  - `gin-workflow setup harness-override --harness <name>` writes `.agent-workflow/runtime/session-harness.override`.
  - `gin-workflow setup harness-override --reset` removes `.agent-workflow/runtime/session-harness.override`.
  - Input validation rejects unknown harness names with structured error.
- **Estimated complexity**: medium

### Track 3: Event Logging & Lifecycle State Integration
- **Dependencies**: Track 1, Track 2
- **Files**:
  - [lifecycle_cli.py](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/workflow_core/lifecycle_cli.py)
  - [registry.py](file:///home/gin/gin-workflow/plugins/gin-workflow/src/scripts/workflow_providers/registry.py)
- **Provider role**: `general`
- **Reasoning**: `medium`
- **Acceptance criteria**:
  - `gin-workflow state` output includes active harness override status if present.
  - Audit event logged when session override is detected or applied during routing.
  - `AssignmentRequest` expands `"main_harness"` candidates to the overridden harness name.
- **Estimated complexity**: medium

### Track 4: Verification, Test Suite & Documentation
- **Dependencies**: Track 1, Track 2, Track 3
- **Files**:
  - `tests/workflow_core/test_configuration.py`
  - `tests/workflow_core/test_assignments.py`
  - `tests/workflow_core/test_cli.py`
  - `docs/provider-routing.md`
  - `docs/setup-system.md`
- **Provider role**: `docs`
- **Reasoning**: `low`
- **Acceptance criteria**:
  - Unit tests pass for env override, file override, reset, and assignment resolution.
  - All existing workflow core and provider test suites pass.
  - Documentation updated with session harness override usage.
- **Estimated complexity**: low

## Integration
- **Branch**: main
- **Merge strategy**: sequential

## Validation
- [ ] `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest discover -s tests -p "test_*.py"` passes 100%.
- [ ] `gin-workflow setup harness-override --harness claude` sets runtime override.
- [ ] `gin-workflow state` acknowledges `claude` as active harness override.
- [ ] `gin-workflow setup harness-override --reset` removes runtime override.
- [ ] `.agent-workflow/config.yaml` and `.agent-workflow/generated/effective-config.yaml` remain unmodified throughout.

## Notes
- Session harness override state lives strictly in memory and gitignored `.agent-workflow/runtime/session-harness.override`.
- All portable assignment roles naming `"main_harness"` dynamically route to the active session harness override.
