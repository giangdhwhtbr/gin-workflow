"""Token usage records from local Claude Code and Codex session logs.

Only numbers and routing fields are read (model, token counts, timestamp, cwd, git branch, session id);
prompt and response text is never kept.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Iterator


@dataclass(frozen=True)
class UsageRecord:
    ts: datetime
    harness: str
    model: str
    session_id: str
    cwd: str
    branch: str
    input: int
    output: int
    cache_read: int
    cache_write: int


@dataclass(frozen=True)
class SourceScan:
    records: tuple[UsageRecord, ...]
    status: str
    skipped_lines: int


def parse_ts(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp without a timezone: {value}")
    return parsed.astimezone(timezone.utc)


def inside(path: str | Path, base: Path) -> bool:
    if not path:
        return False
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(base)))
    except ValueError:
        return False
    return True


def _tokens(usage: Any, *keys: str) -> tuple[int, ...]:
    values = tuple(usage.get(key, 0) if isinstance(usage, dict) else None for key in keys)
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in values):
        raise ValueError("token counts must be non-negative integers")
    return values


def _rows(path: Path) -> Iterator[Any]:
    """Each line parsed as JSON, or None for a line that is not valid JSON."""
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                yield None


def claude_code_records(repo: Path, root: Path | None = None) -> SourceScan:
    repo = Path(os.path.abspath(repo))
    if root is None:
        root = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "projects"
    if not root.is_dir():
        return SourceScan((), "not_found", 0)
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(repo))
    records: list[UsageRecord] = []
    seen: set[tuple[str, str]] = set()
    skipped = 0
    matched = False
    for project in sorted(root.iterdir()):
        if not project.is_dir() or not (project.name == slug or project.name.startswith(slug + "-")):
            continue
        matched = True
        for path in sorted(project.rglob("*.jsonl")):
            for row in _rows(path):
                if row is None:
                    skipped += 1
                    continue
                if not isinstance(row, dict) or row.get("type") != "assistant":
                    continue
                message = row.get("message")
                if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
                    continue
                model = message.get("model")
                if not isinstance(model, str) or not model or model.startswith("<"):
                    continue
                cwd = row.get("cwd")
                if not isinstance(cwd, str) or not inside(cwd, repo):
                    continue
                key = (str(message.get("id", "")), str(row.get("requestId", "")))
                if key != ("", "") and key in seen:
                    continue
                try:
                    tokens = _tokens(message["usage"], "input_tokens", "output_tokens",
                                     "cache_read_input_tokens", "cache_creation_input_tokens")
                    ts = parse_ts(row["timestamp"])
                except (KeyError, TypeError, ValueError, AttributeError):
                    skipped += 1
                    continue
                seen.add(key)
                branch = row.get("gitBranch")
                records.append(UsageRecord(ts, "claude_code", model, str(row.get("sessionId", "")),
                                           os.path.abspath(cwd), branch if isinstance(branch, str) else "",
                                           tokens[0], tokens[1], tokens[2], tokens[3]))
    return SourceScan(tuple(records), "ok" if matched else "not_found", skipped)


def codex_records(repo: Path, root: Path | None = None) -> SourceScan:
    repo = Path(os.path.abspath(repo))
    if root is None:
        root = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex") / "sessions"
    if not root.is_dir():
        return SourceScan((), "not_found", 0)
    records: list[UsageRecord] = []
    skipped = 0
    for path in sorted(root.rglob("rollout-*.jsonl")):
        session, cwd, branch, model = "", "", "", ""
        last_total: Any = None
        for row in _rows(path):
            if row is None:
                skipped += 1
                continue
            if not isinstance(row, dict) or not isinstance(row.get("payload"), dict):
                continue
            payload = row["payload"]
            if row.get("type") == "session_meta":
                session = str(payload.get("id", ""))
                cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else ""
                git = payload.get("git")
                branch = git.get("branch", "") if isinstance(git, dict) else ""
                branch = branch if isinstance(branch, str) else ""
            elif row.get("type") == "turn_context":
                model = payload.get("model") if isinstance(payload.get("model"), str) else model
                if isinstance(payload.get("cwd"), str):
                    cwd = payload["cwd"]
            elif row.get("type") == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info")
                if not isinstance(info, dict):
                    continue
                total = (info.get("total_token_usage") or {}).get("total_tokens") \
                    if isinstance(info.get("total_token_usage"), dict) else None
                if total is not None and total == last_total:
                    continue
                if not inside(cwd, repo):
                    last_total = total
                    continue
                try:
                    if not model:
                        raise ValueError("token count before any model")
                    given, cached, written, output = _tokens(info.get("last_token_usage"), "input_tokens",
                                                             "cached_input_tokens", "cache_write_input_tokens",
                                                             "output_tokens")
                    ts = parse_ts(row["timestamp"])
                except (KeyError, TypeError, ValueError, AttributeError):
                    skipped += 1
                    last_total = total
                    continue
                last_total = total
                records.append(UsageRecord(ts, "codex", model, session, os.path.abspath(cwd), branch,
                                           max(given - cached, 0), output, cached, written))
    return SourceScan(tuple(records), "ok", skipped)
