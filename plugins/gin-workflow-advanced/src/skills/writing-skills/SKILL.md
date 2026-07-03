---
name: writing-skills
description: Use this skill when authoring a new skill, editing an existing skill, or verifying that a skill actually changes agent behavior. Treats skill authoring as TDD for documentation — write a failing pressure scenario first, then write the skill that makes the agent comply.
---

# Writing skills for this plugin

A skill is a reference document that helps a future agent recognize and apply a proven technique. The same discipline that produces good code produces good skills: write the failing test first (a scenario where the agent does the wrong thing), watch it fail, write the minimum skill that makes the agent comply, and refactor to close the loopholes that turn up under pressure.

**Required background:** read `:test-driven-development` first if you haven't. This skill is the same RED → GREEN → REFACTOR loop, applied to documentation rather than code.

## What counts as a skill

A skill is:

- A reusable technique, pattern, or reference that future agents can find and apply.
- Backed by evidence that it changes behavior — not "I think this is a good idea".

A skill is NOT:

- A narrative about how you solved one specific problem.
- A duplicate of conventions that belong in `CLAUDE.md` or `AGENTS.md` (project-specific).
- Something a regex or a validator could enforce mechanically.

## When to create a skill

Write a skill when:

- The technique wasn't obvious to you the first time and you'd want to find it again.
- It applies broadly, not just to this project.
- A future agent on a different task would benefit.

Don't write a skill when:

- The technique is one-off.
- It's already well-documented elsewhere (point to that doc instead).
- It's a project-specific convention (put it in `CLAUDE.md`).
- It's mechanical enough to enforce with tooling — automate it instead.

## TDD mapping for skills

| TDD concept | Skill authoring equivalent |
|-------------|----------------------------|
| Test case | Pressure scenario tested against a subagent |
| Production code | The SKILL.md file |
| RED — test fails | Agent violates the rule without the skill present |
| GREEN — test passes | Agent complies with the skill present |
| Refactor | Close loopholes the agent finds; tighten phrasing |
| Write the test first | Run the baseline scenario *before* writing the skill |
| Watch it fail | Capture exact rationalizations the agent uses, verbatim |
| Minimum code | Write only enough skill to address those specific violations |
| Watch it pass | Verify compliance with the same scenario |
| Refactor cycle | New rationalization surfaces → plug it → re-verify |

The same loop. Different artifact.

## The core rule

**No skill without a failing pressure scenario first.**

If you wrote the skill before testing it, you wrote the skill you *think* is needed, not the skill that actually changes behavior. Delete it and run the baseline scenario first. This applies to new skills *and* to edits of existing ones.

## Skill types

| Type | Description | Example |
|------|-------------|---------|
| **Technique** | A concrete method with steps to follow | `condition-based-waiting`, `root-cause-tracing` |
| **Pattern** | A way of thinking about a class of problems | thinking in interfaces, decomposing by responsibility |
| **Reference** | API docs, syntax guides, tool documentation | language-specific guides, framework references |
| **Discipline** | Rule-enforcing skills that resist rationalization | `:test-driven-development`, `:verification-before-completion` |

Different types need different testing approaches — see `testing-skills-with-subagents.md`.

## Directory structure

```
skills/
  skill-name/
    SKILL.md              # required main file
    supporting-file.md    # optional reference docs
    prompt-template.md    # optional load-bearing prompt template
```

Names use letters, numbers, and hyphens only — no parentheses, no special characters.

**When to add supporting files:**

- **Heavy reference (100+ lines)** — API docs, comprehensive technique guides.
- **Reusable prompt templates** — when the skill dispatches a subagent, give it a separate file.

**Keep inline in SKILL.md:**

- Principles, concepts, the workflow itself.
- Code patterns under ~50 lines.
- Anything that benefits from being read together.

## SKILL.md structure

Every SKILL.md begins with YAML frontmatter and follows a similar shape:

```markdown
---
name: skill-name-with-hyphens
description: Use when [specific triggering conditions and symptoms — keep it about WHEN, not WHAT]
---

# Skill title

Two- or three-paragraph orientation: what this skill is, what it produces.

## The core rule (for discipline skills) or Overview (for techniques)

The single most important sentence the skill enforces, plus the reasoning.

## When to use / when to apply

Symptoms, situations, edge cases. Use a small flowchart only if a decision is genuinely non-obvious.

## The process / step-by-step

Numbered steps. Concrete actions. Code where it helps.

## Common mistakes / rationalizations

Table form. The mistake on the left, the fix on the right.

## Where this skill sits

Table connecting this skill to its caller, its callees, and its artifacts.
```

## The description field — the most load-bearing line

Claude reads the `description` to decide whether to load this skill for the current task. A bad description means the skill is invisible.

**Cardinal rule for description:** describe **WHEN to use the skill**, not WHAT it does. A description that summarizes the workflow becomes a shortcut Claude takes *instead of* reading the skill — it'll follow the description's summary and skip the skill body.

| Bad | Good |
|-----|------|
| `description: Helps with TDD` (vague) | `description: Use when implementing any feature or bugfix, before writing implementation code` |
| `description: Use for TDD - write test first, watch it fail, minimal code, refactor` (summarizes the workflow) | `description: Use when implementing any feature or bugfix, before writing implementation code` |
| `description: I help you with async tests` (first person) | `description: Use when tests have race conditions, timing dependencies, or pass/fail inconsistently` |

Other rules:

- Third person. The description is injected into a system prompt; first or second person reads strangely there.
- Start with "Use when…" to focus on triggers.
- Cover concrete symptoms, not abstract concepts ("race conditions, timing dependencies" rather than "async issues").
- Keep under ~500 characters when possible (frontmatter has a hard 1024-char ceiling).

## Keyword coverage

The description and skill body should contain words the agent might search for:

- Error messages: "ENOTEMPTY", "race condition", "Hook timed out".
- Symptoms: "flaky", "hanging", "pollution", "context drift".
- Synonyms: "timeout / hang / freeze", "cleanup / teardown / afterEach".
- Tools: actual command names, library names, file types.

A skill named `condition-based-waiting` is more discoverable than one named `async-test-helpers` — name by what you're doing, in active voice (gerunds work well: `creating-skills`, `debugging-with-logs`, `testing-skills`).

## Token budget

Skills are loaded into context when activated. Be terse:

- SKILL.md body: ideally under 500 lines, hard limit ~600.
- Frequently-loaded skills (entry points): aim for 200 lines or fewer.
- Move heavy reference content to a separate file in the same directory; link from SKILL.md.

Verification:

```bash
wc -l skills/<name>/SKILL.md
```

## Cross-references between skills

Link to other skills using the `:<name>` form, with a marker for required vs. advisory:

- `**Required upstream:** :writing-plans` — the caller must have produced the plan before invoking this skill.
- `**See also:** :test-driven-development` — relevant context but not strictly required.

Avoid `@`-prefixed force-loads (they consume context immediately, every time the calling skill is loaded).

## Flowcharts

Use a flowchart when:

- A decision point is genuinely non-obvious and could go either way.
- A loop has multiple exits and the agent might stop too early.

Don't use a flowchart for:

- Linear instructions — use numbered lists.
- Reference material — use tables.
- Code examples — use markdown code blocks.

When you do use one, make node labels semantic ("verify that the test fails for the right reason") rather than mechanical ("step1, helper2"). See `:test-driven-development` for examples of useful flowcharts.

## Code examples

One excellent example beats many mediocre ones. The example should be:

- Complete and runnable.
- Commented for *why*, not what.
- Drawn from a real scenario, not a toy.
- Easy to adapt — not a fill-in-the-blank template.

Pick the language closest to where the technique is most often needed (TypeScript / JavaScript for testing techniques, shell or Python for system debugging, etc.). Don't dilute the example by re-implementing it in five languages.

## Closing rationalization loopholes (discipline skills)

Discipline skills exist because agents under pressure rationalize their way around rules. A bare statement of the rule isn't enough; the skill has to anticipate and explicitly forbid the workarounds.

Pattern:

```markdown
**The rule:** delete code written before the test.

**No exceptions:**
- Don't keep the code as "reference".
- Don't "adapt" it while writing the test.
- Don't read it again to see what it did.
- Delete means delete.
```

The bullets aren't redundant — they cut off specific rationalizations agents reach for. See `persuasion-principles.md` for why this works (Cialdini / Meincke research on authority, commitment, scarcity).

A typical discipline skill ends with two reinforcement sections:

- **Common rationalizations** table — excuse on the left, reality on the right.
- **Red flags** list — phrases the agent might be thinking that signal the rule is about to be violated.

Both are populated from real testing. See `testing-skills-with-subagents.md` for the loop.

## Anti-patterns to avoid

- **Narrative example.** "On 2025-10-03 we hit this empty-projectDir bug…" — too specific, not reusable. Distill the principle.
- **Multi-language dilution.** Three half-quality translations beat zero, but one strong example beats three mediocre ones.
- **Code embedded in flowchart nodes.** Hard to read, can't copy-paste. Use a code block alongside the flowchart.
- **Generic node labels.** `helper1, step3, pattern2` carries no meaning. Use semantic names.
- **Repeating cross-referenced content.** If `:test-driven-development` already covers the red-green-refactor cycle, link to it instead of restating it.
- **Pretending nothing was tested.** A skill that claims an effect should describe how that effect was verified.

## Skill creation checklist

**RED phase — write a failing test:**

- [ ] Construct pressure scenarios with three or more combined pressures (for discipline skills).
- [ ] Run the scenarios *without* the skill.
- [ ] Document the agent's choices and rationalizations verbatim.
- [ ] Identify the patterns in those rationalizations.

**GREEN phase — write the minimum skill:**

- [ ] Frontmatter with `name` (hyphens only) and `description` (third person, "Use when…", under 500 chars).
- [ ] Description describes WHEN, not WHAT.
- [ ] Keyword coverage in the body (errors, symptoms, tools).
- [ ] Overview / core rule in the first 50 lines.
- [ ] Address each baseline rationalization from RED.
- [ ] One excellent example, not three mediocre ones.
- [ ] Run the scenarios *with* the skill — confirm compliance.

**REFACTOR phase — close loopholes:**

- [ ] Identify any new rationalizations from compliance testing.
- [ ] Add explicit counters in the body.
- [ ] Build the rationalizations table.
- [ ] Build the red-flags list.
- [ ] Re-test until no new rationalizations appear.

**Quality checks:**

- [ ] Body under ~500 lines (heavy content moved to supporting files).
- [ ] Flowchart only where a decision is non-obvious.
- [ ] "Where this skill sits" table at the end.
- [ ] No narrative storytelling.
- [ ] Cross-references use `:<name>`, no `@` force-loads.
- [ ] Supporting files only for tools or heavy reference content.

## Where this skill sits

| Aspect | Detail |
|--------|--------|
| Direct skill call | `:writing-skills` |
| Required background | `:test-driven-development` |
| Reads | the existing skill (when editing); the source of evidence (when authoring new) |
| Writes | SKILL.md and any supporting files |
| Supporting docs in this directory | `testing-skills-with-subagents.md`, `anthropic-best-practices.md`, `persuasion-principles.md` |
| Deferred to v0.2.0 | the graphviz conventions and `render-graphs.js` helper script (B3 bucket; not bundled in this release) |
