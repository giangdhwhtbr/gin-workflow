"""The orchestrator CLI contract (v2), run as `gin-orchestrator` from PATH."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import functools
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

CONTRACT_VERSION = 2
MISSING = "orchestrator_missing"
MISMATCH = "orchestrator_contract_mismatch"
FAILED = "orchestrator_failed"
INSTALL_COMMAND = "./install.sh --plugin gin-orchestrator"


class OrchestratorError(Exception):
    """The orchestrator cannot be used; the message is MISSING, MISMATCH or FAILED."""


def call(argv: Sequence[str], *, timeout: float = 120) -> Any:
    """Run gin-orchestrator argv --json, returning decoded JSON or raising OrchestratorError."""
    installed = shutil.which("gin-orchestrator")
    if not installed:
        raise OrchestratorError(MISSING)
    args = [installed, *(a for a in argv if a != "--json"), "--json"]
    try:
        done = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if done.returncode == 0:
            return json.loads(done.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    raise OrchestratorError(FAILED)


@functools.cache
def status() -> dict[str, Any]:
    """Report orchestrator availability, cached per process."""
    installed = shutil.which("gin-orchestrator")
    if not installed:
        return {
            "available": False,
            "version": None,
            "contract": None,
            "capabilities": [],
            "reason": MISSING,
        }
    try:
        done = subprocess.run(
            [installed, "version", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if done.returncode != 0:
            return {
                "available": False,
                "version": None,
                "contract": None,
                "capabilities": [],
                "reason": FAILED,
            }
        data = json.loads(done.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return {
            "available": False,
            "version": None,
            "contract": None,
            "capabilities": [],
            "reason": FAILED,
        }

    contract = data.get("contract") if isinstance(data, Mapping) else None
    version = data.get("orchestrator_version") if isinstance(data, Mapping) else None
    caps = data.get("capabilities", []) if isinstance(data, Mapping) else []
    if not isinstance(caps, list):
        caps = []

    if contract != CONTRACT_VERSION:
        return {
            "available": False,
            "version": version,
            "contract": contract,
            "capabilities": caps,
            "reason": MISMATCH,
        }

    return {
        "available": True,
        "version": version,
        "contract": contract,
        "capabilities": caps,
        "reason": None,
    }


def delegates(config: Mapping[str, Any], capability: str) -> bool:
    """True when provider_mode is multi, orchestrator is available, and capability is listed."""
    if config.get("provider_mode") != "multi":
        return False
    st = status()
    if not st.get("available"):
        return False
    return capability in (st.get("capabilities") or [])


def warning(config: Mapping[str, Any]) -> str | None:
    """Warning string if multi mode is configured but orchestrator is unavailable, else None."""
    if config.get("provider_mode") != "multi":
        return None
    st = status()
    if st.get("available"):
        return None
    reason = st.get("reason") or MISSING
    return f"{reason}; install with {INSTALL_COMMAND}"


def models(provider: str) -> list[dict]:
    """List models for a provider via orchestrator, returning [] on FAILED or MISSING."""
    try:
        res = call(["models", "--provider", provider], timeout=60)
        return res if isinstance(res, list) else []
    except OrchestratorError as error:
        if str(error) in (FAILED, MISSING):
            return []
        raise
