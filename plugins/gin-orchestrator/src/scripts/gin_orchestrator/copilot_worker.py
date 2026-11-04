"""GitHub Copilot native-harness worker bridge (no cloud SDK dependency)."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from workflow_core.ext import PROVIDER_DEFAULT

from .circuit_breaker import FailureKind
from .config import ORCHESTRATOR_DEFAULTS
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

COPILOT_ENV_KEYS = (
    "COPILOT_HOME",
    "GH_TOKEN",
    "GITHUB_TOKEN",
    "COPILOT_GITHUB_TOKEN",
    "GH_HOST",
    "COPILOT_GH_HOST",
)


def _copilot_env_extra(source: Mapping[str, str] | None = None) -> dict[str, str]:
    env = os.environ if source is None else source
    return {key: env[key] for key in COPILOT_ENV_KEYS if key in env and env[key]}


def build_copilot_invocation(
    executable: str,
    model: str,
    workspace: Path,
    prompt: str,
    *,
    timeout_seconds: float = float(ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"]),
    effort: str | None = None,
    agent: str | None = None,
    env: Mapping[str, str] | None = None,
) -> NativeCliInvocation:
    resolved_workspace = Path(workspace).resolve()
    argv = [
        executable,
        "-p",
        prompt,
        "--allow-all-tools",
        "--no-ask-user",
        "--output-format",
        "json",
        "--add-dir",
        str(resolved_workspace),
    ]
    if model and model != PROVIDER_DEFAULT:
        argv.extend(["--model", model])
    if effort is not None:
        argv.extend(["--reasoning-effort", effort])
    if agent is not None:
        argv.extend(["--agent", agent])
    return NativeCliInvocation(
        tuple(argv),
        resolved_workspace,
        b"",
        timeout_seconds,
        env_extra=_copilot_env_extra(env),
    )


def copilot_health(
    executable: str,
    *,
    help_text: str | None = None,
    model: str | None = None,
    native_runner: NativeCliRunner | None = None,
    workspace: Path | None = None,
    effort: str | None = None,
) -> NativeHealth:
    help_text = probe_help(executable, "--help") if help_text is None else help_text
    if help_text is None:
        return NativeHealth(False, "executable_or_help_unavailable", False)
    options = frozenset(re.findall(r"--[A-Za-z0-9][A-Za-z0-9-]*", help_text))
    supported = "--model" in options and (effort is None or "--reasoning-effort" in options)
    if not {"--prompt", "--allow-all-tools", "--output-format"}.issubset(options):
        return NativeHealth(False, "required_flags_unverified", supported)
    if effort is not None and "--reasoning-effort" not in options:
        return NativeHealth(False, "required_flags_unverified", False)
    health = NativeHealth(
        True,
        "ready" if supported else "explicit_model_selection_unverified",
        supported,
    )
    if not supported or model is None or model == PROVIDER_DEFAULT or native_runner is None or workspace is None:
        return health
    try:
        native_runner.run(
            build_copilot_invocation(
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
            return NativeHealth(False, "invalid_model", supported)
    return health


class CopilotWorkerAdapter(SynchronousWorkerAdapter):
    provider_name = "copilot"

    def __init__(
        self,
        native_dispatch: Callable[[Mapping[str, Any]], Mapping[str, Any] | WorkerResult] | None = None,
        *,
        native_runner: NativeCliRunner | None = None,
        executable: str | None = None,
        model: str | None = None,
        workspace: Path | None = None,
        timeout_seconds: float = float(ORCHESTRATOR_DEFAULTS["worker"]["timeout_seconds"]),
        effort: str | None = None,
        agent: str | None = None,
    ) -> None:
        cancellable_dispatch = None
        if native_dispatch is None and all((native_runner, executable, model, workspace)):
            cancellable_dispatch = native_cancellable_dispatch(
                native_runner,
                lambda prompt: build_copilot_invocation(
                    str(executable),
                    str(model),
                    Path(workspace),
                    prompt,
                    timeout_seconds=timeout_seconds,
                    effort=effort,
                    agent=agent,
                ),
            )
        super().__init__(
            native_dispatch,
            available=native_dispatch is not None or cancellable_dispatch is not None,
            payload_factory=native_worker_payload,
            cancellable_runner=cancellable_dispatch,
        )
