"""The orchestrator CLI contract (v1), run as `gin-orchestrator` from PATH or the bundled `python -m workflow_providers`."""

from __future__ import annotations

import functools
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

CONTRACT_VERSION = 1
MISMATCH = "orchestrator_contract_mismatch"
FAILED = "orchestrator_failed"
HEALTH_PROVIDERS = frozenset({"claude", "codex", "antigravity", "opencode"})
_SCRIPTS = Path(__file__).resolve().parents[1]


class OrchestratorError(Exception):
    """The orchestrator cannot be used; the message is MISMATCH or FAILED."""


def _run(argv: list[str], *, timeout: float) -> Any:
    installed = shutil.which("gin-orchestrator")
    command = [installed] if installed else [sys.executable, "-m", "workflow_providers"]
    path = os.pathsep.join(filter(None, (str(_SCRIPTS), os.environ.get("PYTHONPATH"))))
    try:
        done = subprocess.run([*command, *argv, "--json"], capture_output=True, text=True, timeout=timeout,
                              check=False, env={**os.environ, "PYTHONPATH": path})
        if done.returncode == 0:
            return json.loads(done.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    raise OrchestratorError(FAILED)


@functools.cache
def _checked() -> None:
    version = _run(["version"], timeout=30)
    if not isinstance(version, dict) or version.get("contract_version") != CONTRACT_VERSION:
        raise OrchestratorError(MISMATCH)


def health(provider: str, executable: str, *, model: str | None = None, effort: str | None = None,
           workspace: Path | None = None) -> dict[str, Any]:
    _checked()
    argv = ["health", "--provider", provider, "--executable", executable]
    for flag, value in (("--model", model), ("--effort", effort), ("--workspace", workspace)):
        if value is not None:
            argv += [flag, str(value)]
    return _run(argv, timeout=120)


def models(provider: str) -> list[dict]:
    try:
        _checked()
        return _run(["models", "--provider", provider], timeout=60)
    except OrchestratorError as error:
        if str(error) == MISMATCH:
            raise
        return []
