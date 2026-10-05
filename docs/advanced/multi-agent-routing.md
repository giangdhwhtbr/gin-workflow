# Multi-Agent Routing & Custom Providers

By default, **`gin-workflow` runs as a single-harness setup using Claude Code**. This baseline is simple, fast, and covers 100% of the workflow lifecycle.

When scaling up to complex architectures, heavy workloads, or specialized tasks, you can optionally configure **multi-agent routing** across different harnesses (such as Codex CLI or Antigravity CLI) and models.

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
    architect:
      tier: heavy
    backend:
      tier: standard
    frontend:
      tier: standard
    reviewer:
      tier: standard
  review:
    independence: provider     # Enforce a different provider for reviews
    max_cycles: 3
```

Define available providers and model tiers in your local machine configuration (`.agent-workflow/providers.local.yaml`, which is git-ignored):

```yaml
providers:
  claude:
    command: "claude"
    tiers:
      heavy: "claude-3-7-sonnet"
      standard: "claude-3-5-sonnet"
      fast: "claude-3-5-haiku"
  codex:
    command: "codex"
    tiers:
      heavy: "o3-mini"
      standard: "o4-mini"
```

---

## 3. How Orchestration Routes Work

During `/gin-workflow:orchestrate`:
1. The orchestrator inspects each track in the approved plan.
2. It resolves the requested role (e.g. `backend`) and reasoning tier (`standard`) against configured providers.
3. It assigns a worker route to the track bead.
4. If a route cannot be resolved, orchestration halts safely before mutating the workspace or task state.

---

## 4. Resilience & Circuit Breakers

`gin-workflow` includes built-in safeguards for routed workers:
- **Health Checks:** Automatically checks if external CLI tools (e.g., `codex`, `agy`) are available on `PATH`.
- **Circuit Breakers:** If a routed provider fails repeatedly on a track, it is tripped and the track falls back to your primary harness.
- **Strict Tier Guarantee:** A fallback will never downgrade the reasoning tier requested by the plan.

For full architectural details, see [Concepts: Providers](../concepts/providers.md).
