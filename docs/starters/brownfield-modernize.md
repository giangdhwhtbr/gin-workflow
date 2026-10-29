# Brownfield modernization

In an existing codebase the code is often the only specification, so preventing regressions comes first. This page suggests a strategy for replacing a legacy system piece by piece. gin-workflow enforces only two parts of it: track areas (`team.areas`) and the requirement hashes that gin-qa test cases pin. The rest is a convention your team follows. The [brownfield walkthrough](brownfield-walkthrough.md) covers setup, the survey, the roadmap and every lifecycle stage.

## Capture current behavior first

Before changing a capability, describe its current behavior as living specs, including the legacy edge cases, validation rules, and error codes. See [migrating to the SDD layout](../guides/sdd.md#migrating) for the setup.

```markdown
### REQ-AUTH-001: Legacy password hashing support
The authentication service MUST verify legacy MD5/SHA1 hashes while upgrading authenticated users to bcrypt/argon2id.
```

## Strangler fig

Modernize one bounded context at a time behind a stable facade or router instead of attempting an all-at-once rewrite.

With [team mode](../guides/team.md), configure `team.areas` in `.agent-workflow/config.yaml` so plan tracks stay inside either the legacy or the modernized paths (`gin-workflow team check-plan` rejects a track that crosses areas):

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

Deploy an API gateway or facade to route traffic for modernized endpoints to the new implementation while letting unmigrated requests pass through to the legacy core. The facade or gateway is your own infrastructure; gin-workflow does not provide one.

## Parity and characterization tests

In a modernization project, passing unit tests does not show that the new code behaves like the old. Parity tests compare the two:
1. Capture recorded production or staging payloads (Golden Master).
2. Execute the payload against both legacy and modern implementations.
3. Assert zero unexpected diff in responses.

With the gin-qa add-on, test cases pin the hash of the requirement they test, so a changed requirement shows its stale cases: see the [QA add-on](../guides/qa.md).

## Migration cycle

For the full sequence of stages and approvals, see [lifecycle and gates](../concepts/lifecycle.md). A migration adds these steps:

- In `/gin-workflow:discuss`, settle the data migration strategy (dual-write or backfill) and the rollback criteria.
- In `/gin-workflow:plan`, a suggested split into five tracks:
  - Track 1: Modern module scaffolding and contracts.
  - Track 2: Parity tests verifying legacy versus new behavior.
  - Track 3: Dual-write or data backfill migration.
  - Track 4: Router or proxy redirection to the modern implementation.
  - Track 5: Legacy cleanup scheduled after verification.
- Parity tests and data validation scripts run in the `pre-push` hook when the `verify.checks.test` command runs them ([configuration](../reference/config.md#verifychecks)).

## Related

- [Brownfield modernization deck](../presentations/brownfield-modernization.html) ([PPTX](../presentations/brownfield-modernization.pptx)) for executive and team presentations.
- [Brownfield walkthrough](brownfield-walkthrough.md) for the end-to-end flow with prompts.
- [Team roles](../roles.md) for role ownership and reading paths.
- [QA add-on](../guides/qa.md) for test cases and end-to-end automation.
- [gin-orchestrator](../orchestrator/README.md) for multi-provider execution.
