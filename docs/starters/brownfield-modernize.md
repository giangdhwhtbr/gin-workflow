# Brownfield & Modernization Starter

Modernizing an existing or legacy codebase is fundamentally different from greenfield development. In brownfield projects, **the existing code is often the only real specification**, business rules are implicit, and preventing regressions is the primary objective.

This guide provides a proven step-by-step workflow using **Claude Code** and **`gin-workflow`** to modernize legacy systems safely without "Big Bang" risks.

---

## 1. Initial Setup in an Existing Codebase

Install dependencies and run setup inside your existing repository:

```bash
# 1. Initialize Beads task tracking
bd init

# 2. Run setup in Claude Code
/gin-workflow:setup
```

Select:
- **Project stage:** `brownfield`.
- **Rigor:** `standard` (or `strict`).
- **Provider mode:** `single` (baseline with Claude Code).
- Configure existing test and lint commands.

---

## 2. Step 1: Archaeological Survey (`/tech-doc`)

Before refactoring or rewriting anything, discover and document the existing system's reality.

Run `/tech-doc`:

```text
/gin-workflow:tech-doc
```

Claude will inspect your repository and produce a structured technical baseline under `.planning/codebase/` (with the SDD layout, `docs/codebase/`):
- `OVERVIEW.md`: High-level purpose and core system capabilities.
- `FEATURES.md`: Feature catalog and the map from each feature to frontend screen, API endpoint, backend handler, and data.
- `API.md`: Endpoints the system exposes, with handler, auth, and summary.
- `STACK.md`: Frameworks, runtimes, database drivers, and legacy libraries.
- `INTEGRATIONS.md`: Third-party APIs, message queues, external databases.
- `ARCHITECTURE.md`: Existing architectural boundaries and runtime flows.
- `STRUCTURE.md`: Directory layout and where things live.
- `CONVENTIONS.md`: Coding patterns the existing code follows.
- `TESTING.md`: Test setup, coverage, and gaps.
- `CONCERNS.md`: Technical debt, performance bottlenecks, security risks, and fragile modules.

If [CodeGraph](../guides/recommended-tools.md) is installed, `/gin-workflow:setup` offers `codegraph init` on brownfield and legacy repositories, and `tech-doc` uses the index to map structure and call paths faster.

Commit these documents as your team's documented baseline.

Next, turn the baseline into a roadmap of epics with `/gin-workflow:roadmap` (see the [Brownfield Walkthrough](brownfield-walkthrough.md)).

---

## 3. Step 2: Establish Baseline Living Specs (SDD)

When refactoring a legacy capability, you must capture its **current behavior** before changing code.

1. Ensure `artifacts.layout: sdd` is set in `.agent-workflow/config.yaml`. `/gin-workflow:migrate-specs` sets it and offers to seed living specs from the tech-doc set.
2. For each capability you intend to modernize, create a living spec in `docs/specs/<capability>/spec.md` from `gin-workflow specs template spec.md`, with explicit requirement IDs (`gin-workflow specs next-id <capability>`, e.g. `REQ-AUTH-001`), and run `gin-workflow specs lint`.
3. Detail all legacy edge cases, validation rules, and error codes identified during code exploration.

```markdown
### REQ-AUTH-001: Legacy Password Hashing Support
The authentication service MUST verify legacy MD5/SHA1 hashes while seamlessly upgrading authenticated users to bcrypt/argon2id.
```

---

## 4. Step 3: Architecture Strategy — Strangler Fig Pattern

Never attempt a "Big Bang" rewrite. Instead, use the **Strangler Fig Pattern**: modernize one bounded context at a time behind a stable facade or router.

1. **Define Areas (team mode):** With [team mode](../guides/team.md), configure `team.areas` in `.agent-workflow/config.yaml` so plan tracks stay inside either the legacy or the modernized paths (`team check-plan` rejects a track that crosses areas):
   ```yaml
   team:
     areas:
       legacy_core:
         paths: ["legacy/**"]
         lead: legacy_lead
       modern_api:
         paths: ["src/**", "tests/**"]
         lead: api_lead
   ```
2. **Deploy an API Gateway or Facade** (your own infrastructure; `gin-workflow` does not provide one): Route traffic for modernized endpoints to the new implementation while letting unmigrated requests pass through to the legacy core.

---

## 5. Step 4: Regression Shields & Parity Testing

In a modernization project, passing unit tests is not enough; you must prove **behavioral parity**.

### Characterization / Parity Testing
Add parity test checks comparing legacy vs. modern behavior:
1. Capture recorded production or staging payloads (Golden Master).
2. Execute the payload against both legacy and modern implementations.
3. Assert zero unexpected diff in responses.

### Test Case Pinning with `gin-qa`
If using the `gin-qa` add-on:
1. Run `/gin-qa:cases <capability>` to generate test cases pinned to requirement hashes:
   ```markdown
   ### TC-AUTH-001: Legacy password migration verification
   REQ: REQ-AUTH-001@hash
   Type: integration
   ...
   ```
2. If requirements change, `gin-qa cases plan` flags stale, missing, or obsolete test cases.

---

## 6. Step 5: Migration Execution Cycle

When ready to modernize a module, run the standard guarded lifecycle:

1. **Discuss (`/gin-workflow:discuss <migration-scope>`):**
   - Propose refactoring/migration architecture.
   - Clarify data migration strategy (dual-write, backfill scripts, rollback criteria).
   - Confirm design to record `requirement-confirmed`.

2. **Plan (`/gin-workflow:plan <migration-scope>`):**
   - Track 1: Modern module scaffolding & contracts.
   - Track 2: Parity tests (verifying legacy vs new).
   - Track 3: Dual-write or data backfill migration.
   - Track 4: Router/proxy redirection to modern implementation.
   - Track 5: Legacy cleanup (scheduled after verification).

3. **Orchestrate & Execute (`/gin-workflow:orchestrate`, `/gin-workflow:execute`):**
   - Builds within isolated Git worktrees under `.planning/worktrees/`.
   - Writes tests first, implements, runs independent review per track.

4. **Quality checks (git hooks):**
   - `pre-commit` runs lint and typecheck; `pre-push` runs the unit tests, parity tests, and data validation scripts you configured in `verify.checks`. They must pass with 0 errors.

5. **Ship (`/gin-workflow:ship`):**
   - Merge or open a Pull Request with all evidence attached.

---

## 7. Next Steps

- **Following the whole flow with prompts per role?** See the [Brownfield Walkthrough](brownfield-walkthrough.md).
- **Collaborating with BA, Dev, and Tester?** Read [Team Roles Guide](team-roles.md).
- **Managing test cases and E2E automation?** See the [QA Guide](../guides/qa.md).
- **Scale execution with multiple providers?** Check [Multi-Agent Routing](../advanced/multi-agent-routing.md).
