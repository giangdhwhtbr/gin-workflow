"""Fake gin-orchestrator CLI for testing delegation."""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
import contextlib
import json
import os
from pathlib import Path
from typing import Any

from workflow_core import orchestrator_client


def fake_orchestrator(
    dir: Path | str,
    *,
    contract: int | dict[str, Any] = 2,
    capabilities: Sequence[str] = ("health", "models", "routes", "reviewer", "doctor"),
    fail: Sequence[str] = (),
    replies: Mapping[str, Any] | None = None,
) -> Path:
    """Write an executable gin-orchestrator script in dir."""
    target_dir = Path(dir).resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    stub = target_dir / "gin-orchestrator"

    script = f"""#!/usr/bin/env python3
import json
from pathlib import Path
import sys

contract = {repr(contract)}
capabilities = {repr(list(capabilities))}
fail = {repr(set(fail))}
replies = {repr(dict(replies) if replies else {})}

root = Path(__file__).resolve().parent
calls_file = root / ".calls"
with open(calls_file, "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")

if len(sys.argv) < 2:
    sys.exit(2)

cmd = sys.argv[1]
full_cmd = " ".join(sys.argv[1:3]) if len(sys.argv) > 2 else cmd

if cmd in fail or full_cmd in fail:
    sys.exit(1)

if cmd == "version":
    if isinstance(contract, dict):
        print(json.dumps(contract))
    else:
        print(json.dumps({{
            "contract": contract,
            "orchestrator_version": "0.1.0",
            "requires_gin_workflow": ">=2.0,<3",
            "capabilities": capabilities,
        }}))
    sys.exit(0)

reply = None
if full_cmd in replies:
    reply = replies[full_cmd]
elif cmd in replies:
    reply = replies[cmd]

if reply is not None:
    if isinstance(reply, str):
        print(reply)
    else:
        print(json.dumps(reply))
    sys.exit(0)

print("{{}}")
sys.exit(0)
"""
    stub.write_text(script, encoding="utf-8")
    stub.chmod(0o755)
    return stub


def calls(dir: Path | str) -> list[list[str]]:
    path = Path(dir) / ".calls"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def call_count(dir: Path | str, command: str = "version") -> int:
    return sum(1 for c in calls(dir) if c and c[0] == command)


@contextlib.contextmanager
def on_path(dir: Path | str) -> Iterator[Path]:
    """Patch PATH and clear orchestrator_client.status cache."""
    if hasattr(orchestrator_client, "status") and hasattr(orchestrator_client.status, "cache_clear"):
        orchestrator_client.status.cache_clear()
    old_path = os.environ.get("PATH", "")
    target = Path(dir).resolve()
    os.environ["PATH"] = f"{target}{os.pathsep}{old_path}"
    try:
        yield target
    finally:
        os.environ["PATH"] = old_path
        if hasattr(orchestrator_client, "status") and hasattr(orchestrator_client.status, "cache_clear"):
            orchestrator_client.status.cache_clear()
