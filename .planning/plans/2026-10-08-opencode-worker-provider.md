# Plan: OpenCode worker provider

Spec: `.planning/specs/2026-10-08-opencode-worker-provider-design.md`

## Objective
`opencode` is a routed provider like `codex`/`antigravity`: worker, independent reviewer, main harness, configurable and health-checked through setup. Success = the spec's US-1..US-3 acceptance criteria pass under `python -m pytest tests` with a fake `NativeCliRunner` (no real OpenCode in CI).

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`: plan `standard_impl`, implement `standard_impl`, verify `standard_impl`, review `high_reasoning`, docs `cheap_simple`

## Requirement Analysis
- Problem statement: OpenCode only installs skills; routing, dispatch, review, and setup cannot use it as a provider.
- Success criteria: spec Requirements 1-11 satisfied; existing claude/codex/antigravity tests still pass unchanged.
- Constraints (verbatim from spec): out of scope are PreToolUse/PostToolUse hooks for OpenCode, a shared table-driven adapter refactor, and putting `~/.opencode/bin` on `PATH`. OpenCode has no `--cd`/`--add-dir` (cwd is the workspace) and no sandbox flag; isolation relies on the worktree and cwd. `provider_default` stays rejected for `claude` and `codex`. Existing behaviour of the other providers is unchanged.
- Non-goals: the three out-of-scope items above.

## Approach Options
### Option 1: dedicated `opencode_worker.py` mirroring `antigravity_worker.py`
- Pros: smallest diff, existing pattern, no change to working adapters.
- Cons: a fourth near-copy adapter.
### Option 2: table-driven shared adapter
- Pros: less duplication long-term.
- Cons: touches three working adapters; YAGNI.
### Recommended Approach
- Selected option: 1. Generalise only the `== "antigravity"` provider_default checks into one constant.

## Scope
- In scope: spec Requirements 1-11.
- Out of scope: see Constraints.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Three dependent tracks touching shared provider modules; three or fewer tasks, so sequential in-session execution.
```

## Tasks

### Track 1: OpenCode adapter, health, and output parsing
- **Dependencies**: none
- **Files**:
  - Create `plugins/gin-workflow/src/scripts/workflow_providers/opencode_worker.py`
  - Modify `plugins/gin-workflow/src/scripts/workflow_providers/native_cli.py` (`direct_worker_result` ~L152-166, `sanitized_environment` ~L85-100, `classify_native_failure` ~L183-206)
  - Modify `tests/workflow_providers/test_worker_adapters.py`
  - Create `tests/workflow_providers/test_opencode_worker.py`
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Interfaces produced**: `build_opencode_invocation(executable: str, model: str, workspace: Path, prompt: str, *, timeout_seconds: float = 900) -> NativeCliInvocation`; `opencode_health(executable: str, *, help_text: str | None = None, model: str | None = None, native_runner: NativeCliRunner | None = None, workspace: Path | None = None) -> NativeHealth`; `class OpenCodeWorkerAdapter(SynchronousWorkerAdapter)` with `provider_name = "opencode"` and the same constructor keywords as `AntigravityWorkerAdapter`.
- **Acceptance criteria**: argv/health/result tests below pass; `direct_worker_result` returns the contract object from an OpenCode `{"type":"text","part":{"text":"..."}}` record; Antigravity/Codex/Claude tests unchanged.
- **Estimated complexity**: medium

Steps:
1. Capture real failure text first (needed for `classify_native_failure`):
   ```
   cd /tmp && mkdir -p ocprobe && cd ocprobe
   ~/.opencode/bin/opencode run --standalone --auto --format json --model nonexistent/model "ok" ; echo "exit=$?"
   ~/.opencode/bin/opencode run --standalone --auto --format json --model github-copilot/does-not-exist "ok" ; echo "exit=$?"
   ```
   Record both outputs in the test as string constants (`OPENCODE_INVALID_MODEL_TEXT`). If the text already contains a token matched by `classify_native_failure` ("invalid model", "unknown model", "not a valid model", "not found" is NOT matched), add the observed phrase to the `INVALID_MODEL` token tuple; otherwise leave it. Quota/auth phrases: add only phrases actually observed, never guessed.
2. Write failing tests in `tests/workflow_providers/test_opencode_worker.py` (same `sys.path` header and `request()`/`result()` helpers as `test_worker_adapters.py`; import them with `from test_worker_adapters import request, result` if the directory is on the path, else copy the two helpers):
   ```python
   class FakeRunner:
       def __init__(self, records=None):
           self.invocations = []
           self.records = records
       def run(self, invocation, *, cancel_event=None):
           self.invocations.append(invocation)
           return NativeCliOutput(self.records or ({"type": "text", "part": {"text": json.dumps(result())}},))

   class OpenCodeWorkerTests(unittest.TestCase):
       def test_explicit_model_argv(self):
           runner = FakeRunner()
           adapter = OpenCodeWorkerAdapter(native_runner=runner, executable="opencode",
                                           model="github-copilot/claude-sonnet-5.5", workspace=Path.cwd())
           receipt = adapter.dispatch(request())
           self.assertEqual("completed", adapter.collect_result(receipt.worker_id).status)
           argv = runner.invocations[0].argv
           self.assertEqual(("opencode", "run", "--standalone", "--auto", "--format", "json",
                             "--model", "github-copilot/claude-sonnet-5.5"), argv[:8])
           self.assertEqual(Path.cwd().resolve(), runner.invocations[0].cwd)

       def test_provider_default_omits_model(self):
           runner = FakeRunner()
           adapter = OpenCodeWorkerAdapter(native_runner=runner, executable="opencode",
                                           model="provider_default", workspace=Path.cwd())
           adapter.dispatch(request())
           self.assertNotIn("--model", runner.invocations[0].argv)

       def test_health_requires_flags(self):
           self.assertFalse(opencode_health("opencode", help_text="--auto --format").available)
           self.assertTrue(opencode_health("opencode", help_text="--auto --format --model").available)

       def test_health_reports_invalid_model(self):
           class Boom:
               def run(self, invocation, *, cancel_event=None):
                   raise NativeCliError(FailureKind.INVALID_MODEL, "unknown model")
           health = opencode_health("opencode", help_text="--auto --format --model",
                                    model="x/y", native_runner=Boom(), workspace=Path.cwd())
           self.assertEqual("invalid_model", health.reason)
           self.assertFalse(health.available)

       def test_invalid_output_is_invalid_result(self):
           with self.assertRaises(NativeCliError):
               direct_worker_result(NativeCliOutput(({"type": "text", "part": {"text": "no json"}},)))

       def test_invalid_model_text_classified(self):
           self.assertIs(FailureKind.INVALID_MODEL, classify_native_failure(OPENCODE_INVALID_MODEL_TEXT))
   ```
   Run: `python -m pytest tests/workflow_providers/test_opencode_worker.py -q` → fails (ImportError).
3. Create `opencode_worker.py`:
   ```python
   """OpenCode native-harness worker bridge (no cloud SDK dependency)."""

   from __future__ import annotations

   from pathlib import Path
   import re
   from typing import Any, Callable, Mapping

   from workflow_core.provider_config import PROVIDER_DEFAULT

   from .circuit_breaker import FailureKind
   from .native_cli import (
       MODEL_PROBE_PROMPT, MODEL_PROBE_TIMEOUT_SECONDS, NativeCliError, NativeCliInvocation,
       NativeCliRunner, NativeHealth, native_cancellable_dispatch, native_worker_payload, probe_help,
   )
   from .worker_dispatch import SynchronousWorkerAdapter, WorkerResult


   def build_opencode_invocation(executable, model, workspace, prompt, *, timeout_seconds=900):
       resolved_workspace = Path(workspace).resolve()
       argv = [executable, "run", "--standalone", "--auto", "--format", "json"]
       if model and model != PROVIDER_DEFAULT:
           argv.extend(["--model", model])
       argv.append(prompt)
       return NativeCliInvocation(tuple(argv), resolved_workspace, b"", timeout_seconds)


   def opencode_health(executable, *, help_text=None, model=None, native_runner=None, workspace=None):
       help_text = probe_help(executable, "run", "--help") if help_text is None else help_text
       if help_text is None:
           return NativeHealth(False, "executable_or_help_unavailable", False)
       options = frozenset(re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", help_text))
       supported = "--model" in options
       if "--auto" not in options or "--format" not in options:
           return NativeHealth(False, "required_flags_unverified", supported)
       health = NativeHealth(True, "ready" if supported else "explicit_model_selection_unverified", supported)
       if not supported or model is None or model == PROVIDER_DEFAULT or native_runner is None or workspace is None:
           return health
       try:
           native_runner.run(build_opencode_invocation(
               executable, model, workspace, MODEL_PROBE_PROMPT, timeout_seconds=MODEL_PROBE_TIMEOUT_SECONDS))
       except NativeCliError as error:
           if error.kind is FailureKind.INVALID_MODEL:
               return NativeHealth(False, "invalid_model", supported)
       return health


   class OpenCodeWorkerAdapter(SynchronousWorkerAdapter):
       provider_name = "opencode"

       def __init__(self, native_dispatch=None, *, native_runner=None, executable=None, model=None,
                    workspace=None, timeout_seconds=900):
           cancellable_dispatch = None
           if native_dispatch is None and all((native_runner, executable, model, workspace)):
               cancellable_dispatch = native_cancellable_dispatch(
                   native_runner,
                   lambda prompt: build_opencode_invocation(
                       str(executable), str(model), Path(workspace), prompt, timeout_seconds=timeout_seconds),
               )
           super().__init__(
               native_dispatch,
               available=native_dispatch is not None or cancellable_dispatch is not None,
               payload_factory=native_worker_payload,
               cancellable_runner=cancellable_dispatch,
           )
   ```
   (Keep the type hints of `antigravity_worker.py` when copying; the above elides them for length only.)
4. In `native_cli.py` `direct_worker_result`, after `item = record.get("item")` handling add the OpenCode shape:
   ```python
   part = record.get("part")
   if isinstance(part, Mapping):
       candidates.append(part.get("text"))
   ```
   In `sanitized_environment` add `"XDG_DATA_HOME"` to `allowed` (OpenCode keeps its login under the XDG data dir).
5. Run `python -m pytest tests/workflow_providers -q` → all pass. Commit on the feature branch: `feat(providers): add OpenCode worker adapter`.

### Track 2: Provider wiring (enums, provider_default, registry, setup, resolver, list-models)
- **Dependencies**: Track 1
- **Files**:
  - Modify `workflow_core/provider_config.py` (add constant ~L17; check ~L159)
  - Modify `workflow_core/assignments.py` (L57-59, L192-193)
  - Modify `workflow_providers/registry.py` (imports ~L43; L216-221; factory ~L311; `health_builders` ~L315; L338-339)
  - Modify `workflow_providers/routed_worker.py` (L279)
  - Modify `workflow_core/cli.py` (L28, L48), `configuration.py` (L229), `project_detect.py` (L200), `setup_service.py` (L82, L379-420)
  - Modify `workflow_core/executable_resolver.py` (`COMMON_INSTALL_DIRS`)
  - Modify `workflow_providers/native_cli.py` (`_LIST_COMMANDS` L499, `list_models` text branch)
  - Tests: `tests/workflow_core/test_provider_config.py`, `test_assignments.py`, `test_executable_resolver.py`, `tests/workflow_providers/test_registry.py`, `test_routed_worker.py`, `test_list_models.py`, `test_review_initialize.py` (review independence)
  (all paths under `plugins/gin-workflow/src/scripts/` unless starting with `tests/`)
- **Provider role**: `backend`
- **Reasoning**: `medium`
- **Interfaces consumed**: Track 1 `OpenCodeWorkerAdapter`, `opencode_health`. **Produced**: `PROVIDER_DEFAULT_PROVIDERS: frozenset[str] = frozenset({"antigravity", "opencode"})` in `workflow_core/provider_config.py`.
- **Acceptance criteria**: spec Requirements 5-8 and 10; US-1, US-2, US-3.
- **Estimated complexity**: medium

Steps:
1. Failing tests first (add to the existing files, mirroring the antigravity cases they already contain):
   - `test_provider_config.py`: an `opencode` block with `low: provider_default`, `high: github-copilot/claude-sonnet-5.5` loads; `selection_mode("low") == "provider_default"`; `claude` with `provider_default` still raises `"provider_default is only supported for antigravity"` (message is kept as a prefix, see step 3).
   - `test_assignments.py`: `RouteCandidate("opencode", "provider_default", False)` is accepted and serialises `selection_mode: provider_default`; `RouteCandidate("codex", "provider_default", False)` raises.
   - `test_executable_resolver.py`: with `HOME` patched to a temp dir containing `.opencode/bin/opencode` (mode 0755) and `PATH` lacking it, `resolve_harness_executable("opencode", provider="opencode")` returns that path. Patch `executable_resolver.COMMON_INSTALL_DIRS` via `mock.patch.object(module, "COMMON_INSTALL_DIRS", (tmp/".opencode/bin",))` if the constant is evaluated at import time.
   - `test_registry.py`: copy the antigravity `provider_default`/explicit subtest to an `opencode` provider (`executable: opencode`, health override returning `NativeHealth(True, "ready", True)`), assert the dispatch goes to `opencode`; `test_registry_rejects_provider_default_for_non_antigravity_injection` stays green for codex.
   - `test_routed_worker.py`: an explicit-model `opencode` candidate whose health reports `explicit_model_selection=False` is skipped as `explicit_model_selection_unsupported`.
   - `test_list_models.py`:
     ```python
     OPENCODE_TEXT = "github-copilot/claude-sonnet-5.5\ngithub-copilot/gemini-3.6-flash\n"
     def test_opencode_lines_are_ids(self):
         models = list_models("opencode", runner=runner_for(OPENCODE_TEXT), which=FOUND)
         self.assertEqual(["github-copilot/claude-sonnet-5.5", "github-copilot/gemini-3.6-flash"], [m["id"] for m in models])
         self.assertEqual([], models[0]["reasoning_levels"])
     ```
   - Review independence (`test_review_initialize.py` or the nearest existing independence test): with `independence: provider`, implementer `claude` + reviewer `opencode` accepted; implementer `opencode` + reviewer `opencode` rejected. If an existing test already covers "same provider rejected", parametrise it with `opencode` rather than adding a new one.
   Run each file → fails.
2. `provider_config.py`: after `PROVIDER_DEFAULT = "provider_default"` add `PROVIDER_DEFAULT_PROVIDERS = frozenset({"antigravity", "opencode"})`; change `if name != "antigravity":` to `if name not in PROVIDER_DEFAULT_PROVIDERS:`.
3. Replace every `!= "antigravity"` provider_default guard with `not in PROVIDER_DEFAULT_PROVIDERS` in `assignments.py` (two sites), `registry.py` L216, and change each message to `"provider_default is only supported for antigravity and opencode"` (the old message is a substring, so existing `assertRaisesRegex` tests still match). `routed_worker.py` L279: `candidate.provider == "antigravity"` → `candidate.provider in PROVIDER_DEFAULT_PROVIDERS` (the explicit-selection check applies to both). `registry.py` L338-339: `if provider in ("claude","codex","antigravity")` → add `"opencode"`; `provider == "antigravity" and model == PROVIDER_DEFAULT` → `provider in PROVIDER_DEFAULT_PROVIDERS and ...`. Import the constant where `PROVIDER_DEFAULT` is already imported.
4. `registry.py`: import `OpenCodeWorkerAdapter, opencode_health`; factory `if candidate.provider == "opencode": return OpenCodeWorkerAdapter(**options)`; `health_builders["opencode"] = opencode_health`.
5. Enums: add `"opencode"` to `cli.py` L28 and L48, `configuration.py` `SUPPORTED_HARNESSES`, `project_detect.py` L200 tuple, `setup_service.py` L82 (`("opencode", ".opencode")`), and the setup probe block at L378-420 (import `opencode_health`, add to `probe_builders`, treat `provider in PROVIDER_DEFAULT_PROVIDERS and model == PROVIDER_DEFAULT` as the no-probe branch).
6. `executable_resolver.py`: add `Path.home() / ".opencode/bin",` to `COMMON_INSTALL_DIRS`.
7. `native_cli.py`: `_LIST_COMMANDS["opencode"] = ("models",)`; in the text branch of `list_models`, before the `"\t" not in line` skip, add:
   ```python
   if provider == "opencode":
       return [{"id": line.strip(), "label": line.strip(), "description": "", "reasoning_levels": []}
               for line in completed.stdout.splitlines() if line.strip()]
   ```
   placed right after the codex branch.
8. Run `python -m pytest tests -q` → all pass. Commit: `feat(providers): wire OpenCode into routing, registry, and setup`.

### Track 3: Docs
- **Dependencies**: Track 2
- **Files**: `docs/concepts/providers.md`, `docs/reference/config.md`, `plugins/gin-workflow/src/examples/providers.local.example.yaml`, `docs/reference/troubleshooting.md` (L27), `README.md`, `docs/advanced/multi-agent-routing.md`, `docs/concepts/architecture.md`
- **Provider role**: `docs`
- **Reasoning**: `low`
- **Acceptance criteria**: no doc claims there is no OpenCode worker adapter; every list of `claude`/`codex`/`antigravity` providers includes OpenCode; the no-sandbox / `--auto` risk is stated.
- **Estimated complexity**: low

Steps:
1. `providers.local.example.yaml`: add
   ```yaml
     opencode:
       executable: opencode
       models:
         low: provider_default
         medium: provider_default
         high: provider_default
   ```
2. `providers.md`: first paragraph lists `opencode`; health row adds `opencode run --help` (`--auto`, `--format`, `--model`); the sentence "For Antigravity only, a tier may be `provider_default`" becomes "For Antigravity and OpenCode"; add one paragraph: OpenCode has no sandbox flag and `--auto` auto-approves permissions, so isolation relies on the worktree and working directory, like Codex's bypass flag.
3. `troubleshooting.md` L27: replace "there is no OpenCode worker adapter" with "OpenCode also runs routed workers (`opencode run --auto --format json`); it has no sandbox, see Providers." Keep the PATH note: the resolver also checks `~/.opencode/bin`.
4. `config.md`, `README.md`, `multi-agent-routing.md`, `architecture.md`: add OpenCode where the other three providers are enumerated (`git grep -n -i antigravity -- <file>` to find each site).
5. Run `python -m pytest tests -q` (docs tests, if any) and `git grep -n "no OpenCode worker adapter"` → no matches. Commit: `docs: document OpenCode as a routed provider`.

## Integration
- **Branch**: `feat/opencode-worker-provider`
- **Merge strategy**: sequential

## Validation
- [ ] `python -m pytest tests -q` passes (all prior tests unchanged)
- [ ] `git grep -n '== "antigravity"' plugins/gin-workflow/src/scripts` shows no remaining provider_default guard
- [ ] Optional manual: `~/.opencode/bin/opencode run --standalone --auto --format json "reply ok"` output parses via `direct_worker_result` shape (`part.text`)

## Notes
- Concrete models appear only in tests/docs examples, never in the portable plan.
- Parent Bead stays open until the human-confirmed merge; track beads close after tests and review.
