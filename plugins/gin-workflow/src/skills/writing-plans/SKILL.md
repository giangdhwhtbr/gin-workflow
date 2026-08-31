---
name: writing-plans
description: Self-contained — turn confirmed requirements into detailed implementation plans with Beads-ready tracks and model guidance.
---

# Writing Plans

## Overview

Write comprehensive implementation plans assuming the engineer has zero context for our codebase and questionable taste. Document everything they need to know: which files to touch for each task, code, testing, docs they might need to check, how to test it. Give them the whole plan as bite-sized tasks. DRY. YAGNI. TDD.

Assume they are a skilled developer, but know almost nothing about our toolset or problem domain. Assume they don't know good test design very well.

**Context:** Use this skill only after the requirement discovery phase has ended with explicit user confirmation of the summarized understanding. If objectives, constraints, non-goals, or success criteria are still unclear, stop and clarify. If working in an isolated worktree, it should have been created via the using-git-worktrees skill at execution time.

**Save plans to:** `.planning/plans/YYYY-MM-DD-<feature-name>.md`
- (User preferences for plan location override this default)

## Planning Standard & Schema

Convert the confirmed requirement into a plan with concrete file mapping, right-sized tasks, explicit validation, and realistic sequencing.
Every plan should answer these questions before the task list begins:
1. What problem is being solved, and what is out of scope?
2. What constraints or risks materially affect implementation?
3. Which approach was selected, and why was it chosen?
4. What files, systems, or behaviors must change?
5. How will the user know the work is complete?
6. Which provider role and reasoning tier does each implementation or review track require?

You must follow the format defined in [plan-schema.md](file://plan-schema.md) when writing or modifying a plan.
- Include goals and scope, technical approach, required changes, implementation steps, testing strategy, and risks or mitigations.
- Include `Model Guidance` metadata using the abstract classes `high_reasoning`, `standard_impl`, and `cheap_simple`. Treat `standard_impl` as the implicit default when no model class is specified. Do not name a concrete provider or model in a portable plan.
- Declare `execution_strategy` exactly as specified in [plan-schema.md](file://plan-schema.md).
- Give every implementation or review track a `provider_role` and `reasoning` value using the low/medium/high guidance in the schema.
- Break work into Beads-ready tracks with explicit dependencies. Structure the plan so it can be turned directly into Beads tasks during orchestration.

## Scope Check

If the spec covers multiple independent subsystems, they should have been broken into sub-project specs during discovery. If not, suggest breaking this into separate plans — one per subsystem. Each plan should produce working, testable software on its own.

## File Structure

Before defining tasks, map out which files will be created or modified and what each one is responsible for. This is where decomposition decisions get locked in.

- Design units with clear boundaries and well-defined interfaces. Each file should have one clear responsibility.
- You reason best about code you can hold in context at once, and your edits are more reliable when files are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together should live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, don't unilaterally restructure - but if a file you're modifying has grown unwieldy, including a split in the plan is reasonable.

This structure informs the task decomposition. Each task should produce self-contained changes that make sense independently.

## Task Right-Sizing

A task is the smallest unit that carries its own test cycle and is worth a fresh reviewer's gate. When drawing task boundaries: fold setup, configuration, scaffolding, and documentation steps into the task whose deliverable needs them; split only where a reviewer could meaningfully reject one task while approving its neighbor. Each task ends with an independently testable deliverable.

## Bite-Sized Task Granularity

**Each step is one action (2-5 minutes):**
- "Write the failing test" - step
- "Run it to make sure it fails" - step
- "Implement the minimal code to make the test pass" - step
- "Run the tests and make sure they pass" - step
- "Commit" - step (only if explicitly authorized)

## Plan Document Header

**Every plan MUST start with this header (or equivalent from plan-schema.md):**

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SKILL: Use `executing-plans` to implement this plan. Authoritative task state is tracked via task-tracking capability (Beads); checkboxes (`- [ ]`) provide visual step breakdown.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about approach]

**Tech Stack:** [Key technologies/libraries]

## Global Constraints

[The spec's project-wide requirements — version floors, dependency limits, naming and copy rules, platform requirements — one line each, with exact values copied verbatim from the spec. Every task's requirements implicitly include this section.]

---
```

## Task Structure

````markdown
### Task N: [Component Name]

**Metadata:**
- Dependencies: []
- Provider role: general
- Reasoning: low
- Model guidance: standard_impl

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Interfaces:**
- Consumes: [what this task uses from earlier tasks — exact signatures]
- Produces: [what later tasks rely on — exact function names, parameter and return types. A task's implementer sees only their own task; this block is how they learn the names and types neighboring tasks use.]

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
*(Note: Do not commit or push unless explicitly authorized)*
````

## No Placeholders

Every step must contain the actual content an engineer needs. These are **plan failures** — never write them:
- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without actual test code)
- "Similar to Task N" (repeat the code — the engineer may be reading tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Remember
- Exact file paths always
- Complete code in every step — if a step changes code, show the code
- Exact commands with expected output
- DRY, YAGNI, TDD
- Do not commit or push unless explicitly authorized

## Self-Review

After writing the complete plan, look at the spec with fresh eyes and check the plan against it. This is a checklist you run yourself.

**1. Spec coverage:** Skim each section/requirement in the spec. Can you point to a task that implements it? List any gaps.

**2. Placeholder scan:** Search your plan for red flags — any of the patterns from the "No Placeholders" section above. Fix them.

**3. Type consistency:** Do the types, method signatures, and property names you used in later tasks match what you defined in earlier tasks? A function called `clearLayers()` in Task 3 but `clearFullLayers()` in Task 7 is a bug.

If you find issues, fix them inline. No need to re-review — just fix and move on. If you find a spec requirement with no task, add the task.
