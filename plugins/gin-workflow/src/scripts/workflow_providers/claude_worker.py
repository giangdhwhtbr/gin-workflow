"""Claude native-harness worker bridge (no cloud SDK dependency)."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .worker_dispatch import SynchronousWorkerAdapter, WorkerRequest, WorkerResult


def _payload(request: WorkerRequest) -> Mapping[str, Any]:
    return {**request.to_payload(), "delegate_to": "subagent-driven-development"}


class ClaudeWorkerAdapter(SynchronousWorkerAdapter):
    provider_name = "claude"

    def __init__(
        self,
        native_dispatch: Callable[[Mapping[str, Any]], Mapping[str, Any] | WorkerResult] | None = None,
    ) -> None:
        super().__init__(native_dispatch, available=native_dispatch is not None, payload_factory=_payload)
