"""Claude native-harness worker bridge (no cloud SDK dependency)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from .native_cli import (
    NativeCliInvocation,
    NativeCliRunner,
    NativeHealth,
    direct_worker_result,
    probe_help,
    worker_prompt,
)
from .worker_dispatch import SynchronousWorkerAdapter, WorkerRequest, WorkerResult


def build_claude_invocation(
    executable: str,
    model: str,
    workspace: Path,
    prompt: str,
    *,
    timeout_seconds: float = 900,
) -> NativeCliInvocation:
    return NativeCliInvocation(
        (
            executable,
            "-p",
            "--model",
            model,
            "--output-format",
            "json",
            "--permission-mode",
            "acceptEdits",
        ),
        workspace,
        prompt.encode("utf-8"),
        timeout_seconds,
    )


def claude_health(executable: str, *, help_text: str | None = None) -> NativeHealth:
    help_text = probe_help(executable, "--help") if help_text is None else help_text
    if help_text is None:
        return NativeHealth(False, "executable_or_help_unavailable", False)
    supported = "--model" in help_text and "--output-format" in help_text
    return NativeHealth(supported, "ready" if supported else "required_flags_unverified", supported)


def _payload(request: WorkerRequest) -> Mapping[str, Any]:
    return {**request.to_payload(), "delegate_to": "subagent-driven-development"}


class ClaudeWorkerAdapter(SynchronousWorkerAdapter):
    provider_name = "claude"

    def __init__(
        self,
        native_dispatch: Callable[[Mapping[str, Any]], Mapping[str, Any] | WorkerResult] | None = None,
        *,
        native_runner: NativeCliRunner | None = None,
        executable: str | None = None,
        model: str | None = None,
        workspace: Path | None = None,
    ) -> None:
        if native_dispatch is None and all((native_runner, executable, model, workspace)):
            def native_dispatch(payload: Mapping[str, Any]) -> Mapping[str, Any]:
                invocation = build_claude_invocation(
                    str(executable), str(model), Path(workspace), worker_prompt(payload)
                )
                return direct_worker_result(native_runner.run(invocation))
        super().__init__(native_dispatch, available=native_dispatch is not None, payload_factory=_payload)
