"""Claude native-harness worker bridge (no cloud SDK dependency)."""

from __future__ import annotations

from pathlib import Path
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


# Scoped Bash allowlist: covers the read-only inspection, test-runner, and
# package-manager commands a worker legitimately needs without prompting, while
# stopping short of unrestricted shell access. --permission-mode acceptEdits
# alone only auto-accepts file edits, not Bash -- the incident this fixes had a
# worker's shell commands denied mid-task despite acceptEdits being set.
SCOPED_BASH_ALLOWLIST = (
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "Bash(git show:*)",
    "Bash(npm test:*)",
    "Bash(npm run:*)",
    "Bash(yarn test:*)",
    "Bash(pnpm test:*)",
    "Bash(python3 -m pytest:*)",
    "Bash(python -m pytest:*)",
    "Bash(python3 -m unittest:*)",
    "Bash(npm install:*)",
    "Bash(npm ci:*)",
    "Bash(pip install:*)",
    "Bash(pip3 install:*)",
)


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
            "--allowedTools",
            ",".join(SCOPED_BASH_ALLOWLIST),
        ),
        workspace,
        prompt.encode("utf-8"),
        timeout_seconds,
    )


def claude_health(
    executable: str,
    *,
    help_text: str | None = None,
    model: str | None = None,
    native_runner: NativeCliRunner | None = None,
    workspace: Path | None = None,
) -> NativeHealth:
    help_text = probe_help(executable, "--help") if help_text is None else help_text
    if help_text is None:
        return NativeHealth(False, "executable_or_help_unavailable", False)
    supported = (
        "--model" in help_text and "--output-format" in help_text and "--allowedTools" in help_text
    )
    health = NativeHealth(supported, "ready" if supported else "required_flags_unverified", supported)
    if not supported or model is None or native_runner is None or workspace is None:
        return health
    try:
        native_runner.run(
            build_claude_invocation(
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
        timeout_seconds: float = 900,
    ) -> None:
        cancellable_dispatch = None
        if native_dispatch is None and all((native_runner, executable, model, workspace)):
            cancellable_dispatch = native_cancellable_dispatch(
                native_runner,
                lambda prompt: build_claude_invocation(
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
