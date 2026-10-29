# Worker Lifecycle

## Launching a worker

Obtain the route from `gin-workflow routes dispatch --workflow-id <w> --task-id <id> --json`. When `provider` is another harness, run the routed executable in the track worktree with the argv from gin-orchestrator's `scripts/gin_orchestrator/<provider>_worker.py`. Verify the diff and tests. When it exits, run `gin-workflow notify --event worker_finished "<track>: <provider>"` (`worker_failed` on failure).

## Events

Record lifecycle events in this order when the corresponding transition occurs:

1. `worker.requested`
2. `worker.assigned`
3. `worker.started`
4. `worker.context_loaded`
5. `worker.progress_updated`
6. exactly one terminal event: `worker.completed`, `worker.failed`, or `worker.cancelled`

Emit `worker.unavailable` between requested and fallback assignment when the selected native adapter is absent. Missing required context emits requested then failed with `context_unavailable`, without invoking a worker.

Before assignment, skip a candidate whose circuit is open or adapter unhealthy; a capacity wait past the queue deadline moves to the next candidate and is not a circuit failure.

The assigned and terminal runtime events include the actual provider, concrete model alias, and fallback flag. These values stay in runtime evidence and never mutate the portable plan or Beads metadata. If no candidate can run, emit a terminal failure with `worker_routes_unavailable`; do not close the durable task.

Retries use a new attempt identity only for unfinished work. A completed worker result is terminal and is never rerun.
