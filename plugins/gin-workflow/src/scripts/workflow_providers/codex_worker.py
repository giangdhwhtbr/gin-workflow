"""Codex native-harness worker bridge (no cloud SDK dependency)."""

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


def build_codex_invocation(
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
            "exec",
            "--model",
            model,
            "--json",
            "--ephemeral",
            "--sandbox",
            "workspace-write",
            "--approve-for-me",
            "-C",
            str(Path(workspace).resolve()),
            "-",
        ),
        workspace,
        prompt.encode("utf-8"),
        timeout_seconds,
    )


def codex_health(executable: str, *, help_text: str | None = None) -> NativeHealth:
    help_text = probe_help(executable, "exec", "--help") if help_text is None else help_text
    if help_text is None:
        return NativeHealth(False, "executable_or_help_unavailable", False)
    supported = all(flag in help_text for flag in ("--model", "--json", "--ephemeral"))
    return NativeHealth(supported, "ready" if supported else "required_flags_unverified", supported)


def _payload(request: WorkerRequest) -> Mapping[str, Any]:
    return {**request.to_payload(), "delegate_to": "subagent-driven-development"}


class CodexWorkerAdapter(SynchronousWorkerAdapter):
    provider_name = "codex"

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
                invocation = build_codex_invocation(
                    str(executable), str(model), Path(workspace), worker_prompt(payload)
                )
                return direct_worker_result(native_runner.run(invocation))
        super().__init__(native_dispatch, available=native_dispatch is not None, payload_factory=_payload)
