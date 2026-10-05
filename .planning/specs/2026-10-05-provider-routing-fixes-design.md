# Design: Provider routing and launcher fixes

Date: 2026-10-05
Status: confirmed in conversation on 2026-10-05
Epic and workflow ID: gin-workflow-vlc

## Goal and Scope

Fix four bugs found while shipping gin-workflow-f7g. No provider model names are hard-coded; real models are chosen through `gin-workflow setup models`. No new dependencies.

1. **q15 launcher packages** (`gin-workflow-q15`): the gin-workflow launcher installs `workflow_core`, `workflow_providers`, and `review_ledger` (all three import each other) in `install.sh` and `install.ps1`. gin-qa still installs only `gin_qa`. The Bash smoke test runs `gin-workflow setup models --provider claude` through the installed launcher, which imports `workflow_providers`. PowerShell is changed and checked statically only (pwsh is not installed here).
2. **up4 worker result with leading text** (`gin-workflow-up4`): `direct_worker_result` accepts a `result`/`response`/`text` string (or `item.text`) whose worker-result JSON object is preceded or followed by other text, choosing the last decodable JSON object that satisfies the result contract. Behavior for pure-JSON strings and records is unchanged; no contract-satisfying object still raises `INVALID_RESULT`.
3. **cij review outside a worktree** (`gin-workflow-cij`): a routed worker request with `provider_role` `review` and no `workspace_id` runs in the repository root. Every other workspace failure raises `WorkspaceUnavailableError`; the router emits `unavailable` with reason `workspace_unavailable` and records no circuit-breaker failure, since it is not a provider fault. Implementation workers still require an isolated worktree.
4. **vlc.1 invalid models on stdout** (`gin-workflow-vlc.1`): native failure classification uses stderr plus the stdout diagnostic, and treats "not recognized" next to "model" as `INVALID_MODEL`, so health probes reject stale aliases that codex and agy report in stdout JSON.

## Error Handling and Testing

Each fix gets a failing test first: an installed-launcher smoke step for q15, unit tests in `tests/workflow_providers/` for the others. Then the full Python suite and the Bash smoke test run. Each track gets an independent provider review.

## Out of Scope

Choosing concrete models in `providers.local.yaml` (done by the user afterwards via `gin-workflow setup models`), launcher version bumps, and other providers.
