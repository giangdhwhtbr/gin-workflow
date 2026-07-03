# Persuasion principles for skill design

Skills that enforce discipline have a hard job: they have to convince an agent under pressure to follow a rule the agent has incentives to break. The wording matters. Research on persuasion (Cialdini's classic taxonomy, validated against LLMs by Meincke et al., 2025) gives us a small toolkit of principles that move compliance — not because manipulation is the goal, but because critical practices need to survive contact with rationalization.

**Research foundation.** Meincke et al. (2025) tested seven persuasion principles across N≈28,000 conversations and found that adding persuasion techniques to prompts roughly doubled compliance rates (33% → 72%, p < 0.001). The strongest movers were authority, commitment, and scarcity.

**Ethical use.** The test is simple: would the user benefit from this technique if they fully understood it? Using authority phrasing to make a TDD skill bulletproof passes that test. Using authority phrasing to make an agent comply with something *bad* for the user does not.

## The seven principles

### 1. Authority

Compliance with directives from credible sources. In a skill, this looks like imperative language and non-negotiable framing.

When to use:

- Discipline-enforcing skills (TDD, verification, debugging protocol).
- Safety-critical practices.
- Established best practices the team has already agreed on.

Example:

```markdown
Wrote code before the test? Delete it. Start over. No exceptions.
```

vs. weaker:

```markdown
Consider writing tests first when feasible.
```

The first version cuts off rationalization paths. The second invites them.

### 2. Commitment

Consistency with prior actions, statements, or public declarations. In skill design, this is "make the agent state what it's doing, then it'll keep doing it".

How to apply:

- Require an announcement: "Announce at start: 'Using `:foo` to do X'."
- Force explicit choices ("Choose A, B, or C") rather than open-ended responses.
- Use a checklist (TaskCreate) the agent ticks through.

Example:

```markdown
When you find a relevant skill, announce: "Using <skill> to <purpose>."
```

vs.

```markdown
Consider letting the user know which skill you're using.
```

The announcement creates a public commitment the agent has now made; the next step has to be consistent with that commitment.

### 3. Scarcity

Urgency from time limits or limited opportunities. In skills, this prevents "I'll do it later" drift.

How to apply:

- Time-bound requirements ("before proceeding", "before the next task").
- Sequential dependencies ("immediately after X").

Example:

```markdown
After completing a task, request the code review immediately —
before starting the next task.
```

vs.

```markdown
Code reviews can happen when convenient.
```

"Convenient" never arrives; "immediately" forces the work into the moment.

### 4. Social proof

Conformity to what's normal or what others do. In skills, this establishes norms — "this is how things are done here".

How to apply:

- Universal patterns ("every time", "always").
- Failure-mode statements that frame the violation as the deviation.

Example:

```markdown
Checklists without TaskCreate tracking get steps skipped. Every time.
```

vs.

```markdown
Some people find TaskCreate helpful for checklists.
```

The first version tells the agent that *not* using TaskCreate is the deviation. The second leaves it open.

### 5. Unity

Shared identity, "we-ness", in-group belonging. In skills, this fits collaborative practices and non-hierarchical norms.

When to use:

- Practices that depend on collaboration ("we both want quality").
- Establishing team culture rather than enforcing rules.

Example:

```markdown
We're colleagues working on the same code. I need your honest technical
judgment, not agreement for agreement's sake.
```

vs.

```markdown
You should probably tell me if I'm wrong.
```

Unity invites; "should probably" defers.

### 6. Reciprocity

Obligation to return benefits received. In a skill, this rarely lands cleanly — most skill content isn't a "favor" the agent owes anyone for. Use sparingly, if at all.

### 7. Liking

Preference for cooperating with people we like. **Avoid this for compliance work.** It conflicts with the honesty needed in technical feedback and creates sycophancy ("you're absolutely right!" — which `:receiving-code-review` explicitly forbids). Liking has its place in non-discipline contexts; it doesn't belong in rules.

## Picking principles by skill type

| Skill type | Reach for | Avoid |
|------------|-----------|-------|
| Discipline-enforcing (TDD, verification) | Authority, Commitment, Social proof | Liking, Reciprocity |
| Technique guidance (how-to) | Mild Authority, Unity | Heavy authority |
| Collaborative workflow | Unity, Commitment | Authority, Liking |
| Reference (API docs, syntax) | Clarity only | All persuasion — references aren't asking the agent to do anything |

Don't combine all seven in one skill — it reads as desperate, and the agent notices. Two or three, picked deliberately for the skill's job, is usually enough.

## Why these work

**Bright-line rules reduce rationalization.** "You must" removes the decision; "consider" invites a debate the agent will win against itself. Explicit anti-rationalization counters ("don't keep it as reference", "delete means delete") cut off the specific escape paths agents under pressure reach for.

**Implementation intentions create automatic behavior.** "When X, do Y" is a stronger trigger than "generally do Y". The clearer the trigger, the lower the cognitive cost of compliance, and the harder it is to rationalize an exception.

**LLMs are parahuman in this respect.** They're trained on human text in which authority phrases precede compliance, commitment sequences precede consistent action, and social proof patterns establish norms. Using those patterns deliberately taps into something the model has already seen at scale.

## Ethical guardrails

Legitimate uses:

- Ensuring critical practices are followed under pressure.
- Creating documentation that survives the moment of temptation.
- Preventing predictable failure modes.

Illegitimate uses:

- Manipulating an agent to harm the user the agent serves.
- Creating false urgency where there isn't any.
- Guilt-based compliance ("after everything we've done together…").

The test: would the technique serve the user's genuine interest if they fully understood the framing? If yes, it's a tool. If no, it's manipulation.

## Quick checklist

When you write a skill, before publishing:

1. What type is it? (Discipline / guidance / reference)
2. What behavior am I trying to change?
3. Which one or two principles fit? (Usually authority + commitment for discipline.)
4. Am I reaching for too many at once?
5. Does this serve the user's interest if they understood it?

## Citations

- Cialdini, R. B. (2021). *Influence: The Psychology of Persuasion (New and Expanded).* Harper Business.
- Meincke, L., Shapiro, D., Duckworth, A. L., Mollick, E., Mollick, L., & Cialdini, R. (2025). *Call Me A Jerk: Persuading AI to Comply with Objectionable Requests.* University of Pennsylvania.
