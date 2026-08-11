# Plan: {title}

## Objective
{What success looks like}

## Model Guidance
- `default_model_class`: `standard_impl`
- `phase_guidance`:
  - `brainstorm`: `high_reasoning`
  - `design`: `high_reasoning`
  - `plan`: `standard_impl`
  - `implement`: `standard_impl`
  - `verify`: `standard_impl`
  - `review`: `high_reasoning`
  - `docs`: `cheap_simple`
- `override_rule`: Use `high_reasoning` for planning only when execution boundaries, dependency sequencing, or major tradeoffs are still unresolved.

## Requirement Analysis
- Problem statement: ...
- Success criteria: ...
- Constraints: ...
- Non-goals: ...

## Approach Options
### Option 1: {name}
- Summary: ...
- Pros: ...
- Cons: ...

### Option 2: {name}
- Summary: ...
- Pros: ...
- Cons: ...

### Recommended Approach
- Selected option: ...
- Reasoning: ...

## Scope
- In scope: ...
- Out of scope: ...

## Execution Strategy

```yaml
execution_strategy:
  mode: direct
  workers:
    mode: sequential
  rationale: Concrete reason for the selected mode
```

- Valid pairings are only `direct` with `workers.mode: sequential`, and `worker` with `workers.mode: parallel`.
- Use `direct` / `sequential` for sequential work, explicitly one-agent work, work with three or fewer tasks, or work without a qualifying worker condition.
- Use `worker` / `parallel` only for more than three independent parallel tasks, long-running work, specialized work, or an independent review.
- `workers.mode` declares scheduling behavior only. It never contains provider model names, commands, credentials, or implementation methodology.

## Tasks
### Track 1: {name}
- **Dependencies**: none | Track N
- **Files**: list of files to modify
- **Model class**: `standard_impl` | `high_reasoning` | `cheap_simple` (optional override)
- **Acceptance criteria**: ...
- **Estimated complexity**: low | medium | high

### Track 2: {name}
...

## Integration
- **Branch**: {integration-branch-name}
- **Merge strategy**: sequential | parallel-then-merge

## Validation
- [ ] All tests pass
- [ ] Type checks clean
- [ ] Manual verification steps

## Notes
- Model guidance is planning metadata, not Beads state.
- If omitted, agents should assume `standard_impl`.
- Use provider-neutral model classes only; do not name vendor-specific models in the plan schema.
