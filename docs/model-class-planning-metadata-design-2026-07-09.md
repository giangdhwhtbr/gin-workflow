# Model Class Planning Metadata Design

## Goal

Add provider-neutral model-selection metadata to workflow plans so agents can prefer the right class of model for each phase of work without turning model choice into durable task state or a hard execution gate.

## Problem

The workflow currently has no structured way to express that some phases benefit from stronger reasoning while others should default to a cheaper implementation model.

That creates two issues:

1. model selection is implicit and inconsistent
2. planning artifacts cannot communicate preferred model class to downstream commands or agents

## Design

### Model classes

Use a small abstract vocabulary:

- `high_reasoning`
- `standard_impl`
- `cheap_simple`

These names are intentionally provider-neutral. They describe workload shape rather than naming a specific vendor model.

### Default behavior

The implicit default is:

- `standard_impl`

If a plan, phase, or track does not specify a model class, agents should assume `standard_impl`.

### Phase guidance

Recommended defaults by workflow phase:

- `brainstorm`: `high_reasoning`
- `design`: `high_reasoning`
- `plan`: `standard_impl`
- `implement`: `standard_impl`
- `verify`: `standard_impl`
- `review`: `high_reasoning`
- `docs`: `cheap_simple`

### Why `plan` defaults to `standard_impl`

Planning after design is usually a decomposition step, not the primary reasoning step.

Once architecture and tradeoffs are already settled, planning mainly translates an approved design into:

- ordered tasks
- dependencies
- validation steps
- scope boundaries

That is still important, but it usually does not justify the default cost of `high_reasoning`.

### Escalation rule for planning

`plan` may be explicitly upgraded to `high_reasoning` when:

- execution boundaries are still unclear
- dependencies are unusually complex
- the design is only partially settled
- the plan itself must resolve major sequencing tradeoffs

## Metadata shape

### Plan-level defaults

Plans may declare a default model class section:

```md
## Model Guidance

Defaults:
- `default_model_class`: `standard_impl`
```

### Phase-level guidance

Plans may declare phase recommendations:

```md
## Model Guidance

Defaults:
- `default_model_class`: `standard_impl`

Phase guidance:
- `brainstorm`: `high_reasoning`
- `design`: `high_reasoning`
- `plan`: `standard_impl`
- `implement`: `standard_impl`
- `verify`: `standard_impl`
- `review`: `high_reasoning`
- `docs`: `cheap_simple`
```

### Track-level override

Individual tracks may override the default when needed:

```md
- id: doc-cleanup
  title: Update README wording
  model_class: cheap_simple
```

## Non-goals

- hard enforcement of model choice
- provider-specific model naming in plan files
- storing model choice in Beads
- treating model selection as workflow status

## Ownership

- plan files own model guidance metadata
- Beads does not own model guidance
- runtime executors may read this metadata later, but they do not define it

## Recommended follow-up implementation

1. extend `plan-schema.md` with a `Model Guidance` section
2. update `writing-plans` to require `standard_impl` as the implicit default
3. document when `plan` may override to `high_reasoning`
4. update lifecycle docs so model guidance is treated as planning metadata, not task state

## Decision

Adopt abstract model classes with:

- `standard_impl` as the implicit default
- `high_reasoning` for brainstorming, design, and review
- `plan` defaulting to `standard_impl` unless complexity justifies escalation
- `cheap_simple` reserved for trivial docs or low-complexity edits
