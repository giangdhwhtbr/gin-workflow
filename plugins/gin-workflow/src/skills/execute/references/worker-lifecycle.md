# Worker Lifecycle

## Launching a worker

Route with `gin routes dispatch --workflow-id <w> --task-id <id> --json`. Run `gin-orchestrator dispatch --workflow-id <w> --task-id <id> --role <role> --provider <provider> --model <model> [--effort <effort>] --stage execute --agent developer --workspace <worktree> --objective "<objective>" --json`. Verify diff and tests. On exit, `gin notify --event worker_finished "<track>: <provider>"` (`worker_failed` on failure). Fallback: native subagent or in-session run.

## Events

Order: `worker.requested`, `worker.assigned`, `worker.started`, `worker.context_loaded`, `worker.progress_updated`, and exactly one terminal event: `worker.completed`, `worker.failed`, or `worker.cancelled`. Emit `worker.unavailable` between requested and fallback assignment when adapter absent. Missing required context emits requested then failed with `context_unavailable`, without invoking a worker.

Skip candidates when circuit open or adapter unhealthy; capacity wait past queue deadline moves to next candidate without tripping circuit. Runtime events record provider, model, fallback; plan/Beads never mutate. If no candidate runs, fail with `worker_routes_unavailable` and leave task open. Retries use new attempt identity only for unfinished work; completed results never rerun.
