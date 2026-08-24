# Context and Evidence Policy

This is the canonical policy for worker context, normalized outcomes, review context, knowledge proposals, evidence, and secret references. It does not define implementation, TDD, debugging, planning, or review methodology; worker dispatch delegates those methods to the applicable skills.

## Worker context, result, and events

A worker receives only its durable task identity, dependency state, approved file scope, validation intent, objective, constraints, generated context manifest, isolation policy, expected output, workflow and retry identities, provider role, and logical reasoning tier. The portable payload never contains the selected provider or concrete model, parent transcript, secrets, or private reasoning. The native adapter adds provider/model aliases only at the local process boundary.

Accepted worker results contain `status`, `task_id`, `summary`, `changed_files`, `commits`, `tests`, `evidence`, and `blockers`; optional `knowledge_candidates` normalizes to an empty list. Invalid or mismatched results fail as `invalid_result_contract`; missing required context fails as `context_unavailable` before dispatch.

Events are idempotent and ordered as applicable: `worker.requested`, zero or more `worker.unavailable` route decisions, `worker.assigned`, `worker.started`, `worker.context_loaded`, `worker.progress_updated`, then one of `worker.completed`, `worker.failed`, or `worker.cancelled`. Runtime route evidence may contain the actual provider/model alias, fallback flag, classified reason, and circuit transition identity, but never a credential, full environment, command line, or private reasoning. Completed results are preserved across timeout, retry, and partial failure.

## Review, knowledge, and evidence

Every review starts with a fresh bounded context containing only approved scope, diff, acceptance criteria, tests, and evidence. It excludes private reasoning, self-assessment, persuasive summaries, unrelated tasks, and excess history. Structured findings include severity, location, expected behavior, and evidence. Revisions retain runtime affinity to the original route and are re-reviewed until terminal or the maximum cycle limit requires human decision. Workers submit knowledge candidates for provider policy decisions; they do not permanently write knowledge.

The evidence capability maintains the configured evidence index, linking tests, review outcomes, repository records, and worker results needed for acceptance verification. Runtime evidence supports audit and verification but never replaces Beads task state or plan-owned scope.

## Secrets

Configuration and manifests use secret references such as `secret_ref:NAME` or `${secret_ref:NAME}` only. Secret values are never resolved into effective configuration, manifests, events, worker results, evidence indexes, bundles, or logs.

## Acceptance identity and authoritative evidence

The acceptance identity is the join key for a workflow attempt:
`workflow_id`, `attempt_id`, `task_id`, and sorted repository snapshots. A snapshot
contains `repository_id`, non-empty `source_scope_hash`, `source_tree_hash`,
`checkpoint_sha`, and `checkpoint_ref`. Worker requests and results must carry
the same identity; a result from another task, attempt, repository, scope, or
checkpoint cannot satisfy acceptance.

The evidence authority resolves four independent sources: completed schema-2.3
worker tests, Git checkpoint records, terminal approved review plus passed
verification, and the configured evidence index. It checks source references and
identity coherence before recording or evaluating completeness. The filesystem
index is atomic and idempotent, but it is not allowed to promote an unverified
record. Empty hashes, missing references, stale approvals, and cross-attempt
records are invalid.

Review evidence is not a worker self-assertion: it must identify a terminal ledger
approval and its verification event. Runtime evidence supports audit and
verification; Beads still owns task status and the approved plan still owns scope.
