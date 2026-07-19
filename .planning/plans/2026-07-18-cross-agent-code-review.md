# Plan: Cross-Agent Code Review Workflow

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a persistent, auditable cross-agent code review workflow where independent implementation and reviewer agents exchange findings, fixes, disputes, and human decisions through Git-committed ledger artifacts — replacing the current single-session code-reviewer subagent pattern.

**Architecture:** A review ledger (`review.json` + generated `review.md`) lives under `.planning/<bead-id>/` and is committed to a dedicated `bead/<bead-id>` review branch. An append-only, hash-chained event log is the authoritative representation of review state. A Python CLI (`review-ledger.py`) manages all ledger mutations, transition validation, and Markdown rendering. Existing skills (`requesting-code-review`, `receiving-code-review`, `bead-worker`, `verification-before-completion`, `ship`) are extended to consume the ledger contract.

**Tech Stack:** Python 3.10+ (CLI + library), JSON (ledger), Bash (Git operations), Markdown (generated output)

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
- `override_rule`: Use `high_reasoning` for Track 1 (core data model) and Track 5 (finding state machine) where protocol correctness is critical.

## Global Constraints

- Python 3.10+ minimum; no external dependencies beyond stdlib for the core library.
- All ledger mutations go through the CLI/library — never direct JSON edits.
- Event hashes use RFC 8785 JSON Canonicalization Scheme (JCS); implementation may use a vendored or minimal JCS module.
- Git operations never use `--force` push.
- The workflow must not stash, reset, clean, or discard unrelated user changes.
- Beads remains the source of truth for runtime task status; the ledger is authoritative for review history.
- Existing skill files are extended, not replaced — preserve all current behavior.
- No new external MCP servers or network dependencies.

## Requirement Analysis

- **Problem statement:** The current code review workflow uses a single-session subagent pattern with no persistent state, no audit trail, no cross-session resumption, and no structured dispute/escalation protocol. Reviews are lost when sessions end. There is no formal approval gate between review and verification/shipping.
- **Success criteria:**
  1. A `review-ledger.py` CLI can create, mutate, validate, and render review ledgers.
  2. The event log is append-only and hash-chained; tampering is detected.
  3. Finding state transitions follow the spec's state machine exactly.
  4. Bead status transitions follow the spec's state machine exactly.
  5. Source identity is deterministic and verified at approval and shipping.
  6. Existing skills integrate with the ledger contract.
  7. All unit tests pass, including failure-injection tests for hash chain corruption, invalid transitions, and lease conflicts.
- **Constraints:** No force-push, no external dependencies, Python 3.10+, cross-platform (Linux/macOS).
- **Non-goals:** Reviewer-authored source fixes (`reviewer-fix` workflow), CI/CD pipeline integration, GUI/web dashboard, multi-reviewer consensus.

## Approach Options

### Option 1: Monolithic Python CLI
- Summary: Single `review-ledger.py` script handling all operations.
- Pros: Simple deployment, single file.
- Cons: Hard to test individual components, grows unwieldy.

### Option 2: Python package with modular internals
- Summary: A `review_ledger/` package with separate modules for data model, event engine, state machines, Git adapter, Markdown renderer, and CLI entry point.
- Pros: Testable units, clear boundaries, maintainable.
- Cons: More files.

### Recommended Approach
- Selected option: Option 2 — modular package.
- Reasoning: The spec has clearly separable concerns (event hashing, state validation, Git operations, rendering). Modular structure enables focused TDD per track and independent review of each component.

## Scope

### In scope
- Review ledger data model (JSON schema, event types, projections)
- Event engine (append, hash chain, replay, validation)
- Finding state machine (all transitions from spec §5)
- Bead status state machine (all transitions from spec §4)
- Source identity computation (tree hash from spec §7.4)
- Lease protocol (acquire, renew, release, break)
- Cross-system transition protocol (Beads ↔ ledger)
- Git adapter (checkpoint, push, fetch, scope validation)
- Generated Markdown renderer
- CLI entry point (`review-ledger.py`)
- Skill updates (requesting-code-review, receiving-code-review, bead-worker, verification-before-completion, ship, bead-orchestrator, progress)
- Unit tests, integration tests, failure-injection tests

### Out of scope
- Reviewer-authored source fixes
- CI/CD integration
- Web UI / dashboard
- Multi-reviewer consensus protocol
- Monorepo/submodule support (documented in spec but deferred to a follow-up plan)

---

## Tasks

### Track 1: Core Data Model and Event Engine
- **Dependencies**: none
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/__init__.py`
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/schema.py`
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/events.py`
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/jcs.py`
  - Create: `tests/review_ledger/test_schema.py`
  - Create: `tests/review_ledger/test_events.py`
  - Create: `tests/review_ledger/test_jcs.py`
- **Model class**: `high_reasoning`
- **Acceptance criteria**:
  - JSON schema constants define all event types from spec §9.5.
  - `LedgerEvent` dataclass with `event_id`, `action`, `timestamp`, `actor`, `payload`, `previous_event_hash`, `event_hash`.
  - JCS canonicalization produces deterministic output matching RFC 8785.
  - Event hash computation: `SHA256(JCS(event excluding event_hash))`.
  - `EventLog` class supports: append, replay, hash chain verification, duplicate-key rejection.
  - First event uses `previous_event_hash: null`.
  - Replay detects: deletion, modification, reordering, duplicate IDs, decreasing numbers, broken chain.
  - All tests pass.
- **Estimated complexity**: high

### Track 2: Ledger Projections and State Derivation
- **Dependencies**: Track 1
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/projections.py`
  - Create: `tests/review_ledger/test_projections.py`
- **Acceptance criteria**:
  - `ReviewProjection` derived from event replay: current review state, finding states, active approval, next finding number, active lease.
  - Projection comparison with stored top-level values; mismatch raises `WorkflowIntegrityError`.
  - `FindingProjection` tracks: id, severity, status, clarification_count, deferral info, linked bead.
  - Derived projections are never authoritative — always reproducible from events.
  - All tests pass.
- **Estimated complexity**: high

### Track 3: Finding State Machine
- **Dependencies**: Track 1, Track 2
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/finding_fsm.py`
  - Create: `tests/review_ledger/test_finding_fsm.py`
- **Model class**: `high_reasoning`
- **Acceptance criteria**:
  - All base transitions from spec §5.1 are implemented and validated.
  - Severity-aware deferral rules from spec §5.2: Critical cannot defer, Important requires human authorization, Minor/Suggestion can defer directly.
  - At most one clarification request per finding; `clarification-provided → clarification-requested` is rejected.
  - Terminal statuses: `verified`, `withdrawn`, `accepted-as-is`, `deferred-verified`, `human-waived`.
  - Invalid transitions raise `InvalidTransitionError` with actor, current status, and attempted status.
  - All tests pass including negative cases for every forbidden transition.
- **Estimated complexity**: high

### Track 4: Bead Status State Machine
- **Dependencies**: Track 1
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/bead_fsm.py`
  - Create: `tests/review_ledger/test_bead_fsm.py`
- **Acceptance criteria**:
  - All transitions from spec §4 state table are implemented.
  - Actor validation: each transition is allowed only by the specified actor role.
  - Source-changing transitions from `verification-in-progress` or `shipping-failed` invalidate active approval.
  - `review-approved` requires all findings terminal.
  - Invalid transitions raise `InvalidTransitionError`.
  - All tests pass including negative cases.
- **Estimated complexity**: medium

### Track 5: Source Identity and Scope
- **Dependencies**: Track 1
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/source_identity.py`
  - Create: `tests/review_ledger/test_source_identity.py`
- **Acceptance criteria**:
  - `compute_source_tree_hash()` implements spec §7.4: `SHA256(sorted(repo_id + NUL + path + NUL + mode + NUL + type + NUL + sha))`.
  - Includes repository identity, normalized relative path, Git file mode, object type, object SHA.
  - Distinguishes: regular files, executable files, symlinks, path renames, deletion, mode changes.
  - Source scope manifest: included/excluded/generated paths from spec §7.3.
  - `compute_source_scope_hash()` for scope identity.
  - Untracked files outside `allowed_generated_paths` fail the checkpoint.
  - All tests pass using a test Git repository fixture.
- **Estimated complexity**: medium

### Track 6: Lease Protocol
- **Dependencies**: Track 1, Track 2
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/lease.py`
  - Create: `tests/review_ledger/test_lease.py`
- **Acceptance criteria**:
  - Lease acquisition: validates no unexpired lease, appends `lease-acquired`, increments revision.
  - Subsequent writes: verify lease ID, expiry, and revision match.
  - Lease release: appends `lease-released`, sets `active_lease` to null.
  - Expired lease breaking: validates expiry + grace, appends `lease-broken`, records replacement actor.
  - Concurrent mutation detection via non-fast-forward push rejection.
  - All tests pass including expiry and conflict scenarios.
- **Estimated complexity**: medium

### Track 7: Git Adapter and Checkpoint Operations
- **Dependencies**: Track 5, Track 6
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/git_adapter.py`
  - Create: `tests/review_ledger/test_git_adapter.py`
- **Acceptance criteria**:
  - `create_source_checkpoint()`: validates scope, partitions changes, fails on unrelated changes, stages only validated paths, commits and pushes.
  - `fetch_review_ref()`: fetches remote review branch, returns SHA.
  - `push_review_ref()`: normal fast-forward push, never force.
  - Working-tree validation: `git status --porcelain`, partition by scope, reject out-of-scope changes.
  - Review branch naming: `bead/<bead-id>`.
  - Repository manifest creation from spec §7.1.
  - All tests pass using temporary Git repositories.
- **Estimated complexity**: medium

### Track 8: Cross-System Transition Protocol
- **Dependencies**: Track 2, Track 4
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/transitions.py`
  - Create: `tests/review_ledger/test_transitions.py`
- **Acceptance criteria**:
  - Transition ID generation (e.g. `CRT-NNNNNN`).
  - Write order from spec §11.1: validate Bead state → validate ledger → confirm match → append `transition-requested` → commit/push → update Beads → append `transition-completed`.
  - Recovery rules from spec §11.2: ledger-ahead replays Bead, Beads-ahead fails closed, unrecognized mismatch raises `WorkflowIntegrityError`.
  - Recovery commands: `recover-transition`, `record-human-decision`, `waive-finding`, `break-expired-lease`.
  - All tests pass.
- **Estimated complexity**: high

### Track 9: CLI Entry Point and Markdown Renderer
- **Dependencies**: Track 1–8
- **Files**:
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/renderer.py`
  - Create: `plugins/gin-workflow/src/scripts/review_ledger/cli.py`
  - Create: `plugins/gin-workflow/src/scripts/review-ledger.py`
  - Create: `tests/review_ledger/test_renderer.py`
  - Create: `tests/review_ledger/test_cli.py`
- **Acceptance criteria**:
  - CLI subcommands: `init`, `checkpoint`, `start-review`, `add-finding`, `fix-finding`, `dispute-finding`, `request-clarification`, `provide-clarification`, `propose-deferral`, `approve-deferral`, `verify-finding`, `withdraw-finding`, `accept-as-is`, `approve`, `reject`, `record-human-decision`, `waive-finding`, `render`, `validate`, `recover-transition`, `break-lease`, `status`.
  - `render` generates deterministic `review.md` from `review.json`.
  - `render --check` fails when committed Markdown doesn't match regenerated output.
  - Rendered Markdown includes: metadata, state, repositories, findings table, finding history, responses, resolutions, decisions, waivers, deferrals, rounds, approval, verification, event summary.
  - `validate` replays events and checks projections.
  - All tests pass.
- **Estimated complexity**: high

### Track 10: Skill Integration and Migration
- **Dependencies**: Track 9
- **Files**:
  - Modify: `plugins/gin-workflow/src/skills/requesting-code-review/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/receiving-code-review/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/bead-worker/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/verification-before-completion/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/ship/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/bead-orchestrator/SKILL.md`
  - Modify: `plugins/gin-workflow/src/skills/progress/SKILL.md`
  - Modify: `plugins/gin-workflow/src/agents/code-reviewer.md`
  - Create: `plugins/gin-workflow/src/skills/cross-agent-code-review/SKILL.md`
  - Create: `plugins/gin-workflow/src/commands/review.md`
  - Modify: `plugins/gin-workflow/src/references/orchestration-state-model.md`
  - Modify: `docs/agent-task-lifecycle.md`
  - Create: `tests/review_ledger/test_integration.py`
- **Acceptance criteria**:
  - `requesting-code-review` creates source checkpoint via CLI, initializes ledger, transitions Bead to `review-requested`.
  - `cross-agent-code-review` (new skill): reviewer entry point, validates manifest, acquires lease, reviews, appends findings, renders Markdown, transitions to `changes-requested`/`blocked-human`/`review-approved`.
  - `receiving-code-review` reads unresolved findings from ledger, records worker actions, creates next checkpoint, requests re-review.
  - `bead-worker` prevents closure of review-required beads, routes `changes-requested` through `receiving-code-review`, halts on `blocked-human` and integrity errors.
  - `bead-orchestrator` dispatches reviewer via `/gin-workflow:review <bead-id>`, invokes the same decoupled commands used manually.
  - `verification-before-completion` validates active approval event, approved source identities, terminal findings, Markdown drift, runs final gates.
  - `ship` revalidates approval and verification before integration, performs post-merge source identity checks.
  - `progress` reads finding projections from validated ledger, reports unresolved counts and human questions.
  - `code-reviewer` agent updated to write findings through CLI rather than freeform output.
  - `/review` command entry point created.
  - `orchestration-state-model.md` updated with review ledger as third source of truth.
  - `agent-task-lifecycle.md` updated with review phase between Implementation and Verification.
  - Integration test: full round-trip from checkpoint → review → findings → fix → re-review → approve → verify → ship.
- **Estimated complexity**: high

---

## Integration

- **Branch**: `feature/cross-agent-code-review`
- **Merge strategy**: sequential (tracks are dependency-ordered)

## Validation

- [ ] All unit tests pass: `python -m pytest tests/review_ledger/ -v`
- [ ] Hash chain corruption detected in failure-injection tests
- [ ] Invalid state transitions rejected for both finding and Bead FSMs
- [ ] Lease conflict scenarios handled correctly
- [ ] Source tree hash deterministic across repeated computations
- [ ] `render --check` detects Markdown drift
- [ ] `validate` detects projection/event mismatches
- [ ] Integration test completes a full review lifecycle
- [ ] Existing `tests/install_smoke_test.sh` still passes
- [ ] Skills render correctly on both Antigravity and Claude Code

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
| --- | --- | --- | --- |
| JCS implementation complexity | Medium | High | Use minimal vendored implementation; test against RFC 8785 examples |
| Git operations in test fixtures are slow | Medium | Low | Use `git init --bare` for lightweight test repos; parallelize where possible |
| Bead CLI (`bd`) interface changes | Low | Medium | Wrap `bd` calls behind an adapter with pinned expected output formats |
| Large plan scope | High | Medium | Tracks are independent; can ship Tracks 1–9 (library) before Track 10 (integration) |
| Monorepo/submodule support deferred | Low | Low | Spec §18 is explicitly out of scope; follow-up plan will cover it |

## Notes

- Model guidance is planning metadata, not Beads state.
- If omitted, agents should assume `standard_impl`.
- Use provider-neutral model classes only; do not name vendor-specific models in the plan schema.
- Monorepo and submodule support (spec §18) is deferred to a separate follow-up plan to keep this plan focused on the core review workflow.
