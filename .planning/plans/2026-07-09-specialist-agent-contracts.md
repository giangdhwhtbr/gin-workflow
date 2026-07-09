# Plan: Specialist Agent Contracts

## Objective
Define and implement Beads-coupled specialist agent contracts for architecture, full-stack implementation, QA, and technical documentation, while clarifying `codebase-mapper` as a reusable evidence scanner and updating technical documentation guidance to support split documentation files and Mermaid diagrams.

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
- `agent_guidance`:
  - `solution-architect`: `high_reasoning`
  - `full-stack-developer`: `standard_impl`
  - `qa-agent`: `standard_impl`
  - `docs-writer`: `cheap_simple`
  - `codebase-mapper`: `cheap_simple`
- `override_rule`: Use `high_reasoning` when architecture boundaries, dependency sequencing, security, concurrency, or failing verification require deeper synthesis. Use `cheap_simple` only for evidence gathering, formatting, and low-risk documentation updates.

## Requirement Analysis
- Problem statement: The plugin has a few lightweight agents, but it does not yet define a complete specialist set for architecture, implementation, QA, and documentation work. The existing `technical-documentation` skill writes one combined document and does not describe split docs, Mermaid diagrams, docs confirmation behavior, model guidance, or optional codegraph use.
- Success criteria: The repository contains clear specialist agent contracts; `codebase-mapper` is explicitly a scanner rather than a writer; `docs-writer` can be invoked directly and will gather mapping evidence when needed; technical documentation guidance supports split output files and Mermaid diagrams; model guidance is provider-neutral and advisory; optional codegraph use is documented as preferred but never required.
- Constraints: Beads remains the durable task-state source. Plans own approved decomposition. Agent files should remain concise and defer shared lifecycle rules to canonical docs. Model guidance must use abstract model classes, not provider-specific model names. Codegraph must not be a hard dependency.
- Non-goals: Implementing runtime model routing, changing Beads schema, adding mandatory codegraph installation, rewriting every command, committing or pushing changes, or making docs generation fully automatic without user/task authorization.

## Approach Options
### Option 1: Beads-coupled specialist agents with reusable role contracts
- Summary: Add or update concise agent markdown files under `plugins/gin-workflow/src/agents/`, each with purpose, inputs, outputs, boundaries, model guidance, and handoff expectations. Keep shared lifecycle and close-out rules in existing canonical docs.
- Pros: Matches the current repository pattern, avoids duplicating lifecycle policy, gives orchestrators consistent contracts, and keeps agents reusable across Beads-backed workflows.
- Cons: Requires agents to follow references to lifecycle and verification docs rather than having every rule inline.

### Option 2: Heavy standalone agent playbooks
- Summary: Put full procedures, examples, Beads policy, verification rules, and handoff templates inside each agent file.
- Pros: Each agent is self-contained and easy to read in isolation.
- Cons: Duplicates canonical repo policy, increases drift risk, and makes future lifecycle updates harder.

### Option 3: Command-first workflows
- Summary: Add slash commands such as `/architect`, `/qa`, and `/full-stack` that dispatch specialists with structured prompts, using agent files as secondary references.
- Pros: Gives users direct entry points for each workflow.
- Cons: Premature before stable agent contracts exist and risks making command text the real policy surface.

### Recommended Approach
- Selected option: Option 1.
- Reasoning: The repository already uses concise agent definitions and canonical lifecycle docs. Adding clear role contracts first gives the plugin stable building blocks. Commands can be added later if repeated usage patterns justify them.

## Scope
- In scope: Agent contract files, technical documentation skill guidance, the `/tech-doc` command text if needed, smoke-test coverage for installed agent/skill files, and docs references only when needed to keep lifecycle ownership clear.
- Out of scope: Runtime orchestration engine changes, provider-specific model selection, mandatory codegraph integration, automatic commits, and generated distribution files edited by hand.

## Tasks
### Track 1: Clarify codebase-mapper as evidence scanner
- **Dependencies**: none
- **Files**: `plugins/gin-workflow/src/agents/codebase-mapper.md`
- **Model class**: `cheap_simple`
- **Acceptance criteria**: The agent contract says `codebase-mapper` scans but does not write durable docs; it produces structured findings with concrete file references, uncertainty, and recommended follow-up inspection; it uses codegraph when available but falls back to direct repository inspection; it reports whether codegraph was used.
- **Estimated complexity**: low

### Track 2: Add solution-architect agent
- **Dependencies**: Track 1
- **Files**: `plugins/gin-workflow/src/agents/solution-architect.md`
- **Model class**: `high_reasoning`
- **Acceptance criteria**: The agent contract defines architecture responsibilities, Beads/plan input expectations, output format, Mermaid diagram use when useful, boundaries against implementation, and escalation/handoff behavior.
- **Estimated complexity**: low

### Track 3: Add full-stack-developer agent
- **Dependencies**: Track 2
- **Files**: `plugins/gin-workflow/src/agents/full-stack-developer.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**: The agent contract defines scoped implementation behavior across frontend/backend work, requires reading the bead and approved plan before edits, preserves architecture boundaries, reports verification evidence, and flags out-of-scope architecture changes instead of silently redefining them.
- **Estimated complexity**: low

### Track 4: Add qa-agent
- **Dependencies**: Track 2
- **Files**: `plugins/gin-workflow/src/agents/qa-agent.md`
- **Model class**: `standard_impl`
- **Acceptance criteria**: The agent contract defines acceptance-criteria verification, regression checks, reproducible issue reporting, test execution expectations, and limits remediation to explicit assignments.
- **Estimated complexity**: low

### Track 5: Add docs-writer agent
- **Dependencies**: Track 1
- **Files**: `plugins/gin-workflow/src/agents/docs-writer.md`
- **Model class**: `cheap_simple`
- **Acceptance criteria**: The agent contract defines docs writing responsibilities, requires mapper evidence or direct fallback mapping, writes only when authorized by user/task context, separates verified facts from inference, owns final prose and Mermaid diagrams, and clarifies that users do not need to invoke `codebase-mapper` manually first.
- **Estimated complexity**: low

### Track 6: Update technical-documentation skill for split docs
- **Dependencies**: Track 1, Track 5
- **Files**: `plugins/gin-workflow/src/skills/technical-documentation/SKILL.md`, `plugins/gin-workflow/src/commands/tech-doc.md`
- **Model class**: `cheap_simple`
- **Acceptance criteria**: The skill supports either a single combined doc or split files such as `Architecture.md`, `Stack.md`, `Database.md`, `Backend.md`, `Frontend.md`, `Operations.md`, and `Risks.md`; it requires concrete evidence, optional Mermaid diagrams where they clarify structure or flow, explicit uncertainty, and confirmation or task authorization before writing docs.
- **Estimated complexity**: medium

### Track 7: Update installation smoke coverage
- **Dependencies**: Tracks 2, 3, 4, 5, 6
- **Files**: `tests/install_smoke_test.sh`
- **Model class**: `standard_impl`
- **Acceptance criteria**: The smoke test verifies the new agent files are included in plugin installation output and that the technical-documentation skill includes the split-doc/codegraph guidance.
- **Estimated complexity**: low

## Integration
- **Branch**: current workspace branch
- **Merge strategy**: sequential

## Validation
- [ ] Review all new and updated agent contracts for consistent input/output sections, model guidance, and Beads lifecycle references.
- [ ] Review `technical-documentation` and `/tech-doc` text for agreement on split-doc defaults, confirmation behavior, Mermaid usage, and codegraph fallback.
- [ ] Run `bash tests/install_smoke_test.sh`.
- [ ] Run `git status`.
- [ ] Confirm Beads task closure only after validation and handoff evidence are available.

## Notes
- Codegraph is preferred when exposed by the platform, but it is never required. Direct repository inspection remains the fallback and must be enough to complete mapping.
- Codegraph-derived claims should be treated as index hints until verified against concrete files.
- `docs-writer` may internally call or perform mapping when invoked directly; users should not have to remember to run `codebase-mapper` first.
- Model guidance is planning metadata and agent dispatch advice, not Beads state or a hard execution gate.
