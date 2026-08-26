"""Codex native-harness worker bridge (no cloud SDK dependency)."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable, Mapping

from .native_cli import (
    MODEL_PROBE_PROMPT,
    MODEL_PROBE_TIMEOUT_SECONDS,
    NativeCliError,
    NativeCliInvocation,
    NativeCliRunner,
    NativeHealth,
    direct_worker_result,
    probe_help,
    worker_prompt,
)
from .circuit_breaker import FailureKind
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
            "--approve-for-me",
            "--cd",
            str(Path(workspace).resolve()),
            "-",
        ),
        workspace,
        prompt.encode("utf-8"),
        timeout_seconds,
    )


def codex_health(
    executable: str,
    *,
    help_text: str | None = None,
    model: str | None = None,
    native_runner: NativeCliRunner | None = None,
    workspace: Path | None = None,
) -> NativeHealth:
    help_text = probe_help(executable, "exec", "--help") if help_text is None else help_text
    if help_text is None:
        return NativeHealth(False, "executable_or_help_unavailable", False)
    options = frozenset(re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", help_text))
    model_selection = "--model" in options
    supported = all(
        flag in options
        for flag in ("--model", "--json", "--ephemeral", "--approve-for-me", "--cd")
    )
    health = NativeHealth(
        supported,
        "ready" if supported else "required_flags_unverified",
        model_selection,
    )
    if not supported or model is None or native_runner is None or workspace is None:
        return health
    try:
        native_runner.run(
            build_codex_invocation(
                executable,
                model,
                workspace,
                MODEL_PROBE_PROMPT,
                timeout_seconds=MODEL_PROBE_TIMEOUT_SECONDS,
            )
        )
    except NativeCliError as error:
        if error.kind is FailureKind.INVALID_MODEL:
            return NativeHealth(False, "invalid_model", model_selection)
    return health


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
        timeout_seconds: float = 900,
    ) -> None:
        cancellable_dispatch = None
        if native_dispatch is None and all((native_runner, executable, model, workspace)):
            def cancellable_dispatch(payload: Mapping[str, Any], cancel_event) -> Mapping[str, Any]:
                invocation = build_codex_invocation(
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
