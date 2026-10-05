# Plan: Provider routing and launcher fixes

## Goal

Fix four bugs found while shipping gin-workflow-f7g. No provider model names are hard-coded; real models are chosen through `gin-workflow setup models`. No new dependencies.

## Architecture

Four independent, file-disjoint fixes on one branch: installer package list (q15), worker-result parsing in `native_cli.py` (up4), review workspace fallback and workspace error reason in `registry.py`/`routed_worker.py` (cij), and stdout-aware failure classification in `native_cli.py` (vlc.1). Tracks 2 and 4 touch different functions in `native_cli.py`, so they run sequentially.

## Tech Stack

Bash, PowerShell, Python 3 standard library, `unittest`. No new tooling.

## Global Constraints

Copied from `.planning/specs/2026-10-05-provider-routing-fixes-design.md`: gin-qa still installs only `gin_qa`; PowerShell is checked statically only (pwsh not installed); pure-JSON results and records parse unchanged and no contract-satisfying object still raises `INVALID_RESULT`; implementation workers still require an isolated worktree; workspace failures record no circuit-breaker failure; no concrete model names are added.

## Model Guidance

- `default_model_class`: `standard_impl`; review `high_reasoning`.

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Four small bounded tracks; tracks 2 and 4 share native_cli.py.
```

Worktree `.planning/worktrees/gin-workflow-vlc`, branch `fix/provider-routing-vlc`. Each track bead closes after its tests and independent review (role `review`, reasoning `high`, provider different from the implementer) pass. Parent epic `gin-workflow-vlc` closes after the user-approved merge to master.

Commands: `T=PYTHONPATH=plugins/gin-workflow/src/scripts:tests python3 -m unittest`; full suite `PYTHONPATH=plugins/gin-workflow/src/scripts python3 -m unittest tests/test_all.py` (baseline 836 OK, skipped 3).

## Tasks

### Track 1: Install all gin-workflow packages with the launcher (gin-workflow-q15)

- **Dependencies**: none. **Provider role**: `general`. **Reasoning**: `low`. **Complexity**: low.
- **Files**: `install.sh` (`install_launcher`), `install.ps1` (`Install-Launcher`), `tests/install_smoke_test.sh` (installed launcher block near `specs --help`).
- **Interfaces**: Bash `packages` (space-separated list) replaces the single `package`; PowerShell `$packages` array replaces `$package`.
- **Steps**:
  1. In the smoke test, after the installed `specs --help` call, add `HOME="$MOCK_HOME" "$MOCK_HOME/.local/bin/gin-workflow" setup models --provider claude >/dev/null` (under the existing `set -e` regime, so a failure fails the test). Run `bash tests/install_smoke_test.sh`; expect failure with `ModuleNotFoundError: No module named 'workflow_providers'`.
  2. `install.sh`: `gin-workflow) packages="workflow_core workflow_providers review_ledger" ;;`, `gin-qa) packages=gin_qa ;;`; loop `for package in $packages; do mkdir -p "$install_dir/$package"; cp -rf "$source_dir/$package/." "$install_dir/$package/"; done` in place of the single mkdir/cp for the package (keep the other mkdirs and copies).
  3. `install.ps1`: `$packages = if ($Name -eq 'gin-workflow') { @('workflow_core', 'workflow_providers', 'review_ledger') } else { @('gin_qa') }`; `foreach ($package in $packages)` around the existing `New-Directory`/`Copy-DirectoryContent` for the package.
  4. Run `bash -n install.sh tests/install_smoke_test.sh` and `bash tests/install_smoke_test.sh`; expect exit 0. Static read of the PowerShell diff; pwsh not run.
- **Acceptance**: installed launcher runs `setup models`; gin-qa unchanged; smoke passes; review approves.

### Track 2: Parse worker results surrounded by text (gin-workflow-up4)

- **Dependencies**: none. **Provider role**: `backend`. **Reasoning**: `medium`. **Complexity**: low.
- **Files**: `plugins/gin-workflow/src/scripts/workflow_providers/native_cli.py` (`direct_worker_result`); test `tests/workflow_providers/test_worker_adapters.py` or the existing native CLI test module that covers `direct_worker_result` (locate with `grep -rn direct_worker_result tests`).
- **Interfaces**: new private `_contract_object(text: str, required: set[str]) -> Mapping[str, object] | None` returning the last JSON object in `text` that has all `required` keys, scanning with `json.JSONDecoder().raw_decode` from each `{`; `direct_worker_result` uses it for the `result`/`response`/`text` strings and `item.text`.
- **Steps**:
  1. Test: `NativeCliOutput(({"status": "SUCCESS", "response": "Progress line...\n" + json.dumps(result())},))` → `direct_worker_result` returns the contract object; a response with only prose still raises `NativeCliError` with `FailureKind.INVALID_RESULT`. Run; expect the first to fail.
  2. Implement `_contract_object` and use it; keep the record-level `required.issubset(record)` check first.
  3. Run the module tests and the full suite; expect pass.
- **Acceptance**: leading/trailing prose tolerated; no-contract text still fails; review approves.

### Track 3: Review workers outside a worktree, honest workspace reason (gin-workflow-cij)

- **Dependencies**: none. **Provider role**: `backend`. **Reasoning**: `medium`. **Complexity**: medium.
- **Files**: `plugins/gin-workflow/src/scripts/workflow_providers/routed_worker.py`, `plugins/gin-workflow/src/scripts/workflow_providers/registry.py` (`workspace_for`); tests `tests/workflow_providers/test_registry.py`.
- **Interfaces**: `class WorkspaceUnavailableError(RuntimeError)` in `routed_worker.py`; `workspace_for` returns `root.resolve()` when `request.provider_role == "review"` and `workspace_id` is empty, otherwise raises `WorkspaceUnavailableError` (instead of `RegistryError`) on each workspace check; the router's adapter step catches `WorkspaceUnavailableError` before the generic `except`, releases capacity, records no breaker failure, emits `unavailable` with `reason="workspace_unavailable"`, and continues.
- **Steps**:
  1. Tests modeled on `test_worker_uses_authoritative_workspace_record_and_rejects_path_mismatch`: (a) a `review` request with `isolation_policy={}` dispatches through a fake runner whose invocation `cwd` equals the repository root and completes; (b) the existing mismatch test also asserts a `worker.unavailable` event with reason `workspace_unavailable` and that `registry.worker.breakers.state("claude", <model>)` is still closed. Run; expect failure.
  2. Implement. Run `test_registry`, `test_routed_worker`, then the full suite.
- **Acceptance**: review-only dispatch works from the main checkout; implementation workers still rejected; reason visible; no breaker penalty; review approves.

### Track 4: Detect invalid models reported on stdout (gin-workflow-vlc.1)

- **Dependencies**: Track 2 (same file). **Provider role**: `backend`. **Reasoning**: `low`. **Complexity**: low.
- **Files**: `native_cli.py` (`classify_native_failure` call site in `NativeCliRunner.run`, token list); tests in the module that covers `classify_native_failure` (locate with grep).
- **Interfaces**: `classify_native_failure(stderr: str)` unchanged in signature; the call site passes `stderr + "\n" + (_diagnostic_from_stdout(stdout) or "")`; `"not recognized"` added to the invalid-model tokens.
- **Steps**:
  1. Tests: `classify_native_failure` of `model gemini flash 3.7 is not recognized as a known model` → `INVALID_MODEL`; a runner fixture process exiting non-zero with stdout JSON `{"type":"error","error":{"message":"The 'sol' model is not supported when using Codex with a ChatGPT account."}}` and empty stderr raises `NativeCliError` with `INVALID_MODEL` (confirm `_diagnostic_from_stdout` extracts that message; if not, assert on the diagnostic shape it does extract). Run; expect failure.
  2. Implement; run module tests and the full suite.
- **Acceptance**: health probes flag both observed stale-model messages; other classifications unchanged; review approves.

## Integration

Branch `fix/provider-routing-vlc` merges into `master` after all tracks pass and the merged-tree full suite and Bash smoke test pass (merge and push approved by the user on 2026-10-05). Then `./install.sh --platform all` refreshes the host install, and the user runs `gin-workflow setup models` to choose real codex and antigravity models.

## Validation and Traceability

| Spec item | Evidence |
|---|---|
| q15 | smoke `setup models` via installed launcher; PS static review |
| up4 | prose-wrapped result test; no-contract test |
| cij | review fallback test; workspace_unavailable event + closed breaker |
| vlc.1 | classification tests for both observed messages |
