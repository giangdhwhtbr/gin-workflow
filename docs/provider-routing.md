# Native Provider Routing

Gin Workflow v2.2 lets the harness that opened a project remain the planner and
review coordinator while authenticated native Claude, Codex, or Antigravity
CLIs perform bounded implementation work. It does not call vendor SDKs and does
not share one provider's credential with another.

## Selection rule

Plans name a portable `provider role` and `reasoning tier`, never a concrete
vendor model. Typical reasoning guidance is:

- `low`: mechanical edits, simple documentation, predictable boilerplate;
- `medium`: normal implementation with clear requirements and bounded design;
- `high`: architecture, security, migrations, concurrency, or unusually
  constrained work.

At orchestration, the role expands to its ordered preferred and fallback
providers. `main_harness` expands to the harness that opened the workflow. The
reasoning tier is then resolved through the machine-local model aliases in
`.agent-workflow/providers.local.yaml`. For example, `backend/high` can resolve
to Claude/Opus while `frontend/medium` resolves to Antigravity/Gemini Flash.
Fallback preserves the requested tier: `high` never silently becomes `medium`.

At dispatch time the preview is rechecked. Candidates are tried in order after
checking circuit state, native CLI health, and provider concurrency. The actual
provider/model alias and fallback reason are runtime evidence, not Beads or plan
data.

Runtime callers should construct scheduling through
`ProviderRegistry.build_worker_scheduler()`. This carries
`routing.worker.timeout_seconds`, `routing.worker.max_retries`, and the summed
provider concurrency into the scheduler instead of maintaining a second set of
defaults.

## Two configuration layers

`plugins/gin-workflow/src/examples/config.full.yaml` is the full portable
example. Copy its policy shape into `.agent-workflow/config.yaml`; this file is
safe to review and commit. It defines roles, concurrency, queue/timeout policy,
the circuit breaker, and independent review limits.

`plugins/gin-workflow/src/examples/providers.local.example.yaml` demonstrates
the local layer. Configure it through `--provider-set`; setup writes
`.agent-workflow/providers.local.yaml` and gitignores it. It contains executable
and low/medium/high model aliases, but no token or credential. Each native CLI
must already be installed and authenticated using its own login mechanism.

The model shown in a plan is therefore a logical tier. The default concrete
model for each provider is configured only in `providers.local.yaml` under
`providers.<name>.models.low|medium|high`.

## Health and circuit breaker

Health detection verifies the executable and required non-interactive flags,
including explicit model selection. If an installed CLI cannot prove that it
supports `--model`, that provider is unavailable; Gin Workflow never guesses or
uses its implicit default. `doctor` is read-only and should be used after CLI
upgrades or authentication changes.

The circuit breaker is keyed by provider and model alias. Quota exhaustion,
rate limiting, authentication failure, service unavailability, timeout, and
process crash count toward opening it. Compilation/test failures, review
findings, invalid result contracts, unclear requirements, and concurrency
saturation do not. After cooldown, only the configured number of half-open
probes may run. A successful probe closes that specific circuit.

If no healthy same-tier route has capacity before the queue deadline, the
worker returns `worker_routes_unavailable`; the Bead remains open. When review
is independent, its provider must differ from the implementation provider
unless explicit self-review fallback is enabled. Unresolved findings return to
the original implementation route, or a same-role/same-reasoning fallback, for
at most the configured review cycles.

Review workers return one explicit `review_decision` evidence record
(`approved` or `changes_requested`) plus structured `review_finding`
records when changes are required. A review result cannot edit files, create
commits, approve with blockers, or rely on an empty generic worker result as
implicit approval. The coordinator persists the decision and findings through
the configured review provider before exposing a terminal review status.

## Setup and maintenance

The `/setup` wrapper asks nine question groups one at a time, then runs a
non-writing preview with both `--set` and `--provider-set`. Review both
`configuration` and `provider_configuration` before approving the identical
write.

Useful maintenance actions are `detect`, `status`, `doctor`, `diff`,
`configure`, `update`, `rollback`, `export-bundle`, and `verify-bundle`.
`configure` and `update` preview before approval. A v2.1-to-v2.2 update creates
a backup, does not invent routes, and supports explicit rollback.

## Privacy boundary

Portable config, bundles, worker requests, and plans exclude executables,
concrete provider models, credentials, parent transcripts, secrets, and private
reasoning. Local provider configuration is excluded from bundles. Native
processes receive bounded stdin, an explicit isolated working directory,
timeout/cancellation policy, and a sanitized environment that retains only the
paths needed for the CLI's existing local authentication.
