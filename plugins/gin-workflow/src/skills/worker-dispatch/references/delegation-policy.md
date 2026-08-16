# Delegation Policy

Plans record the selection at `execution_strategy.mode`, the configured adapter behavior at `execution_strategy.workers.mode`, and a concrete `execution_strategy.rationale`.

Use `direct` mode when work is sequential, explicitly one-agent, contains three or fewer tasks, or has no qualifying worker condition. Use `worker` mode only when work has more than three independent parallel tasks or is explicitly long-running, specialized, or an independent review.

Each worker receives only its objective, constraints, generated manifest, isolation policy, expected output, task ID, workflow ID, retry identity, and model tier. Provider model names and parent conversation context are not worker inputs.

Native Claude, Codex, and Antigravity adapters detect harness support through the injected native dispatch boundary. They normalize the same provider-neutral request and result. The call delegates methodology to `subagent-driven-development`; the adapter must not embed TDD steps, debugging procedures, implementation recipes, planning instructions, or review instructions.

If native support is unavailable, emit `worker.unavailable` and activate the configured sequential adapter. Absence of a fallback is a normalized failure. Adapters must not import cloud SDKs, contact provider APIs directly, or launch daemon processes.
