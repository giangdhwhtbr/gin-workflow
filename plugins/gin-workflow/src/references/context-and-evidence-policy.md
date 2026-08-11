# Context and Evidence Policy

This is the canonical policy for worker context, normalized outcomes, review context, knowledge proposals, evidence, and secret references. It does not define implementation, TDD, debugging, planning, or review methodology; worker dispatch delegates those methods to the applicable skills.

## Worker context, result, and events

A worker receives only its durable task identity, dependency state, approved file scope, validation intent, objective, constraints, generated context manifest, isolation policy, expected output, workflow and retry identities, and logical model tier. It never receives the parent transcript, provider model names, secrets, or private reasoning.

Accepted worker results contain `status`, `task_id`, `summary`, `changed_files`, `commits`, `tests`, `evidence`, and `blockers`; optional `knowledge_candidates` normalizes to an empty list. Invalid or mismatched results fail as `invalid_result_contract`; missing required context fails as `context_unavailable` before dispatch.

Events are idempotent and ordered as applicable: `worker.requested`, `worker.assigned`, `worker.started`, `worker.context_loaded`, `worker.progress_updated`, then one of `worker.completed`, `worker.failed`, or `worker.cancelled`. An unavailable native provider records `worker.unavailable` before configured sequential fallback. Completed results are preserved across timeout, retry, and partial failure.

## Review, knowledge, and evidence

Every review starts with a fresh bounded context derived from the approved scope and evidence. It excludes private reasoning, self-assessment, persuasive summaries, unrelated tasks, and excess history. Workers submit knowledge candidates for provider policy decisions; they do not permanently write knowledge.

The evidence capability maintains the configured evidence index, linking tests, review outcomes, repository records, and worker results needed for acceptance verification. Runtime evidence supports audit and verification but never replaces Beads task state or plan-owned scope.

## Secrets

Configuration and manifests use secret references such as `secret_ref:NAME` or `${secret_ref:NAME}` only. Secret values are never resolved into effective configuration, manifests, events, worker results, evidence indexes, bundles, or logs.
