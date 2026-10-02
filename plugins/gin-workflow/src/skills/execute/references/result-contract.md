# Worker Result Contract

A worker result is accepted only when it contains every required field:

- `status`: `completed`, `failed`, or `cancelled`
- `task_id`: exactly the dispatched task identity
- `summary`: string
- `changed_files`: list of strings
- `commits`: list of strings
- `tests`: list of structured objects
- `evidence`: list of structured objects
- `blockers`: list of strings

`knowledge_candidates` is an optional list of structured objects and normalizes to an empty list when omitted.

Missing fields, invalid field types, unsupported status, or a mismatched task identity fail with `invalid_result_contract`. Unavailable required manifest entries fail with `context_unavailable` before a worker call. Provider exceptions are normalized as worker failures and do not erase results already completed by other workers.

Collection is idempotent: repeated collection returns the same normalized result and does not emit another terminal event. Retry may rerun only failed or unfinished work, using a distinct attempt identity while retaining completed results.
