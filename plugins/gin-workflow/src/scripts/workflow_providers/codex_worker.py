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
    native_cancellable_dispatch,
    native_worker_payload,
    probe_help,
)
from .circuit_breaker import FailureKind
from .worker_dispatch import SynchronousWorkerAdapter, WorkerResult


def build_codex_invocation(
    executable: str,
    model: str,
    workspace: Path,
    prompt: str,
    *,
    timeout_seconds: float = 900,
    effort: str | None = None,
) -> NativeCliInvocation:
    argv = [
        executable,
        "exec",
        "--model",
        model,
        "--json",
        "--ephemeral",
        "--dangerously-bypass-approvals-and-sandbox",
        "--cd",
        str(Path(workspace).resolve()),
    ]
    if effort is not None:
        argv.extend(["-c", f"model_reasoning_effort={effort}"])
    argv.append("-")
    return NativeCliInvocation(
        tuple(argv),
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
    effort: str | None = None,
) -> NativeHealth:
    help_text = probe_help(executable, "exec", "--help") if help_text is None else help_text
    if help_text is None:
        return NativeHealth(False, "executable_or_help_unavailable", False)
    options = frozenset(re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", help_text))
    model_selection = "--model" in options
    supported = all(
        flag in options
        for flag in (
            "--model",
            "--json",
            "--ephemeral",
            "--dangerously-bypass-approvals-and-sandbox",
            "--cd",
        )
    )
    if effort is not None:
        has_config = bool(re.search(r"(?:^|\s)-c\b", help_text)) or "--config" in options
        if not has_config:
            supported = False
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
                effort=effort,
            )
        )
    except NativeCliError as error:
        if error.kind is FailureKind.INVALID_MODEL:
            return NativeHealth(False, "invalid_model", model_selection)
    return health


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
        effort: str | None = None,
    ) -> None:
        cancellable_dispatch = None
        if native_dispatch is None and all((native_runner, executable, model, workspace)):
            cancellable_dispatch = native_cancellable_dispatch(
                native_runner,
                lambda prompt: build_codex_invocation(
                    str(executable),
                    str(model),
                    Path(workspace),
                    prompt,
                    timeout_seconds=timeout_seconds,
                    effort=effort,
                ),
            )
        super().__init__(
            native_dispatch,
            available=native_dispatch is not None or cancellable_dispatch is not None,
            payload_factory=native_worker_payload,
            cancellable_runner=cancellable_dispatch,
        )
