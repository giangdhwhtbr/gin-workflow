# Cross-Agent Code Review Workflow Design

## 1. Purpose

This document defines an auditable cross-agent code review workflow for the `gin-workflow` plugin.

The workflow allows an implementation agent and an independent reviewing agent—potentially running in different sessions and using different models—to exchange findings, fixes, disputes, clarifications, and human decisions through persistent repository artifacts.

The design optimizes for:

* independent review;
* reproducible Git-based inputs;
* cross-session resumption;
* durable audit history;
* controlled technical debate;
* deterministic human escalation;
* compatibility with normal repositories, monorepos, and Git submodules;
* strict separation between implementation, review, orchestration, verification, and human authority.

The design phase ends with this specification. A separate implementation plan must define exact files, APIs, schemas, tests, and migration steps.

---

## 2. Architectural Principles

### 2.1 Decoupled review invocation

The canonical review entry point is:

```text
/gin-workflow:review <bead-id>
```

The reviewer runs in a fresh session and reconstructs its context from persistent artifacts.

The reviewer must not depend on:

* the implementation agent’s conversation history;
* hidden reasoning;
* parent-agent memory;
* transient subagent messages;
* local-only files that are unavailable from a clean clone.

An orchestrator may automatically invoke the command, but automatic invocation must behave identically to a manually initiated fresh review session.

### 2.2 Persistent sources of truth

The workflow has three distinct sources of truth:

| System        | Authoritative responsibility                                                          |
| ------------- | ------------------------------------------------------------------------------------- |
| Beads         | Runtime task state, blockers, dependencies, and current workflow phase                |
| Review ledger | Findings, decisions, review events, audit history, and approval evidence              |
| Git           | Source code, revisions, branches, repository identity, and committed review artifacts |

No system replaces another.

For example:

* `/progress` reads runtime state from Beads;
* `/progress` enriches that state with findings from the ledger;
* source identity and reviewed content are validated from Git.

### 2.3 Event history is authoritative

The append-only event log is the authoritative representation of review history.

Top-level values such as:

* current review state;
* current finding status;
* current approval;
* next finding number;

are derived projections.

A command must never authorize a transition solely from mutable projection fields. It must validate the event chain and replay the events first.

### 2.4 Reviewer independence

The reviewer may:

* read the complete repository;
* inspect source code surrounding the changed lines;
* search callers, consumers, tests, configuration, and documentation;
* inspect Git history and diffs;
* run approved validation commands in an isolated environment;
* write reviewer-owned ledger events.

The reviewer may not modify implementation source code.

An explicit future `reviewer-fix` workflow may allow reviewer-authored fixes, but it is outside this design and must not be enabled implicitly.

---

## 3. Roles and Permissions

### 3.1 Worker agent

The worker may:

* implement source changes;
* create review checkpoints;
* write worker responses;
* mark findings as fixed, disputed, clarification-provided, or deferral-proposed;
* create or link follow-up Beads;
* request re-review.

The worker may not:

* write reviewer resolutions;
* create review approval events;
* mark its own fix as verified;
* approve a deferral;
* waive a finding;
* rewrite historical review events.

### 3.2 Reviewer agent

The reviewer may:

* inspect the complete review context;
* create findings;
* verify fixes;
* accept or reject disputes;
* request one clarification per disputed finding;
* approve or reject proposed deferrals;
* create review approval or changes-requested outcomes.

The reviewer may not:

* modify implementation source files;
* rewrite worker response history;
* create human decisions;
* waive findings;
* silently alter prior events.

### 3.3 Human

The human may:

* record product or architectural decisions;
* explicitly waive findings;
* authorize deferral of Important findings;
* accept risk for a Critical finding;
* recover an incomplete cross-system transition;
* break an expired lease;
* resolve exceptional workflow integrity failures.

Human actions must be performed through explicit audited commands.

The human must not directly rewrite or delete historical events.

### 3.4 Orchestrator

The orchestrator may:

* invoke worker, reviewer, verification, and shipping commands;
* execute validated state transitions;
* resume idempotent operations;
* replay a known pending transition.

The orchestrator may not:

* choose technical outcomes;
* waive findings;
* invent human decisions;
* rewrite findings;
* bypass verification or approval gates.

### 3.5 Verifier

The verifier may:

* validate the active approval;
* run final quality gates;
* record verification evidence;
* transition the Bead to `ready-to-ship`;
* invalidate approval when verification reveals a source defect.

The verifier may not modify implementation source code as part of verification.

---

## 4. Bead Runtime State Contract

The Bead status must transition only through the following state machine.

| Current state                | Actor                  | Allowed next state           | Condition                                                               |
| ---------------------------- | ---------------------- | ---------------------------- | ----------------------------------------------------------------------- |
| `implementation-in-progress` | Worker                 | `implementation-complete`    | Worker finishes the current implementation pass                         |
| `implementation-complete`    | Worker                 | `review-requested`           | Immutable checkpoint and review manifest are published                  |
| `review-requested`           | Reviewer               | `review-in-progress`         | Reviewer acquires the review lease                                      |
| `review-in-progress`         | Reviewer               | `changes-requested`          | At least one unresolved finding requires worker action                  |
| `review-in-progress`         | Reviewer               | `blocked-human`              | At least one finding requires a human decision                          |
| `review-in-progress`         | Reviewer               | `review-approved`            | All findings have valid terminal dispositions                           |
| `changes-requested`          | Worker                 | `implementation-in-progress` | Worker begins applying fixes or decisions                               |
| `blocked-human`              | Human decision command | `changes-requested`          | All blocking human questions have recorded decisions                    |
| `review-approved`            | Verifier               | `verification-in-progress`   | Active approval and source identities are valid                         |
| `verification-in-progress`   | Verifier               | `ready-to-ship`              | All final checks pass                                                   |
| `verification-in-progress`   | Verifier               | `implementation-in-progress` | Verification discovers a source defect or required source change        |
| `ready-to-ship`              | Shipping command       | `closed`                     | Integration succeeds and post-merge identity checks pass                |
| `ready-to-ship`              | Shipping command       | `shipping-failed`            | Merge, publication, or deployment fails                                 |
| `shipping-failed`            | Shipping command       | `ready-to-ship`              | Retryable infrastructure failure; approved source is unchanged          |
| `shipping-failed`            | Worker                 | `implementation-in-progress` | Source or integration code must change                                  |
| `shipping-failed`            | Human recovery command | `closed`                     | Integration succeeded but state recording failed, with audited evidence |

A source-changing transition from either `verification-in-progress` or `shipping-failed` invalidates the active approval and requires a new review checkpoint.

---

## 5. Finding State Contract

### 5.1 Base finding transitions

| Current status                | Actor    | Allowed next status           |
| ----------------------------- | -------- | ----------------------------- |
| `open`                        | Worker   | `fixed-awaiting-verification` |
| `open`                        | Worker   | `disputed`                    |
| `open`                        | Worker   | `deferral-proposed`           |
| `fixed-awaiting-verification` | Reviewer | `verified`                    |
| `fixed-awaiting-verification` | Reviewer | `open`                        |
| `disputed`                    | Reviewer | `withdrawn`                   |
| `disputed`                    | Reviewer | `accepted-as-is`              |
| `disputed`                    | Reviewer | `clarification-requested`     |
| `disputed`                    | Reviewer | `human-decision-required`     |
| `clarification-requested`     | Worker   | `clarification-provided`      |
| `clarification-provided`      | Reviewer | `withdrawn`                   |
| `clarification-provided`      | Reviewer | `accepted-as-is`              |
| `clarification-provided`      | Reviewer | `open`                        |
| `clarification-provided`      | Reviewer | `human-decision-required`     |
| `human-decision-required`     | Human    | `human-decision-recorded`     |
| `human-decision-required`     | Human    | `human-waived`                |
| `human-decision-recorded`     | Worker   | `fixed-awaiting-verification` |

A finding may receive at most one clarification request.

The transition validator must reject:

```text
clarification-provided -> clarification-requested
```

The finding projection must retain:

```json
{
  "clarification_count": 1
}
```

### 5.2 Severity-aware deferral transitions

#### Critical

Critical findings:

* block approval;
* cannot be deferred;
* may only be waived by an explicit human risk-acceptance event.

The validator must reject:

```text
Critical open -> deferral-proposed
```

#### Important

Important findings:

* block approval;
* may be deferred only after explicit human authorization.

The valid flow is:

```text
deferral-proposed
    -> human-decision-required
    -> human-decision-recorded
    -> deferred-awaiting-verification
    -> deferred-verified
```

The human decision must explicitly authorize deferral.

#### Minor and Suggestion

Minor and Suggestion findings may use:

```text
deferral-proposed
    -> deferred-verified
```

Only the reviewer may mark a deferral as verified.

### 5.3 Terminal finding statuses

A finding is terminal only when it is one of:

```text
verified
withdrawn
accepted-as-is
deferred-verified
human-waived
```

`review-approved` requires every finding to have a valid terminal status.

---

## 6. Dispute and Escalation Policy

The workflow permits one evidence-based dispute and one reviewer judgment.

The sequence is:

1. The reviewer creates a finding.
2. The worker verifies it against the codebase.
3. The worker either fixes, defers, or disputes it.
4. If disputed, the worker provides technical evidence.
5. The reviewer evaluates the evidence.
6. The reviewer either:

   * withdraws the finding;
   * accepts the implementation as-is;
   * requests one clarification;
   * escalates to a human decision.
7. After clarification, the reviewer must resolve, reopen, or escalate.

A substantive disagreement after the reviewer considers the worker’s evidence must become:

```text
human-decision-required
```

The agents must not enter repeated debate rounds.

---

## 7. Repository and Revision Identity Model

### 7.1 Repository manifest

The ledger records every repository participating in the review.

```json
{
  "repositories": [
    {
      "repository_id": "backend",
      "role": "primary",
      "path": ".",
      "remote": "origin",
      "target_ref": "refs/heads/main",
      "review_ref": "refs/heads/bead/backend-auth-123",
      "review_base_sha": "a89f921...",
      "previous_reviewed_source_sha": "b92d83f...",
      "reviewed_source_sha": "c72b11d...",
      "reviewed_source_tree_hash": "84f221..."
    }
  ]
}
```

The manifest must not assume:

* the remote is named `origin`;
* the target branch is named `main`;
* one repository is sufficient;
* a single directory represents the complete source scope.

### 7.2 Immutable review range

Each review round is bound to:

```text
review_base_sha..reviewed_source_sha
```

The reviewer must inspect the complete implementation range using the recorded immutable SHAs.

For re-review, the reviewer also inspects:

```text
previous_reviewed_source_sha..reviewed_source_sha
```

This separates:

* the complete implementation;
* the changes made in response to the previous review.

### 7.3 Source-scope manifest

The source scope is initialized from the Bead requirements or implementation plan, then normalized and recorded in the ledger.

After initialization, the ledger scope becomes authoritative.

```json
{
  "source_scope": {
    "included_paths": [
      "services/backend/src/",
      "services/backend/test/",
      "packages/contracts/"
    ],
    "excluded_artifact_paths": [
      ".planning/backend-auth-123/review.json",
      ".planning/backend-auth-123/review.md"
    ],
    "allowed_generated_paths": [
      "coverage/",
      ".cache/"
    ]
  }
}
```

A `review-scope-established` event binds the scope to the review.

Changing the source scope requires:

1. a `review-scope-change-requested` event;
2. invalidation of the current approval;
3. a new source checkpoint;
4. complete re-review of the new scope.

### 7.4 Deterministic source identity

The source hash is calculated from tracked Git objects within the normalized scope.

```text
reviewed_source_tree_hash = SHA256(
  sorted(
    repository_id
    + NUL
    + normalized_relative_path
    + NUL
    + git_mode
    + NUL
    + object_type
    + NUL
    + object_sha
  )
)
```

The hash includes:

* repository identity;
* normalized relative path;
* Git file mode;
* object type;
* Git object SHA.

This distinguishes:

* regular files;
* executable files;
* symbolic links;
* submodule gitlinks;
* path renames;
* file deletion;
* identical content with different file modes.

Untracked files have no Git object SHA and must fail the checkpoint or verification cleanliness gate unless they match an explicitly allowed generated path in a disposable validation environment.

Path normalization must be repository-relative and case-preserving. The workflow must not silently normalize case based on the host filesystem.

### 7.5 No self-referential Git fields

The ledger must not contain a required field representing the SHA of the commit that contains that field.

In particular, the authoritative ledger must not contain:

```text
review_branch_head_sha
approval_ledger_commit
```

Git is authoritative for the current branch head.

A command may retain a resulting commit SHA in process memory or record it in a later event, but a commit must not be required to contain its own SHA.

---

## 8. Review Approval Contract

### 8.1 Approval event

Approval is represented by an immutable event that contains the complete approved source snapshot.

```json
{
  "event_id": "CRE-000042",
  "action": "review-approved",
  "timestamp": "2026-07-18T17:30:00Z",
  "actor": {
    "role": "reviewer",
    "actor_id": "reviewer-session-7f923"
  },
  "payload": {
    "review_round": 3,
    "approved_repositories": [
      {
        "repository_id": "backend",
        "review_base_sha": "a89f921...",
        "reviewed_source_sha": "c72b11d...",
        "reviewed_source_tree_hash": "84f221..."
      }
    ],
    "source_scope_hash": "19cc74...",
    "terminal_findings": [
      "CR-001",
      "CR-002",
      "CR-003"
    ]
  }
}
```

Final verification reads approved source identities from this event.

It must not rely only on mutable top-level projection fields.

### 8.2 Approval invalidation

Any source-changing checkpoint after approval appends:

```json
{
  "action": "review-approval-invalidated",
  "payload": {
    "previous_approval_event_id": "CRE-000042",
    "reason": "source-checkpoint-updated",
    "new_reviewed_source_sha": "d83f921..."
  }
}
```

Approval is also invalidated when:

* verification reveals a source defect;
* source scope changes;
* merge conflict resolution changes source;
* shipping requires implementation changes;
* a previously terminal finding is reopened.

Ledger-only and generated-document-only commits do not invalidate approval when the approved source hash remains unchanged.

---

## 9. Review Ledger Contract

### 9.1 Files

Each reviewed Bead uses:

```text
.planning/<bead-id>/
├── review.json
└── review.md
```

`review.json` contains:

* schema version;
* current derived projection;
* repository manifest;
* source-scope manifest;
* active lease projection;
* findings projection;
* append-only events.

`review.md` is generated deterministically from `review.json`.

### 9.2 Event authority

The event log is authoritative.

Top-level projections are caches used for efficient reading and human inspection.

Before any transition, the ledger helper must:

1. parse the JSON with duplicate-key rejection;
2. validate the schema version;
3. verify the event hash chain;
4. replay all events;
5. derive the review state;
6. derive every finding state;
7. derive active approval and invalidation state;
8. derive the next finding number;
9. derive the active lease;
10. compare the replay result with stored projections;
11. abort with `workflow-integrity-error` on any mismatch.

### 9.3 Append-only enforcement

A newly committed ledger version must preserve all previous events.

The validator must reject:

* event deletion;
* event modification;
* event reordering;
* duplicate event IDs;
* duplicate finding IDs;
* decreasing event numbers;
* a broken hash chain;
* a projection that cannot be reproduced from events.

### 9.4 Event hash canonicalization

Event hashes use RFC 8785 JSON Canonicalization Scheme.

```text
event_hash = SHA256(
  JCS(event excluding event_hash)
)
```

Rules:

* encoding is UTF-8;
* duplicate JSON keys are rejected;
* `event_hash` is excluded from its own hash input;
* `previous_event_hash` is included;
* timestamps use UTC RFC 3339 format;
* event IDs are unique;
* the first event uses:

```json
{
  "previous_event_hash": null
}
```

### 9.5 Core event types

The event model should support at least:

```text
ledger-created
review-scope-established
review-scope-change-requested
lease-acquired
lease-renewed
lease-released
lease-broken
source-checkpoint-created
review-started
finding-created
finding-fixed
finding-disputed
clarification-requested
clarification-provided
deferral-proposed
deferral-approved
finding-verified
finding-withdrawn
finding-accepted-as-is
human-decision-required
human-decision-recorded
finding-waived
review-approved
review-approval-invalidated
verification-started
verification-passed
verification-failed
transition-requested
transition-completed
shipping-started
shipping-failed
shipping-completed
recovery-performed
```

---

## 10. Concurrency and Lease Protocol

### 10.1 Purpose

The lease prevents two agents from concurrently mutating the same ledger.

Git remote branch updates provide the compare-and-swap boundary.

### 10.2 Lease projection

```json
{
  "active_lease": {
    "lease_id": "4fbb621e-...",
    "actor_role": "reviewer",
    "actor_id": "reviewer-session-7f923",
    "acquired_at": "2026-07-18T16:10:00Z",
    "expires_at": "2026-07-18T16:40:00Z",
    "current_ledger_revision": 5
  }
}
```

The persisted lease does not store the current or resulting Git commit SHA.

### 10.3 Lease acquisition

The canonical lease acquisition algorithm is:

1. Fetch the remote review branch.
2. Record the fetched remote SHA in process memory.
3. Validate that no unexpired lease exists.
4. Append a `lease-acquired` event.
5. Increment `ledger_revision`.
6. Set `active_lease.current_ledger_revision` to the new revision.
7. Commit the ledger and generated Markdown locally.
8. Push using a normal fast-forward push:

```bash
git push <remote> HEAD:<review-ref>
```

A competing update causes a non-fast-forward rejection.

The command must not force-push.

### 10.4 Subsequent ledger writes

Before each write, the active process must:

1. fetch the remote review ref;
2. verify that the remote SHA matches its last successfully pushed local commit;
3. reload and replay the ledger;
4. verify the lease ID;
5. verify the lease has not expired;
6. verify `ledger_revision` matches `active_lease.current_ledger_revision`;
7. append events;
8. increment the revision;
9. update `active_lease.current_ledger_revision`;
10. commit and push normally.

After a successful push, the process updates its local expected Git SHA.

### 10.5 Lease release

The final mutation for an actor:

1. appends a `lease-released` event;
2. sets `active_lease` to `null`;
3. commits and pushes normally.

### 10.6 Expired lease recovery

A lease may be broken only when:

* its expiry time has passed;
* the configured grace period has passed;
* the remote ref has been freshly fetched;
* the replacing actor has confirmed that no newer ledger commit exists.

Breaking the lease:

1. appends a `lease-broken` event;
2. records the expired lease ID and actor;
3. records the replacement actor;
4. records the reason;
5. atomically replaces the lease through a normal fast-forward commit;
6. never force-pushes.

Human intervention is required when the expired session may still be active or when the remote state is ambiguous.

---

## 11. Cross-System Transition Protocol

Beads and Git cannot be updated atomically. Each workflow transition therefore uses a durable transition ID.

```json
{
  "transition_id": "CRT-000024",
  "from": "review-in-progress",
  "to": "changes-requested"
}
```

### 11.1 Write order

1. Validate the expected current Bead state.
2. Validate the replayed ledger state.
3. Confirm both states match.
4. Append a `transition-requested` event.
5. Commit and push the ledger.
6. Update Beads using the same transition ID in metadata.
7. Append `transition-completed` in the next safe ledger mutation.

### 11.2 Recovery rules

#### Ledger ahead, Beads behind

When the ledger contains a valid pending transition and Beads remains at the expected previous state:

* replay the Beads transition;
* preserve the same transition ID;
* append completion evidence later.

#### Beads ahead, ledger missing

When Beads moved forward but the committed ledger has no matching transition event:

* fail closed;
* require audited human recovery.

#### Unrecognized mismatch

When the states differ without a recognized transition ID:

```text
workflow-integrity-error
```

Review, verification, shipping, and closure are blocked.

### 11.3 Recovery commands

Recovery uses explicit commands such as:

```text
recover-transition
record-human-decision
waive-finding
break-expired-lease
```

There is no unrestricted `force` command.

Recovery requires:

* expected Bead state;
* expected ledger revision;
* transition ID;
* requested target state;
* human identity;
* human justification.

---

## 12. Review Checkpoint Strategy

### 12.1 Dedicated branch

Each reviewed Bead uses a dedicated review branch:

```text
bead/<bead-id>
```

The branch and remote are resolved during review initialization and recorded in the repository manifest.

### 12.2 Dirty working-tree policy

The workflow must never automatically:

* stash;
* reset;
* clean;
* discard;
* overwrite;
* move unrelated user work.

Checkpoint creation must:

1. load the authoritative source scope;
2. run `git status --porcelain`;
3. partition changed files by scope;
4. fail when unrelated changes are present;
5. stage only validated paths;
6. fail when prohibited untracked files are present;
7. commit the source checkpoint;
8. push the review branch.

Example failure:

```text
Error: unrelated working-tree changes detected.

Outside review scope:
- services/frontend/index.ts

Allowed source scope:
- services/backend/src/
- services/backend/test/

Review checkpoint was not created.
```

### 12.3 Source checkpoint event

After the source checkpoint is created and pushed, the ledger records:

* repository ID;
* review base SHA;
* previous reviewed source SHA;
* reviewed source SHA;
* source tree hash;
* normalized source-scope hash;
* remote and review ref.

---

## 13. Review Execution

### 13.1 Initial review

The reviewer:

1. validates the repository manifest;
2. fetches all required review refs;
3. validates that recorded commits exist;
4. validates the source-scope hash;
5. acquires the review lease;
6. reads Bead requirements and acceptance criteria;
7. reads the implementation plan;
8. reviews `review_base_sha..reviewed_source_sha`;
9. inspects relevant surrounding code;
10. runs approved isolated validation;
11. appends findings;
12. generates `review.md`;
13. transitions to:

    * `changes-requested`;
    * `blocked-human`;
    * `review-approved`.

### 13.2 Re-review

During re-review, the reviewer inspects both:

```text
review_base_sha..reviewed_source_sha
```

and:

```text
previous_reviewed_source_sha..reviewed_source_sha
```

The reviewer must:

* verify prior worker responses;
* check whether fixes introduced regressions;
* verify follow-up Beads;
* evaluate disputes;
* resolve clarifications;
* identify new findings when necessary.

---

## 14. Receiving Code Review

The worker invokes the receiving workflow after `changes-requested`.

For every non-terminal finding, the worker must choose one valid action:

```text
fix
dispute
request interpretation through existing clarification flow
propose deferral
```

The worker must not ignore findings.

### 14.1 Fix

The worker:

1. verifies the finding;
2. implements one fix at a time;
3. runs targeted tests;
4. records the changed files;
5. records verification evidence;
6. marks the finding `fixed-awaiting-verification`.

### 14.2 Dispute

The worker records:

* technical reasoning;
* source references;
* test evidence;
* compatibility constraints;
* architectural context;
* any relevant human decision.

### 14.3 Deferral

Before creating a new follow-up Bead, the worker searches for an equivalent existing open Bead.

A proposed deferral includes:

```json
{
  "deferral": {
    "reason": "Outside current acceptance criteria",
    "follow_up_bead_id": "backend-104",
    "follow_up_bead_title": "refactor: centralize role mapping",
    "relationship": "discovered-from"
  }
}
```

Only the reviewer may add:

```json
{
  "verified_by": "reviewer-session-7f923",
  "verified_at": "2026-07-18T17:10:00Z"
}
```

---

## 15. Human Decisions and Waivers

### 15.1 Human decision

A human decision event records:

```json
{
  "action": "human-decision-recorded",
  "finding_id": "CR-002",
  "payload": {
    "question": "Should token secret resolution be centralized?",
    "decision": "Centralize token secret resolution.",
    "reason": "Configuration consistency is required across service layers.",
    "recorded_by": "gin",
    "recorded_at": "2026-07-18T17:20:00Z"
  }
}
```

The worker then implements the decision.

The reviewer verifies conformity with the decision but may not reopen the resolved architectural question unless the implementation introduces a new and distinct issue.

### 15.2 Human waiver

A waiver records explicit accepted risk:

```json
{
  "action": "finding-waived",
  "finding_id": "CR-004",
  "payload": {
    "decision": "accept-risk",
    "reason": "Compatibility requirement prevents remediation in this release.",
    "scope": "CR-004",
    "recorded_by": "gin",
    "recorded_at": "2026-07-18T17:25:00Z"
  }
}
```

A waiver is not equivalent to a verified fix.

The generated ledger must clearly distinguish:

```text
verified
human-waived
```

---

## 16. Generated Markdown Contract

`review.md` is derived output.

Rules:

* agents and humans do not edit it directly;
* every ledger command regenerates it;
* rendering is deterministic;
* verification fails when the committed Markdown does not match regenerated output.

The check command is:

```bash
python review-ledger-parser.py render \
  --ledger .planning/<bead-id>/review.json \
  --check
```

The rendered document should include:

* review metadata;
* current Bead and review state;
* repository and revision identities;
* current findings table;
* detailed finding history;
* worker responses;
* reviewer resolutions;
* human decisions;
* waivers;
* deferred follow-up Beads;
* review rounds;
* approval state;
* verification evidence;
* complete chronological event summary.

---

## 17. Reviewer Validation Isolation

Reviewer-run validation must execute in:

* a disposable Git worktree;
* or an isolated container.

Credentials must:

* be read-only where possible;
* target non-production environments;
* prohibit destructive database operations;
* avoid production secrets.

After every command, classify workspace mutations as:

| Mutation class                                      | Result                                   |
| --------------------------------------------------- | ---------------------------------------- |
| Unexpected source mutation                          | Fail the review command                  |
| Known generated output in `allowed_generated_paths` | Record and discard                       |
| Snapshot or expected source update                  | Create a finding requiring worker action |
| Unknown untracked output                            | Fail closed                              |

The disposable environment is discarded after review.

---

## 18. Monorepo and Submodule Model

### 18.1 Submodule-owned Bead

When a Bead is scoped to a submodule:

* the Bead belongs to the submodule project;
* the ledger lives under the submodule root;
* the submodule owns the review branch;
* the submodule source checkpoint is pushed to its remote.

### 18.2 Parent pointer during review

During review rounds:

* the parent repository pointer may remain at the reviewed source checkpoint;
* it does not follow every ledger-only submodule commit;
* resumed sessions fetch and check out the submodule’s recorded `review_ref` directly.

This avoids a parent pointer transaction for every ledger event.

### 18.3 Shipping finalization

At shipping:

1. determine the final approved submodule artifact commit containing the durable ledger;
2. update the parent submodule pointer to that commit;
3. commit the parent pointer update;
4. push the parent branch;
5. verify the pointer;
6. merge or integrate both repositories;
7. perform post-merge source identity checks.

The parent manifest tracks:

```json
{
  "expected_reviewed_source_sha": "submodule-source-checkpoint",
  "expected_final_submodule_artifact_sha": "final-ledger-commit",
  "parent_pointer_status": "pending-finalization"
}
```

### 18.4 Partial failure

If the submodule push succeeds but the parent pointer push fails:

* record `failed-parent-sync`;
* leave the Bead in `shipping-failed`;
* block closure;
* roll forward by retrying the parent pointer operation.

Do not rewrite or remove the already-published submodule history.

---

## 19. Final Verification

Review approval does not replace verification.

The verifier must:

1. replay and validate the ledger;
2. identify the active, non-invalidated approval event;
3. load the approved repository identities from that event;
4. verify each reviewed source SHA exists;
5. verify each reviewed source SHA is an ancestor of the review branch HEAD;
6. recompute each approved source tree hash;
7. recompute the source-scope hash;
8. confirm every finding has a valid terminal disposition;
9. regenerate and validate `review.md`;
10. run repository-specific tests, type checks, linting, builds, migration checks, and manual gates;
11. record exact commands and results;
12. append `verification-passed` or `verification-failed`.

When verification requires a source change:

1. append `review-approval-invalidated`;
2. transition to `implementation-in-progress`;
3. create a new checkpoint after the fix;
4. request re-review.

---

## 20. Shipping and Post-Merge Validation

Before integration, shipping revalidates:

* active approval;
* source-scope hashes;
* verification evidence;
* terminal finding states;
* parent/submodule pointer state;
* ledger and generated Markdown;
* remote review refs.

Shipping may perform:

* merge;
* squash merge;
* submodule pointer finalization;
* publication metadata updates.

Shipping must not resolve source-changing conflicts.

A source-changing conflict returns the Bead to implementation and invalidates approval.

### 20.1 Squash merge

A squash merge changes commit ancestry. Therefore, post-merge validation must use source identity rather than source commit ancestry.

After squash integration, shipping verifies:

1. the integrated source-scope hash equals the approved source-scope hash;
2. the final ledger is present;
3. generated Markdown is present and valid;
4. the final submodule pointer references the intended artifact;
5. no unresolved findings exist;
6. verification evidence refers to the active approval event.

Only then may the Bead transition to `closed`.

---

## 21. Component Responsibility Contracts

### `requesting-code-review`

* validates repository and scope state;
* validates the working tree;
* creates and pushes source checkpoints;
* initializes or updates the review manifest;
* appends source-checkpoint events;
* requests the transition to `review-requested`.

### `cross-agent-code-review`

* provides the reviewer entry point;
* validates the manifest and event history;
* acquires the reviewer lease;
* performs initial review or re-review;
* appends reviewer-owned events;
* renders `review.md`;
* transitions to `changes-requested`, `blocked-human`, or `review-approved`.

### `receiving-code-review`

* provides the worker response entry point;
* validates worker-owned transitions;
* presents unresolved findings;
* records fixes, disputes, clarifications, and deferral proposals;
* creates or links follow-up Beads;
* creates and publishes the next source checkpoint;
* requests re-review.

### `bead-worker`

* prevents closure of review-required Beads;
* routes `changes-requested` through `receiving-code-review`;
* halts on `blocked-human`;
* halts on workflow integrity errors.

### `bead-orchestrator`

* dispatches roles;
* invokes the same decoupled commands used manually;
* resumes idempotent transitions;
* cannot alter technical outcomes;
* cannot record human decisions.

### `verification-before-completion`

* validates the active approval event;
* validates approved source identities;
* rejects unresolved findings;
* checks generated Markdown drift;
* executes final quality gates;
* records verification evidence;
* transitions to `ready-to-ship` or back to implementation.

### `/progress`

* reads runtime status from Beads;
* reads finding projections from the validated ledger;
* reports unresolved finding counts;
* reports human questions;
* reports deferred follow-up Beads;
* reports integrity mismatches without reconciling silently.

### `ship`

* revalidates approval and verification;
* performs integration without source-changing conflict resolution;
* finalizes submodule pointers;
* verifies the ledger survives merge or squash;
* performs post-merge tree identity checks;
* closes the Bead only after integration succeeds.

---

## 22. Required Workflow Invariants

The implementation must enforce the following invariants:

1. No review depends on private session history.
2. Every reviewed source state is identified by immutable Git revisions and deterministic source hashes.
3. The event log is append-only and cryptographically chained.
4. Current projections are reproducible from event replay.
5. Workers cannot verify their own fixes.
6. Reviewers cannot modify implementation source code.
7. Orchestrators cannot make human or technical decisions.
8. One disputed finding receives at most one clarification request.
9. Unresolved worker-reviewer disagreement escalates to a human.
10. Critical findings cannot be deferred.
11. Deferred work is owned by a follow-up Bead.
12. Human actions are explicit audited events.
13. Git pushes never use unrestricted force.
14. Unrelated user changes are never automatically stashed, cleaned, or discarded.
15. Any source change after approval invalidates approval.
16. Ledger-only commits do not invalidate approval when the source identity remains unchanged.
17. Verification and shipping validate the source snapshot embedded in the approval event.
18. A squash merge must preserve approved source identity and the final ledger.
19. A Bead cannot close with unresolved findings, incomplete transitions, or integrity errors.
20. A clean clone with access to the configured Git remotes and Beads data must be able to resume the workflow.

---

## 23. Next Deliverable

The next deliverable must be a separate implementation plan.

It should define:

* exact JSON Schema files;
* exact command names and arguments;
* event and projection data types;
* transition-validation interfaces;
* Git repository adapter interfaces;
* Beads adapter interfaces;
* canonicalization and hashing implementation;
* Markdown renderer behavior;
* lease APIs;
* recovery APIs;
* exact files to create and modify;
* migration strategy for existing workflows;
* unit tests;
* integration tests;
* failure-injection tests;
* monorepo and submodule fixtures;
* test commands and expected outputs;
* incremental implementation commits.

The implementation plan must follow test-driven development and divide the work into independently reviewable tasks.
