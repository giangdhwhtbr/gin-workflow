"""Usage adapters: token records from Claude Code and Codex session logs, numbers and routing fields only."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import team_fixtures  # noqa: E402,F401  (puts the plugin scripts on sys.path)
from workflow_core.usage_logs import (  # noqa: E402
    UsageRecord, claude_code_records, codex_records, inside, parse_ts,
)

SECRET = "SECRET PROMPT"


def _lines(path: Path, rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join((row if isinstance(row, str) else json.dumps(row)) + "\n" for row in rows),
                    encoding="utf-8")


def _assistant(repo: Path, msg_id: str, request: str, *, model: str = "claude-opus-5-5", cwd: Path | None = None,
               branch: str = "master", sidechain: bool = False, output=50, ts: str = "2026-10-04T10:00:00.000Z"):
    return {"type": "assistant", "timestamp": ts, "sessionId": "s1", "cwd": str(cwd or repo),
            "gitBranch": branch, "isSidechain": sidechain, "requestId": request,
            "message": {"id": msg_id, "model": model, "role": "assistant",
                        "content": [{"type": "text", "text": SECRET}],
                        "usage": {"input_tokens": 3, "output_tokens": output, "cache_read_input_tokens": 1000,
                                  "cache_creation_input_tokens": 200}}}


class HelperTests(unittest.TestCase):
    def test_parse_ts_gives_aware_utc(self):
        self.assertEqual(parse_ts("2026-10-04T10:00:00.500Z"),
                         datetime(2026, 10, 4, 10, 0, 0, 500000, tzinfo=timezone.utc))
        self.assertEqual(parse_ts("2026-10-04T12:00:00+02:00"), datetime(2026, 10, 4, 10, tzinfo=timezone.utc))

    def test_inside(self):
        base = Path("/r/repo")
        self.assertTrue(inside("/r/repo", base))
        self.assertTrue(inside("/r/repo/.planning/worktrees/x", base))
        self.assertFalse(inside("/r/repo-other", base))
        self.assertFalse(inside("", base))


class ClaudeCodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo = base / "work" / "repo"
        self.repo.mkdir(parents=True)
        self.root = base / "claude" / "projects"
        slug = re.sub(r"[^A-Za-z0-9]", "-", str(self.repo.resolve()))
        worktree = self.repo / ".planning/worktrees/ep1"
        _lines(self.root / slug / "s1.jsonl", [
            {"type": "user", "message": {"content": SECRET}, "cwd": str(self.repo)},
            _assistant(self.repo, "m1", "r1"),
            _assistant(self.repo, "m1", "r1"),                       # same message, another content block
            _assistant(self.repo, "m2", "r2", model="<synthetic>"),
            "{broken",
            _assistant(self.repo, "m3", "r3", output="many"),
        ])
        _lines(self.root / slug / "s1" / "subagents" / "agent-1.jsonl", [
            _assistant(self.repo, "m4", "r4", sidechain=True, model="claude-sonnet-5-5"),
        ])
        _lines(self.root / (slug + "--planning-worktrees-ep1") / "s2.jsonl", [
            _assistant(self.repo, "m5", "r5", cwd=worktree, branch="feat/x"),
        ])
        _lines(self.root / (slug + "-other") / "s3.jsonl", [
            _assistant(self.repo, "m6", "r6", cwd=base / "work" / "repo-other"),
        ])
        _lines(self.root / "-unrelated" / "s4.jsonl", [_assistant(self.repo, "m7", "r7")])

    def test_reads_records_once_with_cache_tokens(self):
        scan = claude_code_records(self.repo, self.root)
        self.assertEqual(scan.status, "ok")
        self.assertEqual(scan.skipped_lines, 2)
        by_model = sorted((r.model, r.branch) for r in scan.records)
        self.assertEqual(by_model, [("claude-opus-5-5", "feat/x"), ("claude-opus-5-5", "master"),
                                    ("claude-sonnet-5-5", "master")])
        first = next(r for r in scan.records if r.branch == "master" and r.model == "claude-opus-5-5")
        self.assertEqual((first.harness, first.input, first.output, first.cache_read, first.cache_write),
                         ("claude_code", 3, 50, 1000, 200))
        self.assertEqual(first.ts, datetime(2026, 10, 4, 10, tzinfo=timezone.utc))
        self.assertEqual(first.session_id, "s1")

    def test_never_keeps_text(self):
        scan = claude_code_records(self.repo, self.root)
        self.assertNotIn(SECRET, repr(scan))
        for record in scan.records:
            self.assertEqual(set(vars(record)), {f for f in UsageRecord.__dataclass_fields__})

    def test_missing_root_is_not_found(self):
        scan = claude_code_records(self.repo, Path(self.tmp.name) / "nope")
        self.assertEqual((scan.status, scan.records, scan.skipped_lines), ("not_found", (), 0))

    def test_env_root(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.root.parent)}):
            self.assertEqual(len(claude_code_records(self.repo).records), 3)


class CodexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.repo = base / "repo"
        self.repo.mkdir()
        self.root = base / "codex" / "sessions"
        worktree = str(self.repo / ".planning/worktrees/ep1")

        def count(total, inp, cached, out, ts):
            return {"timestamp": ts, "type": "event_msg", "payload": {"type": "token_count", "info": {
                "total_token_usage": {"total_tokens": total},
                "last_token_usage": {"input_tokens": inp, "cached_input_tokens": cached,
                                     "cache_write_input_tokens": 0, "output_tokens": out}}}}

        _lines(self.root / "2026/10/04/rollout-a.jsonl", [
            {"timestamp": "2026-10-04T09:00:00Z", "type": "session_meta",
             "payload": {"id": "c1", "cwd": worktree, "git": {"branch": "feat/x"},
                         "base_instructions": {"text": SECRET}}},
            count(10, 5, 0, 5, "2026-10-04T09:00:01Z"),               # before any turn_context: skipped
            {"timestamp": "2026-10-04T09:00:02Z", "type": "turn_context",
             "payload": {"model": "gpt-6-astra", "cwd": worktree}},
            {"timestamp": "2026-10-04T09:00:03Z", "type": "response_item",
             "payload": {"type": "message", "content": [{"text": SECRET}]}},
            count(1100, 1000, 800, 100, "2026-10-04T09:00:04Z"),
            count(1100, 1000, 800, 100, "2026-10-04T09:00:05Z"),     # same running total: not counted again
            {"timestamp": "2026-10-04T09:00:06Z", "type": "event_msg", "payload": {"type": "token_count", "info": None}},
            "not json",
            count(1400, 250, 200, 50, "2026-10-04T09:00:07Z"),
        ])
        _lines(self.root / "2026/10/04/rollout-b.jsonl", [
            {"timestamp": "2026-10-04T09:00:00Z", "type": "session_meta", "payload": {"id": "c2", "cwd": "/elsewhere"}},
            {"timestamp": "2026-10-04T09:00:02Z", "type": "turn_context", "payload": {"model": "gpt-6-astra"}},
            count(500, 400, 0, 100, "2026-10-04T09:00:04Z"),
        ])

    def test_per_turn_records_with_uncached_input(self):
        scan = codex_records(self.repo, self.root)
        self.assertEqual(scan.status, "ok")
        self.assertEqual(scan.skipped_lines, 2)
        self.assertEqual([(r.input, r.cache_read, r.output) for r in scan.records], [(200, 800, 100), (50, 200, 50)])
        first = scan.records[0]
        self.assertEqual((first.harness, first.model, first.session_id, first.branch, first.cache_write),
                         ("codex", "gpt-6-astra", "c1", "feat/x", 0))
        self.assertTrue(first.cwd.endswith("/.planning/worktrees/ep1"))
        self.assertNotIn(SECRET, repr(scan))

    def test_missing_root_and_env_root(self):
        self.assertEqual(codex_records(self.repo, Path(self.tmp.name) / "nope").status, "not_found")
        with mock.patch.dict(os.environ, {"CODEX_HOME": str(self.root.parent)}):
            self.assertEqual(len(codex_records(self.repo).records), 2)


if __name__ == "__main__":
    unittest.main()
