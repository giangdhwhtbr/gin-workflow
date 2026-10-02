# Shape: Backend

Apply on top of the `execute` or `quick` rules when the change touches server, API, or data code.

- **Contracts:** explicit types or schemas at every boundary (request, response, message, persisted record); change a public contract only when the plan says so.
- **Validation:** validate and normalize input at the edge; trust nothing that crosses a boundary.
- **Errors:** one consistent error shape; map internal failures to safe messages and never leak stack traces, queries, or secrets.
- **Migrations:** reversible, and separate from the code change that depends on them.
- **Data access:** go through the existing data layer; avoid N+1 queries and unbounded reads.
- **Retries:** make handlers that can be retried idempotent.
- **Tests:** cover the contract, the validation failures, and the error paths, not only the happy path.
