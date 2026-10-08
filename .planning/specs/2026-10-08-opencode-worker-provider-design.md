# OpenCode worker provider

Status: draft for user review.

## Goal and scope

OpenCode is currently only a skill-install platform (`install.sh`). Make `opencode` a full routed provider like `codex` and `antigravity`: it can be a worker for implementation tracks, an independent reviewer, a main harness, and be configured and health-checked through setup.

Out of scope: PreToolUse/PostToolUse hooks for OpenCode (it has none), a shared table-driven adapter refactor, and putting `~/.opencode/bin` on `PATH`.

Verified against `opencode v2.0.12`: `opencode run --standalone --auto --format json --model <provider/model#variant> "<prompt>"` runs non-interactively and emits JSONL (`{"type":"text","part":{"text":...}}`). There is no `--cd`/`--add-dir` (cwd is the workspace) and no sandbox flag. `opencode models` prints one `provider/model` id per line.

## Requirements

1. `workflow_providers/opencode_worker.py` provides `build_opencode_invocation`, `opencode_health`, and `OpenCodeWorkerAdapter`, modelled on `antigravity_worker.py`.
2. Invocation argv: `[exe, run, --standalone, --auto, --format, json, (--model M unless provider_default), prompt]`, cwd = worker workspace.
3. Health runs `opencode run --help` and requires `--auto`, `--format`, `--model`; with an explicit model it probes once with `MODEL_PROBE_PROMPT` and reports `invalid_model`.
4. JSONL output is normalized to a `WorkerResult`; unparseable output or missing final text fails as `invalid_result_contract`.
5. `opencode` is accepted wherever `claude|codex|antigravity` are enumerated: `cli.py` (`--harness`, `--provider`), `configuration.py` `SUPPORTED_HARNESSES`, `project_detect.py`, `setup_service.py` (marker `.opencode`, health builder), `registry.py` (factory, `health_builders`).
6. A shared `PROVIDER_DEFAULT_PROVIDERS = {"antigravity", "opencode"}` replaces the `== "antigravity"` checks for `provider_default` in `assignments.py`, `provider_config.py`, `registry.py`, `routed_worker.py`. `provider_default` stays rejected for `claude` and `codex`. A tier may also be a verbatim model string (`provider/model` or `provider/model#variant`).
7. `~/.opencode/bin` is added to `COMMON_INSTALL_DIRS` so the executable resolves without configuration.
8. `list_models("opencode")` runs `opencode models`; each line becomes `{id, label=id, reasoning_levels=[]}`.
9. `classify_native_failure` recognises OpenCode's real quota, auth, and invalid-model messages (captured from the CLI) so infrastructure failures open the circuit and task failures do not.
10. Independent review routes through `routing.review` with `opencode` as a valid, different provider under `independence: provider`.
11. Docs state that OpenCode has no sandbox and `--auto` auto-approves permissions, so isolation relies on the worktree and cwd.

## User Stories

### US-1: Dispatch a track to OpenCode
As a workflow user, I want routing to send a track to OpenCode, so that I can use my OpenCode models for implementation.

Acceptance criteria:
- `providers.local.yaml` with an `opencode` block resolves, and `orchestrate` writes an assignment naming `opencode`.
- Dispatch invokes `opencode run` in the track workspace and returns a normalized `WorkerResult`.
- An unhealthy or unavailable OpenCode falls back to the next candidate at the same tier.

### US-2: Independent review by OpenCode
As a workflow user, I want OpenCode to review another provider's work, so that review stays independent.

Acceptance criteria:
- With `independence: provider`, an OpenCode reviewer is accepted when the implementer is not OpenCode, and rejected when it is.
- The review result is recorded only through the ledger, never from the worker result.

### US-3: Configure OpenCode in setup
As a workflow user, I want setup to detect and probe OpenCode, so that I do not hand-write its config.

Acceptance criteria:
- Setup detects `.opencode`, lists models from `opencode models`, and accepts `provider_default` or an explicit model per tier.
- The executable is found at `~/.opencode/bin/opencode` without `PATH` changes.

## Errors and compatibility

- Health failure (missing flags, no executable, `invalid_model`) drops the route; fallback keeps the tier and never downgrades.
- Infrastructure failures count against the circuit; task, test, review, and invalid-result failures do not.
- Existing claude/codex/antigravity behaviour is unchanged; `provider_default` is still rejected for claude and codex.
- Risk: no sandbox. Accepted, documented, same trade-off as codex's bypass flag.

## Testing

Fake `NativeCliRunner`, no real OpenCode in CI:
- `test_worker_adapters.py`: argv (with/without model, cwd, prompt), health (missing flag, `invalid_model`), JSONL to `WorkerResult`, bad output.
- `test_registry.py`, `test_routed_worker.py`: resolve, dispatch, fallback; `provider_default` accepted for opencode, rejected for claude/codex.
- `test_executable_resolver.py`: finds `~/.opencode/bin/opencode`.
- `test_list_models.py`: parses `provider/model` lines.
- Review routing test: opencode reviewer accepted/rejected by independence.
- Optional smoke test, skipped when `opencode` is absent: one `--format json` call.
- Docs: `providers.md`, `config.md`, `providers.local.example.yaml`, `troubleshooting.md` (drop "no OpenCode worker adapter"), `README.md`, `multi-agent-routing.md`, `architecture.md`.
