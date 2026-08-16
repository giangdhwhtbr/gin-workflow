# Cross-Harness Worker Routing Design

Status: approved design, awaiting written-spec review

Date: 2026-08-14

Bead: `gin-workflow-r87`

## Summary

Extend `gin-workflow` so one active harness can plan, orchestrate, and review
work while implementation tasks run through other locally authenticated native
harnesses. Plans describe a task using a configurable provider role and a
logical reasoning tier. At orchestration and execution time, a policy router
resolves that request to a concrete provider and model, observes provider
capacity and circuit-breaker state, and uses configured fallbacks without
silently reducing the requested reasoning tier.

The initial target flow is:

```text
Codex plans and orchestrates
  -> backend/high resolves to Claude/Opus
  -> frontend/medium resolves to Antigravity/Gemini Flash
  -> review resolves to the main harness, Codex
  -> review findings return to the original implementation worker
```

The design preserves the repository's ownership model: plans own approved
scope and logical execution guidance, Beads owns durable task state, review
ledger records own findings, and runtime artifacts own disposable assignment,
dispatch, capacity, and circuit-breaker state.

## Goals

- Make initial setup collect every required routing decision instead of
  silently choosing a policy.
- Provide a complete, schema-validated example configuration and user guide.
- Let the planner assign a configurable provider role and reasoning tier to
  every implementation and review track.
- Resolve logical assignments to a native harness and concrete model through
  user configuration.
- Reuse locally installed and authenticated Claude, Codex, and Antigravity CLI
  sessions rather than storing API credentials or starting cloud SDK clients.
- Route around quota, rate-limit, authentication, service, and CLI failures
  with an auditable provider-and-model circuit breaker.
- Prefer the main harness as a configured fallback when it is healthy and has
  concurrency capacity.
- Send structured review findings back to the worker responsible for the
  implementation and repeat validation and review until findings are terminal.

## Non-Goals

- Querying vendor billing APIs or predicting exact remaining token quota.
- Dynamically optimizing cost using live pricing or token telemetry.
- Putting credentials, provider commands, or concrete model identifiers into
  portable configuration, plan files, Beads, worker payloads, or bundles.
- Silently downgrading a requested reasoning tier to obtain capacity.
- Treating runtime worker metadata as authoritative task state.
- Supporting remote cloud SDK workers in the first implementation.

## Terminology

- **Main harness**: the harness in which the workflow was opened and approvals
  are collected, such as Codex.
- **Provider role**: a user-configurable workload category such as `backend`,
  `frontend`, `review`, `docs`, or `general`.
- **Reasoning tier**: the portable workload requirement `low`, `medium`, or
  `high`.
- **Provider**: a native worker harness, initially `claude`, `codex`, or
  `antigravity`.
- **Model mapping**: machine-local resolution from provider plus reasoning tier
  to the model alias understood by that provider's CLI.
- **Assignment manifest**: runtime preview of the requested role/tier and its
  currently resolved provider/model/fallback route.
- **Sticky affinity**: preference for sending a revision to the same
  provider/model that produced the implementation.

## Existing System and Required Changes

The current version has separate Claude, Codex, and Antigravity worker adapter
classes, but each adapter requires an injected `native_dispatch` callback. The
provider registry does not expose worker dispatch, and `WorkerScheduler`
accepts one dispatcher rather than a router capable of selecting different
providers per task. Effective configuration contains logical model tiers but
does not map them to concrete provider models. The review ledger supports
findings, but no coordinator automatically returns those findings to the
originating worker.

This design adds routing and coordination around the existing provider-neutral
contracts instead of teaching lifecycle skills to branch on harness names.

## Architecture

```text
Approved plan
  | provider_role + reasoning
  v
AssignmentResolver
  | portable role policy + machine-local model mapping
  v
AssignmentManifest
  | reviewable initial route
  v
RoutedWorkerDispatcher
  | health + capacity + circuit breaker + fallback
  v
NativeCliAdapter
  | bounded worker payload + isolated workspace
  v
WorkerResult
  | diff + tests + evidence
  v
ReviewCoordinator
  | fresh review context
  v
Review ledger
  | approved OR structured findings
  v
Original worker affinity / same-tier fallback
```

### Component Boundaries

#### SetupQuestionnaire

The native setup skill or command wrapper asks one deterministic sequence of
questions and converts the answers into CLI assignments. The setup CLI itself
remains non-interactive. It validates and previews the complete write before
requesting native-harness approval.

#### ProviderLocalConfig

Loads provider executable and model mappings from a machine-local file that is
excluded from portable effective configuration, bundle export, and version
control by default. It never stores credentials.

#### AssignmentResolver

Accepts `provider_role`, `reasoning`, main harness, portable routing policy, and
local provider mappings. It returns an ordered candidate route or a structured
configuration error. It does not check live availability.

#### RoutedWorkerDispatcher

Revalidates a previewed route at dispatch time, skips open circuits, checks
native health and concurrency capacity, applies queue and fallback policy, and
delegates lifecycle normalization to the selected adapter.

#### CircuitBreakerStore

Stores disposable state keyed by provider and concrete model alias. It uses an
injectable clock, atomic updates, and explicit transition events.

#### NativeCliAdapter

Runs one supported native CLI in non-interactive mode using its existing local
login. It supplies the concrete model through the native CLI boundary while
keeping provider model identifiers out of the portable worker request. It
normalizes provider output and classifies provider/infrastructure failures.

#### ReviewCoordinator

Creates fresh bounded review context, dispatches the configured review role,
records findings, returns findings to the implementation route, schedules
revalidation, and enforces the maximum review-cycle policy.

## Setup Experience

Initial setup asks for:

1. the main harness;
2. enabled native worker providers;
3. provider roles and their preferred providers;
4. model mapping for `low`, `medium`, and `high` on each provider;
5. ordered fallback providers for each role;
6. concurrency limits per provider;
7. queue wait, worker timeout, and retry limits;
8. circuit-breaker threshold, cooldown, and half-open probe limit;
9. review provider role, independent-review requirement, self-review fallback,
   and maximum review cycles.

Detection verifies that configured executables exist. `doctor` performs a
non-mutating native health/authentication check when the provider CLI supports
one. Setup does not manufacture a policy when required answers are absent.

The wrapper runs `init --dry-run` or `configure --dry-run`, displays every
proposed file and value, obtains explicit approval, and then repeats the same
operation with approval. The CLI validates all portable and machine-local
configuration before writing any file atomically.

## Configuration Model

### Portable Configuration

`.agent-workflow/config.yaml` remains safe to commit and bundle. It identifies
provider roles and policies but contains no executable, provider model name, or
credential.

```yaml
harness: codex
schema_version: "2.2"
workflow_version: "2.2"
setup_cli_version: "2.2"

routing:
  roles:
    backend:
      preferred: [claude]
      fallback: [main_harness]
    frontend:
      preferred: [antigravity]
      fallback: [claude, main_harness]
    review:
      preferred: [main_harness]
      fallback: [claude]
      require_independent: true
    docs:
      preferred: [antigravity]
      fallback: [main_harness]
    general:
      preferred: [main_harness]
      fallback: [claude, antigravity]

  concurrency:
    claude: 2
    antigravity: 2
    codex: 1

  queue:
    max_wait_seconds: 120

  worker:
    timeout_seconds: 900
    max_retries: 1

  circuit_breaker:
    failure_threshold: 1
    cooldown_seconds: 900
    half_open_max_probes: 1

  review:
    role: review
    require_independent: true
    allow_self_review_fallback: false
    max_cycles: 3
```

Provider names in this layer select a logical native capability. They do not
name a provider command or concrete model.

### Machine-Local Provider Configuration

`.agent-workflow/providers.local.yaml` is gitignored, never exported, and never
merged into portable `EffectiveConfig`.

```yaml
schema_version: "2.2"
providers:
  claude:
    executable: claude
    models:
      low: haiku
      medium: sonnet
      high: opus

  antigravity:
    executable: antigravity
    models:
      low: gemini-flash
      medium: gemini-flash
      high: gemini-pro

  codex:
    executable: codex
    models:
      low: fast
      medium: standard
      high: reasoning
```

These aliases are examples and must be validated against the locally installed
CLI. Credentials remain owned by the native CLI login. Logs and events redact
the complete launched command and environment.

## Plan and Assignment Semantics

The planner evaluates each track and writes portable execution guidance:

```yaml
provider_role: backend
reasoning: high
```

Reasoning guidance is:

- `low`: mechanical changes, simple documentation, and predictable boilerplate;
- `medium`: normal implementation with clear requirements and bounded design;
- `high`: complex architecture, security, migration, concurrency, or unusually
  constrained work.

The planner assigns a role based on task responsibility and approved scope,
not file-extension heuristics alone. Users can override role or reasoning before
plan approval.

Orchestration produces a runtime assignment manifest under
`.agent-workflow/runtime/assignments/<workflow-id>.yaml`:

```yaml
task_id: api-auth
requested:
  provider_role: backend
  reasoning: high
resolved:
  provider: claude
  model: opus
fallback:
  provider: codex
  model: reasoning
```

The manifest is a reviewable preview, not an execution guarantee. Dispatch
rechecks current health, capacity, and circuit state and records the actual
route selected. Assignment manifests are supplemental runtime metadata and do
not replace the plan or Beads.

## Routing Algorithm

For each dependency-ready task:

1. Read its approved provider role and reasoning tier.
2. Expand the role into ordered preferred and fallback providers.
3. Resolve `main_harness` to the harness that opened the workflow.
4. Resolve each provider plus reasoning tier through machine-local model
   mappings.
5. Reject incomplete or invalid mappings before dispatch.
6. Skip candidates whose provider/model circuit is open.
7. Check native executable health and authenticated availability.
8. If concurrency is full, queue for the configured maximum wait.
9. Dispatch the first healthy candidate with capacity.
10. If the queue wait expires, continue to the next same-tier fallback.
11. If no candidate is usable, mark the task blocked with structured evidence.

Fallback never changes the requested reasoning tier. A high-reasoning task may
move from Claude/Opus to the main harness's high mapping, but it may not move to
a medium model without an explicit approved execution-strategy change.

## Circuit Breaker

The breaker key is `(provider, model_alias)`. Its states are:

```text
closed --failure threshold reached--> open
open --cooldown elapsed-------------> half-open
half-open --probe succeeds----------> closed
half-open --probe fails-------------> open
```

Counted failures are:

- quota exhausted;
- rate limited;
- authentication or native session unavailable;
- provider service unavailable;
- native CLI timeout or crash.

Task-domain failures do not affect the breaker:

- compilation or test failure;
- incorrect implementation;
- review findings;
- unclear requirements or missing approved scope.

Concurrency saturation also does not open a breaker. It triggers queue policy.
Every transition includes provider, model alias, classified reason, timestamp,
cooldown, workflow identity, and triggering task identity in runtime evidence.
No token, credential, full command, or private reasoning is recorded.

State is stored atomically in
`.agent-workflow/runtime/circuit-breakers.json`. It is disposable and may be
initialized as closed when it is absent before any provider failure has been
observed. Corrupt state is archived as evidence, and affected circuits are
initialized as open until a cooldown and successful half-open health probe
restore them; corrupt state is never silently trusted.

## Native CLI Adapter Contract

Each adapter must provide:

- executable detection and health metadata;
- a non-interactive invocation builder;
- model-alias validation;
- bounded context input without parent transcript, credentials, or private
  reasoning;
- cancellation and timeout behavior;
- normalized `WorkerResult` output;
- normalized provider/infrastructure failure classification;
- redacted diagnostic evidence.

Adapters use isolated workspaces and one durable task claim per worker. They do
not introduce provider-specific branching into lifecycle skills. Unsupported
native CLI versions fail health checks and enter fallback handling rather than
guessing invocation syntax.

## Review and Revision Loop

An implementation worker returning `completed` does not close its Bead.

1. The coordinator creates fresh review context from approved scope, diff,
   acceptance criteria, tests, and evidence.
2. The review role resolves through the same router. By default it maps to the
   main harness.
3. If independent review is required, the selected reviewer must differ from
   the implementation provider.
4. The reviewer records structured findings with severity, location, expected
   behavior, and evidence. It does not edit implementation code.
5. Findings are sent to the originating task with sticky affinity for its
   original provider/model.
6. If that circuit is open or the route is unavailable, the router selects a
   same-role, same-tier fallback.
7. The worker fixes only its assigned findings and reruns scoped validation.
8. A fresh review cycle verifies the revision.
9. The Bead closes only after all findings are terminal and acceptance evidence
   passes.

Each cycle uses a new `revision_identity` while retaining task identity and
retry idempotency. The default maximum is three cycles. Exceeding the maximum
creates a human-decision state instead of continuing indefinitely. Self-review
is used only when explicitly enabled by policy.

## State Ownership and Evidence

| Concern | Owner |
| --- | --- |
| Approved scope, role, reasoning | Plan file |
| Task identity, dependency, status, closure | Beads |
| Resolved preview and actual dispatch route | Runtime assignment/evidence |
| Provider/model breaker and concurrency state | Runtime state/evidence |
| Review findings and terminal disposition | Review ledger |
| Concrete executable/model mapping | Machine-local provider config |
| Credentials and login session | Native harness |

Provider/model aliases may appear in local assignment and audit artifacts so
the user can inspect routing decisions. They are excluded from portable config,
plans, Beads, worker payloads, exported bundles, and knowledge capture.

## Error Handling

- Missing provider mapping fails setup/configuration validation.
- Missing required role mapping blocks plan orchestration with a configuration
  error.
- Stale assignment preview is re-resolved at dispatch time.
- Malformed native output becomes `invalid_result_contract` and does not count
  as task completion.
- A provider failure is classified before breaker mutation; unknown failures
  fail closed and require evidence rather than being mislabeled as quota.
- If all preferred and fallback routes are unavailable, the task is blocked and
  remains open in Beads.
- A failed review provider follows review fallback policy. Self-review is not
  silently enabled.
- Corrupt local config or breaker state is never partially applied.

## Versioning and Migration

The configuration, workflow, and setup CLI channels advance to `2.2` because
the setup contract, plan execution metadata, and worker provider contract all
change.

Existing 2.1 repositories use `setup update --dry-run` followed by explicit
approval. Migration preserves artifact paths, plans, Beads, review ledgers,
knowledge, evidence, worktrees, and user changes. It adds the portable routing
section and machine-local provider configuration only after the questionnaire
has complete answers.

Until routing setup is completed, an upgraded repository retains compatible
main-harness direct execution. It does not invent cross-harness provider or
model mappings. Lifecycle entry reports that cross-harness routing is disabled
until configured.

Rollback uses the existing validated setup backup mechanism. Runtime assignment
and breaker files are supplemental and do not change durable plan or Beads
state.

## Documentation and Examples

The implementation provides:

- a complete portable configuration example;
- a complete machine-local provider configuration example;
- setup questionnaire instructions;
- a routing, reasoning, fallback, and circuit-breaker reference;
- native CLI prerequisites and health-check guidance;
- an end-to-end Claude backend, Antigravity frontend, Codex review example;
- reconfiguration, dry-run, update, rollback, and doctor instructions;
- failure and blocked-task troubleshooting.

Examples are loaded by automated tests with the production config loaders so
schema changes cannot silently make documentation invalid.

## Test Strategy

### Unit Tests

- Setup answers normalize into exact portable and local config structures.
- Invalid roles, reasoning tiers, model mappings, fallback cycles, and provider
  references fail before writes.
- Resolver produces deterministic candidate ordering.
- Router respects breaker, health, authentication, concurrency, queue, and
  fallback policy.
- Breaker transitions use a fake clock and atomic persistence.
- Provider failures are distinguished from task-domain failures.
- Fallback preserves reasoning tier.
- Review findings preserve task identity and worker affinity.
- Revision cycle limits produce human-decision state.

### Adapter Contract Tests

- Every native adapter detects supported and unsupported CLI versions.
- Invocation is non-interactive and command/environment diagnostics are
  redacted.
- Timeout, cancellation, quota, rate-limit, auth, unavailable service,
  malformed output, and success are normalized.
- Worker payloads contain no provider model identifier, credential, parent
  transcript, or private reasoning.

### Integration Tests

- Setup dry-run writes nothing and reports all proposed files and values.
- Approved setup writes both config layers atomically.
- Local provider config is gitignored and excluded from bundle export.
- Concurrency saturation queues before fallback.
- Breaker state survives scheduler recreation and recovers through half-open
  probes.
- Review requests use fresh bounded context.
- Review findings return to the original worker and trigger revalidation.

### End-to-End Fake CLI Scenario

1. `backend/high` resolves to Claude/Opus.
2. `frontend/medium` resolves to Antigravity/Gemini Flash.
3. Claude reports quota exhaustion; the Claude/Opus circuit opens.
4. The backend task falls back to Codex's high mapping.
5. Codex reviews the implementation and records a finding.
6. The finding returns to the actual implementation worker.
7. The worker fixes and validates the change.
8. Codex approves the new revision.
9. Evidence is complete and the Bead closes.

Regression coverage must retain setup atomicity, lifecycle gates, Beads
ownership, worktree isolation, bounded context, idempotent events, and
conservative commit/push behavior.

## Acceptance Criteria

- Setup collects and previews every required routing parameter.
- A full portable example, local provider example, and instruction document are
  shipped and schema-tested.
- Plans can assign configurable provider roles and reasoning tiers.
- Orchestration previews concrete provider/model assignments.
- Execution routes tasks through locally authenticated Claude, Codex, and
  Antigravity CLIs according to policy.
- Provider/model circuit breakers drive auditable same-tier fallback.
- Main-harness fallback occurs only when healthy and within configured capacity.
- Review findings return to the responsible worker and are re-reviewed after
  validation.
- No credentials, private reasoning, or provider commands enter portable
  artifacts or worker payloads.
- Existing 2.1 repositories have a dry-run, approval-gated migration and safe
  rollback path.
