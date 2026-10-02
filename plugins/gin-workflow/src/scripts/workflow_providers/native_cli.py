"""Safe non-interactive process boundary for authenticated native CLIs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import threading
import time
from types import MappingProxyType
from typing import Callable

from workflow_core.executable_resolver import PROVIDER_EXE_ALIASES

from .circuit_breaker import FailureKind
from .worker_dispatch import _SECRET_VALUE

MAX_DIAGNOSTIC_CHARS = 2000


@dataclass(frozen=True)
class NativeCliInvocation:
    argv: tuple[str, ...]
    cwd: Path
    stdin: bytes
    timeout_seconds: float
    idle_timeout_seconds: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "argv", tuple(str(item) for item in self.argv))
        object.__setattr__(self, "cwd", Path(self.cwd).resolve())
        object.__setattr__(self, "stdin", bytes(self.stdin))
        if not self.argv or self.timeout_seconds <= 0:
            raise ValueError("native CLI requires argv and positive timeout")
        if self.idle_timeout_seconds is not None and self.idle_timeout_seconds <= 0:
            raise ValueError("native CLI idle_timeout_seconds must be positive when set")

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

    @property
    def explicit_model_selection(self) -> bool:
        return self.supports_model_selection


class NativeCliError(RuntimeError):
    def __init__(
        self,
        kind: FailureKind,
        message: str,
        *,
        changed_files: tuple[str, ...] = (),
    ) -> None:
        self.kind = kind
        self.changed_files = tuple(changed_files)
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


MODEL_PROBE_PROMPT = "Reply with exactly the single word OK. Do not read, write, or modify any files."
MODEL_PROBE_TIMEOUT_SECONDS = 30.0


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
    if "model" in diagnostic and any(
        token in diagnostic
        for token in (
            "not supported",
            "unsupported",
            "not a valid model",
            "invalid model",
            "unknown model",
            "no access to",
        )
    ):
        return FailureKind.INVALID_MODEL
    if any(token in diagnostic for token in ("service unavailable", "connection refused", "502", "503")):
        return FailureKind.SERVICE
    return FailureKind.CRASH


def _redact_secrets(text: str) -> str:
    return _SECRET_VALUE.sub("[REDACTED]", text)


def _diagnostic_from_stdout(stdout: bytes) -> str | None:
    """Best-effort extraction of an error/message field from JSON(L) stdout records."""
    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return None
    records: list[object] = []
    try:
        records.append(json.loads(text))
    except json.JSONDecodeError:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    for record in reversed(records):
        if not isinstance(record, Mapping):
            continue
        for field in ("error", "message", "detail", "reason"):
            value = record.get(field)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, Mapping):
                inner = value.get("message")
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
    return None


def _classified_diagnostic(kind: FailureKind, stdout: bytes, stderr: bytes) -> str:
    """Sanitized, bounded diagnostic text for a classified native CLI failure."""
    diagnostic = _diagnostic_from_stdout(stdout) or stderr.decode("utf-8", errors="replace").strip()
    diagnostic = _redact_secrets(diagnostic) or f"native CLI failed with classified reason: {kind.value}"
    if len(diagnostic) > MAX_DIAGNOSTIC_CHARS:
        diagnostic = diagnostic[:MAX_DIAGNOSTIC_CHARS] + "...[truncated]"
    return diagnostic


GRACEFUL_STOP_GRACE_SECONDS = 10.0
POLL_INTERVAL_SECONDS = 0.05


def _workspace_changed_files(cwd: Path) -> tuple[str, ...]:
    """Best-effort real changed-file list for a workspace, e.g. after a kill/cancel."""
    try:
        completed = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=sanitized_environment(),
            timeout=5,
            check=False,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ()
    if completed.returncode:
        return ()
    files = []
    for line in completed.stdout.decode("utf-8", errors="replace").splitlines():
        if len(line) > 3 and line[3:].strip():
            files.append(line[3:].strip())
    return tuple(files)


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
        idle_timeout_seconds = invocation.idle_timeout_seconds

        activity_lock = threading.Lock()
        last_activity = [time.monotonic()]
        stdout_chunks: list[bytes] = []
        stderr_chunks: list[bytes] = []

        def pump(stream, sink: list[bytes]) -> None:
            try:
                for chunk in iter(lambda: stream.read(4096), b""):
                    sink.append(chunk)
                    with activity_lock:
                        last_activity[0] = time.monotonic()
            except (OSError, ValueError):
                pass

        def feed_stdin() -> None:
            try:
                if invocation.stdin:
                    process.stdin.write(invocation.stdin)
                process.stdin.close()
            except (OSError, ValueError, BrokenPipeError):
                pass

        stdin_thread = threading.Thread(target=feed_stdin, daemon=True)
        stdout_thread = threading.Thread(target=pump, args=(process.stdout, stdout_chunks), daemon=True)
        stderr_thread = threading.Thread(target=pump, args=(process.stderr, stderr_chunks), daemon=True)
        stdin_thread.start()
        stdout_thread.start()
        stderr_thread.start()

        def group_alive() -> bool:
            # process.poll() reaps the leader as soon as it exits; without reaping it
            # first, killpg(pid, 0) below would keep reporting an unreaped zombie as
            # "alive" and this check would never observe termination.
            if process.poll() is None:
                return True
            if os.name != "posix":
                return False
            try:
                os.killpg(process.pid, 0)
                return True
            except ProcessLookupError:
                return False

        def wait_until_dead(timeout_seconds: float) -> bool:
            stop_deadline = time.monotonic() + timeout_seconds
            while group_alive() and time.monotonic() < stop_deadline:
                time.sleep(POLL_INTERVAL_SECONDS)
            return not group_alive()

        def terminate_tree() -> None:
            """Graceful stop signal first (bounded grace window), then force-kill escalation."""
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGINT)
                else:
                    process.terminate()
            except ProcessLookupError:
                pass
            if wait_until_dead(GRACEFUL_STOP_GRACE_SECONDS):
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
                return
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            except ProcessLookupError:
                pass
            if not wait_until_dead(0.2):
                try:
                    if os.name == "posix":
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass
            try:
                process.wait(timeout=0.5)
            except subprocess.TimeoutExpired as error:
                raise NativeCliError(
                    FailureKind.CRASH, "native CLI process group did not terminate"
                ) from error

        kind: FailureKind | None = None
        idle_fired = False
        while True:
            if process.poll() is not None:
                break
            if cancel_event is not None and cancel_event.is_set():
                kind = FailureKind.CANCELLED
                break
            if time.monotonic() >= deadline:
                kind = FailureKind.TIMEOUT
                break
            if idle_timeout_seconds is not None:
                with activity_lock:
                    quiet_since = last_activity[0]
                if time.monotonic() - quiet_since >= idle_timeout_seconds:
                    kind = FailureKind.TIMEOUT
                    idle_fired = True
                    break
            time.sleep(POLL_INTERVAL_SECONDS)

        def close_pipes() -> None:
            for pipe in (process.stdin, process.stdout, process.stderr):
                try:
                    pipe.close()
                except (OSError, ValueError):
                    pass

        if kind is not None:
            terminate_tree()
            stdin_thread.join(timeout=1)
            stdout_thread.join(timeout=1)
            stderr_thread.join(timeout=1)
            close_pipes()
            changed_files = _workspace_changed_files(invocation.cwd)
            if kind is FailureKind.CANCELLED:
                message = "native CLI invocation cancelled"
            elif idle_fired:
                message = (
                    "native CLI invocation produced no output for "
                    f"{invocation.idle_timeout_seconds}s (idle timeout)"
                )
            else:
                message = f"native CLI invocation exceeded its {invocation.timeout_seconds}s timeout"
            raise NativeCliError(kind, message, changed_files=changed_files)

        process.wait()
        stdin_thread.join(timeout=1)
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        close_pipes()
        stdout = b"".join(stdout_chunks)
        stderr = b"".join(stderr_chunks)

        if process.returncode:
            failure_kind = classify_native_failure(stderr.decode("utf-8", errors="replace"))
            diagnostic = _classified_diagnostic(failure_kind, stdout, stderr)
            raise NativeCliError(failure_kind, diagnostic)
        try:
            records = _parse_records(stdout)
        except UnicodeDecodeError as error:
            raise NativeCliError(FailureKind.INVALID_RESULT, "native CLI returned invalid UTF-8") from error
        return NativeCliOutput(records)


_CLAUDE_ALIASES = (("opus", "Claude Opus (latest)"), ("sonnet", "Claude Sonnet (latest)"), ("haiku", "Claude Haiku (latest)"))
_LIST_COMMANDS = {"codex": ("debug", "models"), "antigravity": ("models",)}
_LEVEL_SUFFIX = re.compile(r"-(low|medium|high)$")


def list_models(
    provider: str,
    *,
    runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> list[dict]:
    """Models a provider CLI offers; [] on any failure so setup falls back to manual entry."""
    if provider == "claude":
        return [{"id": i, "label": label, "description": "alias tracks the latest model", "reasoning_levels": []}
                for i, label in _CLAUDE_ALIASES]
    if provider not in _LIST_COMMANDS:
        return []
    executable = which(PROVIDER_EXE_ALIASES.get(provider, (provider,))[0])
    if executable is None:
        return []
    run = runner or (lambda argv: subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False,
                                                  env=sanitized_environment()))
    try:
        completed = run([executable, *_LIST_COMMANDS[provider]])
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0:
        return []
    if provider == "codex":
        try:
            data = json.loads(completed.stdout)
        except ValueError:
            return []
        entries = data.get("models", data) if isinstance(data, dict) else data
        return [{"id": str(m.get("slug") or m.get("id")), "label": str(m.get("display_name", m.get("slug", ""))),
                 "description": str(m.get("description", "")),
                 "reasoning_levels": [str(l.get("effort", l)) if isinstance(l, dict) else str(l)
                                      for l in m.get("supported_reasoning_levels", [])]}
                for m in entries if isinstance(m, dict) and m.get("visibility", "list") == "list" and (m.get("slug") or m.get("id"))]
    models = []
    for line in completed.stdout.splitlines():
        if "\t" not in line:
            continue
        model_id, label = (part.strip() for part in line.split("\t", 1))
        match = _LEVEL_SUFFIX.search(model_id)
        models.append({"id": model_id, "label": label, "description": "",
                       "reasoning_levels": [match.group(1)] if match else []})
    return models
