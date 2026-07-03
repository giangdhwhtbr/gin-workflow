# Spec document reviewer — prompt template

Dispatched as a subagent during step 9 of `:brainstorming` (inline self-review augmented by an independent reviewer). The reviewer's job is to flag real problems that would cause the planner to misbuild — not to polish prose.

**When to dispatch:** after the spec has been written to `.planning/specs/YYYY-MM-DD-<topic>-design.md` and the inline self-review has completed.

**Subagent type:** general-purpose

## Prompt body

Pass this body to the Task tool, with `[SPEC_PATH]` replaced by the actual path:

```
You are reviewing a design spec for completeness, internal consistency, and readiness
for the planning step. You are not editing it — only flagging problems.

Spec to review: [SPEC_PATH]

Read the entire file. Look at the sections and how they fit together.

## What counts as a problem worth flagging

| Category | Definition |
|----------|------------|
| Completeness | TODO, TBD, "see below" with no follow-up, or a section that's a heading with no body |
| Consistency | Two parts of the spec disagree (e.g., the architecture says component X owns this, but the file structure puts it elsewhere) |
| Clarity | A requirement that two readers could interpret two different ways, where the choice would change the implementation |
| Scope | The spec covers more than one independently-implementable subsystem; planner cannot break it into one plan |
| YAGNI | A feature appears in the spec but the user never asked for it (over-engineering) |

## Calibration — flag only real problems

Approve unless there is a serious gap. The bar is "would this cause the planner to
build the wrong thing or get stuck?" — not "could this sentence be smoother?".

Do NOT flag:
- Minor wording preferences
- Sections of uneven length (some are simply more nuanced than others)
- Style choices that work either way
- Speculative concerns about edge cases the spec didn't enumerate, unless those edge
  cases are reasonably foreseeable

Do flag:
- Sections that are blank or placeholder
- Architecture-vs-description contradictions
- Requirements ambiguous enough to result in two different implementations
- Scope creep — the spec mixes goals and non-goals or covers multiple projects

## Output

Reply with exactly this structure:

## Spec review

**Status:** Approved | Issues found

**Issues (if any):**
- `<section heading>` — <one-sentence problem statement> — <one-sentence reason it
  blocks planning>

**Recommendations (advisory; do not block approval):**
- <suggestion for the spec author>

If status is Approved, the Issues section may be empty.
```

## What the orchestrator does with the response

- **Status: Approved** → proceed to step 10 (user reviews the spec).
- **Status: Issues found** → fix each blocking issue inline, re-run step 9 self-review, then either re-dispatch this reviewer or proceed if the issues were trivial. Recommendations are advisory; ignore unless they catch your eye.

The reviewer is a second pair of eyes, not a gate. The user remains the final reviewer in step 10.
