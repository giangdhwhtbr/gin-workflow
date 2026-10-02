"""Benchmark usage summarizer over a recorded Claude Code transcript."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("summarize_usage", ROOT / "scripts/benchmark/summarize_usage.py")
summarize_usage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summarize_usage)


class TestSummarizeUsage(unittest.TestCase):
    def test_sums_usage_tool_calls_and_wall_time(self):
        result = summarize_usage.summarize(ROOT / "tests/fixtures/benchmark/session-a.jsonl")
        self.assertEqual({"input_tokens": 130, "output_tokens": 25, "cache_creation_input_tokens": 50,
                          "cache_read_input_tokens": 40, "tool_calls": 1, "wall_seconds": 100.0}, result)

    def test_table_has_one_row_per_label(self):
        table = summarize_usage.table({"gin-easy": ROOT / "tests/fixtures/benchmark/session-a.jsonl"})
        self.assertIn("| gin-easy | 130 | 25 | 50 | 40 | 1 | 100 |", table)
