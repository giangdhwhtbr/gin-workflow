"""Summarize token usage, tool calls, and wall time from Claude Code transcript JSONL files."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys

FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def summarize(path: Path) -> dict[str, float]:
    totals = {field: 0 for field in FIELDS}
    tool_calls, stamps = 0, []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("timestamp"):
            stamps.append(datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00")))
        message = entry.get("message") or {}
        if entry.get("type") != "assistant":
            continue
        for field in FIELDS:
            totals[field] += int((message.get("usage") or {}).get(field, 0))
        content = message.get("content") or []
        tool_calls += sum(1 for block in content if isinstance(block, dict) and block.get("type") == "tool_use")
    wall = (max(stamps) - min(stamps)).total_seconds() if stamps else 0.0
    return {**totals, "tool_calls": tool_calls, "wall_seconds": wall}


def table(runs: dict[str, Path]) -> str:
    lines = ["| Run | Input | Output | Cache write | Cache read | Tool calls | Wall s |", "|---|---|---|---|---|---|---|"]
    for label, path in runs.items():
        s = summarize(path)
        lines.append(f"| {label} | {s['input_tokens']} | {s['output_tokens']} | {s['cache_creation_input_tokens']} | "
                     f"{s['cache_read_input_tokens']} | {s['tool_calls']} | {int(s['wall_seconds'])} |")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    runs = dict(arg.split("=", 1) for arg in argv)
    print(table({label: Path(path) for label, path in runs.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
