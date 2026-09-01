"""Antigravity native-harness worker bridge (no cloud SDK dependency)."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable, Mapping

from workflow_core.provider_config import PROVIDER_DEFAULT

from .native_cli import (
    NativeCliInvocation,
    NativeCliRunner,
    NativeHealth,
    direct_worker_result,
    probe_help,
    worker_prompt,
)
from .worker_dispatch import SynchronousWorkerAdapter, WorkerRequest, WorkerResult


def build_antigravity_invocation(
    executable: str,
    model: str,
    workspace: Path,
    prompt: str,
    *,
    timeout_seconds: float = 900,
) -> NativeCliInvocation:
    resolved_workspace = Path(workspace).resolve()
    timeout_str = f"{int(timeout_seconds)}s"
    argv = (
        executable,
        "--add-dir",
        str(resolved_workspace),
        "--sandbox",
        "--print-timeout",
        timeout_str,
        "--print",
        prompt,
    )
    return NativeCliInvocation(
        argv,
        resolved_workspace,
        b"",
        timeout_seconds,
    )



def antigravity_health(executable: str, *, help_text: str | None = None) -> NativeHealth:
    help_text = probe_help(executable, "--help") if help_text is None else help_text
    if help_text is None:
        return NativeHealth(False, "executable_or_help_unavailable", False)
    options = frozenset(re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", help_text))
    supported = "--model" in options
    if "--print" not in options or "--sandbox" not in options:
        return NativeHealth(False, "required_flags_unverified", supported)
    return NativeHealth(
        True,
        "ready" if supported else "explicit_model_selection_unverified",
        supported,
    )


def _payload(request: WorkerRequest) -> Mapping[str, Any]:
    return {**request.to_payload(), "delegate_to": "subagent-driven-development"}


class AntigravityWorkerAdapter(SynchronousWorkerAdapter):
    provider_name = "antigravity"

    def __init__(
        self,
        native_dispatch: Callable[[Mapping[str, Any]], Mapping[str, Any] | WorkerResult] | None = None,
        *,
        native_runner: NativeCliRunner | None = None,
        executable: str | None = None,
        model: str | None = None,
        workspace: Path | None = None,
        timeout_seconds: float = 900,
    ) -> None:
        cancellable_dispatch = None
        if native_dispatch is None and all((native_runner, executable, model, workspace)):
            def cancellable_dispatch(payload: Mapping[str, Any], cancel_event) -> Mapping[str, Any]:
                invocation = build_antigravity_invocation(
                    str(executable),
                    str(model),
                    Path(workspace),
                    worker_prompt(payload),
                    timeout_seconds=timeout_seconds,
                )
                return direct_worker_result(native_runner.run(invocation, cancel_event=cancel_event))
        super().__init__(
            native_dispatch,
            available=native_dispatch is not None or cancellable_dispatch is not None,
            payload_factory=_payload,
            cancellable_runner=cancellable_dispatch,
        )
