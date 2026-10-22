"""Configured in-process fallback when native worker dispatch is unavailable."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .worker_dispatch import SynchronousWorkerAdapter, WorkerResult


class SequentialWorkerAdapter(SynchronousWorkerAdapter):
    """Run one bounded worker request through a configured sequential callback."""

    provider_name = "sequential"

    def __init__(
        self,
        runner: Callable[[Mapping[str, Any]], Mapping[str, Any] | WorkerResult] | None,
        *,
        available: bool = True,
    ) -> None:
        super().__init__(runner, available=available)
