"""Safe non-interactive process boundary for authenticated native CLIs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from types import MappingProxyType
from typing import Callable

from .circuit_breaker import FailureKind


@dataclass(frozen=True)
class NativeCliInvocation:
    argv: tuple[str, ...]
    cwd: Path
    stdin: bytes
    timeout_seconds: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "argv", tuple(str(item) for item in self.argv))
        object.__setattr__(self, "cwd", Path(self.cwd).resolve())
        object.__setattr__(self, "stdin", bytes(self.stdin))
        if not self.argv or self.timeout_seconds <= 0:
            raise ValueError("native CLI requires argv and positive timeout")

    @property
    def shell(self) -> bool:
        return False


@dataclass(frozen=True)
class NativeCliOutput:
    records: tuple[Mapping[str, object], ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "records",
            tuple(MappingProxyType(dict(record)) for record in self.records),
        )


@dataclass(frozen=True)
class NativeHealth:
    available: bool
    reason: str
    supports_model_selection: bool


class NativeCliError(RuntimeError):
    def __init__(self, kind: FailureKind, message: str) -> None:
        self.kind = kind
        super().__init__(message)


def sanitized_environment(source: Mapping[str, str] | None = None) -> dict[str, str]:
    source = source or os.environ
    allowed = {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "LC_ALL",
        "TERM",
        "TMPDIR",
        "XDG_CONFIG_HOME",
        "CODEX_HOME",
        "CLAUDE_CONFIG_DIR",
    }
    return {key: value for key, value in source.items() if key in allowed or key.startswith("LC_")}


def probe_help(executable: str, *arguments: str) -> str | None:
    """Read installed CLI help without a shell or inherited secret variables."""
    try:
        completed = subprocess.run(
            [executable, *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            cwd=Path.cwd(),
            env=sanitized_environment(),
            timeout=5,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode:
        return None
    return completed.stdout.decode("utf-8", errors="replace")


def worker_prompt(payload: Mapping[str, object]) -> str:
    return (
        "Execute this bounded worker request. Return only one JSON object containing every "
        "field listed in expected_output; do not wrap it in Markdown.\n"
        + json.dumps(dict(payload), sort_keys=True)
    )


def direct_worker_result(output: NativeCliOutput) -> Mapping[str, object]:
    required = {"status", "task_id", "summary", "changed_files", "commits", "tests", "evidence", "blockers"}
    for record in reversed(output.records):
        if required.issubset(record):
            return record
        for field in ("result", "response", "text"):
            candidate = record.get(field)
            if isinstance(candidate, str):
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, Mapping) and required.issubset(parsed):
                    return parsed
        item = record.get("item")
        if isinstance(item, Mapping) and isinstance(item.get("text"), str):
            try:
                parsed = json.loads(item["text"])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, Mapping) and required.issubset(parsed):
                return parsed
    raise NativeCliError(FailureKind.INVALID_RESULT, "native CLI output lacks worker result contract")


def classify_native_failure(stderr: str) -> FailureKind:
    diagnostic = stderr.lower()
    if any(token in diagnostic for token in ("quota", "usage limit", "credits exhausted")):
        return FailureKind.QUOTA
    if any(token in diagnostic for token in ("rate limit", "too many requests", "429")):
        return FailureKind.RATE_LIMIT
    if any(token in diagnostic for token in ("unauthorized", "authentication", "not logged in", "401")):
        return FailureKind.AUTH
    if any(token in diagnostic for token in ("service unavailable", "connection refused", "502", "503")):
        return FailureKind.SERVICE
    return FailureKind.CRASH


def _parse_records(stdout: bytes) -> tuple[Mapping[str, object], ...]:
    text = stdout.decode("utf-8", errors="strict").strip()
    if not text:
        raise NativeCliError(FailureKind.INVALID_RESULT, "native CLI returned no JSON output")
    try:
        whole = json.loads(text)
    except json.JSONDecodeError:
        try:
            values = [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError as error:
            raise NativeCliError(
                FailureKind.INVALID_RESULT, "native CLI returned malformed JSON output"
            ) from error
    else:
        values = whole if isinstance(whole, list) else [whole]
    if not values or any(not isinstance(value, Mapping) for value in values):
        raise NativeCliError(FailureKind.INVALID_RESULT, "native CLI JSON records must be objects")
    return tuple(dict(value) for value in values)


class NativeCliRunner:
    def __init__(self, *, max_stdin_bytes: int = 65_536) -> None:
        if max_stdin_bytes < 1:
            raise ValueError("max_stdin_bytes must be positive")
        self.max_stdin_bytes = max_stdin_bytes

    def run(
        self,
        invocation: NativeCliInvocation,
        *,
        cancel_event: threading.Event | None = None,
    ) -> NativeCliOutput:
        if len(invocation.stdin) > self.max_stdin_bytes:
            raise NativeCliError(FailureKind.INVALID_RESULT, "native CLI input exceeds size limit")
        if cancel_event is not None and cancel_event.is_set():
            raise NativeCliError(FailureKind.CANCELLED, "native CLI invocation cancelled")
        try:
            process = subprocess.Popen(
                list(invocation.argv),
                cwd=invocation.cwd,
                env=sanitized_environment(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                start_new_session=os.name == "posix",
            )
        except FileNotFoundError as error:
            raise NativeCliError(FailureKind.SERVICE, "native CLI executable unavailable") from error
        except OSError as error:
            raise NativeCliError(FailureKind.CRASH, "native CLI failed to start") from error

        deadline = time.monotonic() + invocation.timeout_seconds
        pending_input: bytes | None = invocation.stdin

        def terminate_tree() -> None:
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            except ProcessLookupError:
                pass
            try:
                process.communicate(timeout=0.2)
            except subprocess.TimeoutExpired:
                pass
            group_alive = False
            if os.name == "posix":
                try:
                    os.killpg(process.pid, 0)
                    group_alive = True
                except ProcessLookupError:
                    pass
            if group_alive or (os.name != "posix" and process.poll() is None):
                try:
                    if os.name == "posix":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass
            try:
                process.communicate(timeout=0.5)
            except subprocess.TimeoutExpired as error:
                raise NativeCliError(
                    FailureKind.CRASH, "native CLI process group did not terminate"
                ) from error

        while True:
            if cancel_event is not None and cancel_event.is_set():
                terminate_tree()
                raise NativeCliError(FailureKind.CANCELLED, "native CLI invocation cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                terminate_tree()
                raise NativeCliError(FailureKind.TIMEOUT, "native CLI invocation timed out")
            try:
                stdout, stderr = process.communicate(
                    input=pending_input,
                    timeout=min(0.05, remaining),
                )
                break
            except subprocess.TimeoutExpired:
                pending_input = None

        if process.returncode:
            kind = classify_native_failure(stderr.decode("utf-8", errors="replace"))
            raise NativeCliError(kind, f"native CLI failed with classified reason: {kind.value}")
        try:
            records = _parse_records(stdout)
        except UnicodeDecodeError as error:
            raise NativeCliError(FailureKind.INVALID_RESULT, "native CLI returned invalid UTF-8") from error
        return NativeCliOutput(records)
