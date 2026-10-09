"""OpenCode native-harness worker bridge (no cloud SDK dependency)."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable, Mapping

from workflow_core.provider_config import PROVIDER_DEFAULT

from .circuit_breaker import FailureKind
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
from .worker_dispatch import SynchronousWorkerAdapter, WorkerResult


def build_opencode_invocation(
    executable: str,
    model: str,
    workspace: Path,
    prompt: str,
    *,
    timeout_seconds: float = 900,
) -> NativeCliInvocation:
    # OpenCode has no --cd/--add-dir: the process cwd is the workspace.
    resolved_workspace = Path(workspace).resolve()
    argv = [executable, "run", "--standalone", "--auto", "--format", "json"]
    if model and model != PROVIDER_DEFAULT:
        argv.extend(["--model", model])
    argv.append(prompt)
    return NativeCliInvocation(tuple(argv), resolved_workspace, b"", timeout_seconds)


def opencode_health(
    executable: str,
    *,
    help_text: str | None = None,
    model: str | None = None,
    native_runner: NativeCliRunner | None = None,
    workspace: Path | None = None,
) -> NativeHealth:
    help_text = probe_help(executable, "run", "--help") if help_text is None else help_text
    if help_text is None:
        return NativeHealth(False, "executable_or_help_unavailable", False)
    options = frozenset(re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", help_text))
    supported = "--model" in options
    if "--auto" not in options or "--format" not in options:
        return NativeHealth(False, "required_flags_unverified", supported)
    health = NativeHealth(
        True,
        "ready" if supported else "explicit_model_selection_unverified",
        supported,
    )
    if not supported or model is None or model == PROVIDER_DEFAULT or native_runner is None or workspace is None:
        return health
    try:
        native_runner.run(
            build_opencode_invocation(
                executable,
                model,
                workspace,
                MODEL_PROBE_PROMPT,
                timeout_seconds=MODEL_PROBE_TIMEOUT_SECONDS,
            )
        )
    except NativeCliError as error:
        if error.kind is FailureKind.INVALID_MODEL:
            return NativeHealth(False, "invalid_model", supported)
    return health


class OpenCodeWorkerAdapter(SynchronousWorkerAdapter):
    provider_name = "opencode"

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
            cancellable_dispatch = native_cancellable_dispatch(
                native_runner,
                lambda prompt: build_opencode_invocation(
                    str(executable),
                    str(model),
                    Path(workspace),
                    prompt,
                    timeout_seconds=timeout_seconds,
                ),
            )
        super().__init__(
            native_dispatch,
            available=native_dispatch is not None or cancellable_dispatch is not None,
            payload_factory=native_worker_payload,
            cancellable_runner=cancellable_dispatch,
        )
