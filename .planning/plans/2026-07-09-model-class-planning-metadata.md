# Plan: Add Model Class Planning Metadata

## Objective
Add provider-neutral model-class metadata to workflow plans so `gin-workflow` can express preferred model classes by phase and by track, with `standard_impl` as the implicit default, without making model choice durable task state or a hard execution gate.

## Requirement Analysis
- Problem statement: Plans currently cannot express preferred model class for different phases of work, so model selection is implicit and inconsistent.
- Success criteria: The plan schema supports model guidance metadata; planning docs explain the abstract model classes and defaults; lifecycle and workflow guidance treat model guidance as plan metadata rather than Beads state or enforcement.
- Constraints: The solution must stay provider-neutral, advisory-only, and compatible with the existing markdown plan format.
- Non-goals: Hard enforcement, vendor-specific model names in plan files, storing model guidance in Beads, or adding runtime model-routing logic.

## Approach Options
### Option 1: Plan-wide model guidance plus optional track overrides
- Summary: Add a `Model Guidance` section to the plan schema with a default model class, phase guidance, and optional per-track `model_class` override.
- Pros: Matches the approved design, keeps metadata close to planning artifacts, allows both sensible defaults and targeted overrides.
- Cons: Requires updating the plan schema and several workflow docs together.

### Option 2: Single plan-level default only
- Summary: Add only one plan-level default model class and no phase or track metadata.
- Pros: Smallest schema change.
- Cons: Too coarse for the approved use case because brainstorming, design, review, implementation, and trivial docs often need different classes.

### Option 3: Workflow docs only, no schema change
- Summary: Document recommended classes in skills and commands without adding plan metadata.
- Pros: Lowest implementation cost.
- Cons: Fails to make model guidance part of the durable planning artifact and weakens downstream reuse.

### Recommended Approach
- Selected option: Option 1
- Reasoning: It captures the approved design with minimal abstraction, preserves provider neutrality, and keeps model guidance in the plan where it belongs.

## Scope
- In scope: `plan-schema.md`, `writing-plans` guidance, lifecycle/model-guidance docs, and any nearby workflow docs that need to explain the new metadata.
- Out of scope: Executor changes, platform-specific model switching, hook-based enforcement, or Beads schema changes.

## Tasks
### Track 1: Extend plan schema with model guidance
- **Dependencies**: none
- **Files**: `plugins/gin-workflow/src/skills/writing-plans/plan-schema.md`
- **Acceptance criteria**: The schema includes a `Model Guidance` section with `standard_impl` as the implicit default, phase guidance examples, and optional per-track `model_class` override.
- **Estimated complexity**: low

### Track 2: Update planning skill guidance
- **Dependencies**: Track 1
- **Files**: `plugins/gin-workflow/src/skills/writing-plans/SKILL.md`, `plugins/gin-workflow/src/commands/plan.md`
- **Acceptance criteria**: Planning guidance explains the abstract model classes, the `standard_impl` default, and when `plan` may escalate to `high_reasoning`.
- **Estimated complexity**: low

### Track 3: Align lifecycle and supporting docs
- **Dependencies**: Track 1
- **Files**: `docs/agent-task-lifecycle.md`, `README.md`, `docs/model-class-planning-metadata-design-2026-07-09.md`
- **Acceptance criteria**: Lifecycle and overview docs describe model guidance as planning metadata only and do not imply Beads ownership or hard enforcement.
- **Estimated complexity**: low

## Integration
- **Branch**: current working branch
- **Merge strategy**: sequential

## Validation
- [ ] Review the updated schema examples for internal consistency
- [ ] Review updated docs for agreement on `standard_impl` as the implicit default
- [ ] Confirm no doc still describes model guidance as Beads state or execution enforcement
