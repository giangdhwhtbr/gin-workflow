# Worker Lifecycle

The dispatcher exposes `dispatch(request)`, `cancel(worker_id)`, `status(worker_id)`, and `collect_result(worker_id)` for every worker provider.

## Events

Record lifecycle events in this order when the corresponding transition occurs:

1. `worker.requested`
2. `worker.assigned`
3. `worker.started`
4. `worker.context_loaded`
5. `worker.progress_updated`
6. exactly one terminal event: `worker.completed`, `worker.failed`, or `worker.cancelled`

Emit `worker.unavailable` between requested and fallback assignment when the selected native adapter is absent. Missing required context emits requested then failed with `context_unavailable`, without invoking a worker.

Event identity includes the workflow, task, retry identity, and transition. Replayed progress, cancellation, and completion operations must not append duplicate records or replace an existing terminal completion. Event persistence and task-tracking updates must remain concurrency safe.

Retries use a new attempt identity only for unfinished work. A completed worker result is terminal and is never rerun.
