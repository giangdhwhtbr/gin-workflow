# Worker Result Contract

A worker result is accepted only when it contains every required field:

- `status`: `completed`, `failed`, or `cancelled`; the execute loop treats `completed` as `done` and `cancelled` as `blocked`
- `task_id`: exactly the dispatched task identity
- `summary`: string
- `changed_files`: list of strings
- `commits`: list of strings
- `tests`: list of structured objects
- `evidence`: list of structured objects
- `blockers`: list of strings

`knowledge_candidates` is an optional list of structured objects and normalizes to an empty list when omitted.

Missing fields, invalid field types, unsupported status, or a mismatched task identity fail with `invalid_result_contract`.
