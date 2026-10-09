# Multi-Agent Routing & Custom Providers

With `provider_mode: single`, **`gin-workflow` runs everything in the harness you open**, such as Claude Code. This baseline is simple and covers the whole workflow lifecycle.

When scaling up to complex architectures, heavy workloads, or specialized tasks, you can optionally configure **multi-agent routing** across different harnesses (such as Codex CLI, Antigravity CLI, or OpenCode) and models.

---

## 1. When to Use Multi-Agent Routing

Multi-agent routing is recommended when:
- **High concurrency:** You have more than 3 parallel tracks in an epic and want concurrent execution without context contention.
- **Model specialization / Cost efficiency:** Routing simpler, boilerplate tasks to faster/cheaper models while reserving high-reasoning models for core architecture and security.
- **True independent code review:** Having a completely different provider or model family review code changes before closing a track.

---

## 2. Configuration

Enable multi-provider mode in `.agent-workflow/config.yaml`:

```yaml
provider_mode: multi

routing:
  roles:
    backend:
      preferred: [claude]
      fallback: [codex]
    frontend:
      preferred: [antigravity]
      fallback: [codex, claude]
    review:
      preferred: [codex]
      fallback: [antigravity]
  review:
    role: review
    require_independent: true
    independence: provider     # the reviewer's provider must differ from the implementer's
    max_cycles: 3
```

Roles are responsibilities such as `backend`, `frontend`, `docs`, `review`, or `general`; each lists providers (`claude`, `codex`, `antigravity`, `opencode`, or `main_harness`) in preference order. Plans name a role and a reasoning tier (`low`, `medium`, `high`), never a provider or model.

Map each provider's executable and its models per reasoning tier in your local machine configuration (`.agent-workflow/providers.local.yaml`, which is git-ignored):

```yaml
providers:
  claude:
    executable: claude
    models:
      low: haiku
      medium: sonnet
      high: opus
  codex:
    executable: codex
    models:
      low: <codex model>
      medium: <codex model>
      high: <codex model>
```

---

## 3. How Orchestration Routes Work

During `/gin-workflow:orchestrate`:
1. The orchestrator inspects each track in the approved plan.
2. It resolves the requested role (e.g. `backend`) and reasoning tier (e.g. `medium`) against the role's `preferred` then `fallback` providers; each candidate needs an executable and a model for that tier in `providers.local.yaml`.
3. It writes the resolved routes to the runtime assignment manifest (`.agent-workflow/runtime/assignments/<workflow>.yaml`). Provider and model names never enter the plan or Beads.
4. If any track cannot be resolved, every diagnostic is reported and nothing durable is created.

---

## 4. Resilience & Circuit Breakers

`gin-workflow` includes built-in safeguards for routed workers:
- **Health checks:** at dispatch, each candidate CLI must start and support the flags its adapter needs (`claude -p`, `codex exec`, `agy --print --sandbox`, `opencode run --auto --format json`).
- **Circuit breakers:** infrastructure failures (quota, rate limit, authentication, timeout, crash) count against a provider; at `routing.circuit_breaker.failure_threshold` the provider is skipped for `cooldown_seconds` and the task moves to the next configured route. When no route is left, the worker returns `worker_routes_unavailable` and the bead stays open.
- **Strict tier guarantee:** a fallback never downgrades the reasoning tier requested by the plan.

For full architectural details, see [Concepts: Providers](../concepts/providers.md).
