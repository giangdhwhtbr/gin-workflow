# Native Provider Routing

Gin Workflow v2.3 keeps the opening harness as planner and coordinator while
bounded implementation work is delegated through configured native providers.
Portable plans name logical provider roles and reasoning tiers, and portable
configuration may include provider aliases plus routing/concurrency policy. They
never name a concrete vendor model, executable path, credential, secret value, or
provider bypass.

## Selection and provider-default

At orchestration, the role expands to ordered preferred and fallback providers.
`main_harness` resolves to the harness that opened the workflow. Each candidate
must have a machine-local executable and `low`, `medium`, and `high` mappings in
`.agent-workflow/providers.local.yaml`. The machine-local provider/authentication
layer owns executable paths, concrete model aliases, credentials, and secret
values; it is gitignored and never copied into portable config or bundles.

`provider_default` is a deliberate selection mode supported only for the
`antigravity` provider. Its assignment manifest records `provider: antigravity`
and `selection_mode: provider_default` and omits a concrete model. Explicit
model aliases are recorded only for explicit selections. A non-Antigravity
`provider_default` mapping is rejected during local configuration and assignment
resolution. This rule is implemented by `workflow_core/provider_config.py` and
`workflow_core/assignments.py`, with coverage in `tests/workflow_core/`.

The Antigravity adapter emits `--print --sandbox` and adds `--model` only for
an explicit model. Health requires the executable to prove the required flags;
model support is reported as runtime health evidence. See
`workflow_providers/antigravity_worker.py` and `workflow_providers/routed_worker.py`.

## Dispatch, fallback, and review

At dispatch, candidates are rechecked for CLI health, explicit-model support
when required, circuit breaker state, and capacity. Fallback preserves the requested
reasoning tier. If no healthy same-tier route is available before the queue
deadline, the worker returns `worker_routes_unavailable` and the Bead remains
open. Runtime receipts may include the actual provider/model alias, fallback
reason, and circuit transition; these are evidence, not task state or plan data.

Review is routed through the same capability boundary. Independent review uses
a different provider unless an explicitly configured self-review fallback is
allowed. A review decision is persisted as structured approval or
changes-requested evidence; a generic worker result is never implicit approval.

## Setup and safe maintenance

Run the `setup` skill once to create `.agent-workflow/generated/effective-config.yaml`.
Use `status`, `doctor`, `diff`, `configure`, `update`, `rollback`,
`export-bundle`, and `verify-bundle` for explicit maintenance. Review the
non-writing preview before an approved configuration write. Do not edit a
runtime/cache copy or install directory directly; change canonical repository
sources or use the setup/provider capability that owns the artifact.

Version channels are independent but currently all supported at `2.3`.
A registered v2.2-to-v2.3 migration creates a validated backup and requires
approval; it does not move plans, Beads data, worktrees, review ledgers, or
evidence. See [setup-system](setup-system.md).

## Privacy boundary

Portable config, bundles, worker requests, and plans exclude executable paths,
concrete provider models, credentials, secret values, parent transcripts, and
private reasoning. Portable configuration may retain references such as
`secret_ref:NAME`; the machine-local provider/authentication layer resolves any
credential or secret value at the native process boundary.
