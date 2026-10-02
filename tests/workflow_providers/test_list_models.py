"""Provider model listing from native CLIs with safe fallback."""

from __future__ import annotations

import json
import subprocess
import unittest

from workflow_providers.native_cli import list_models

CODEX_JSON = json.dumps({"models": [
    {"slug": "gpt-6-sol", "display_name": "GPT-6 Sol", "description": "frontier", "visibility": "list",
     "supported_reasoning_levels": [{"effort": "low"}, {"effort": "high"}]},
    {"slug": "internal", "display_name": "x", "visibility": "hide"}]})
AGY_TEXT = "Fetching available models...\ngemini-3.8-flash-high\tGemini 3.8 Flash (High)\nclaude-opus-4-6-thinking\tClaude Opus 4.6 (Thinking)\n"


def runner_for(stdout, code=0):
    return lambda argv: subprocess.CompletedProcess(argv, code, stdout, "")


FOUND = lambda name: f"/bin/{name}"  # noqa: E731


class TestListModels(unittest.TestCase):
    def test_codex_json_keeps_listed_models(self):
        models = list_models("codex", runner=runner_for(CODEX_JSON), which=FOUND)
        self.assertEqual([{"id": "gpt-6-sol", "label": "GPT-6 Sol", "description": "frontier",
                           "reasoning_levels": ["low", "high"]}], models)

    def test_agy_text_parses_ids_and_suffix_levels(self):
        models = list_models("antigravity", runner=runner_for(AGY_TEXT), which=FOUND)
        self.assertEqual(["gemini-3.8-flash-high", "claude-opus-4-6-thinking"], [m["id"] for m in models])
        self.assertEqual(["high"], models[0]["reasoning_levels"])
        self.assertEqual([], models[1]["reasoning_levels"])

    def test_claude_returns_aliases_without_running_cli(self):
        def fail(argv):
            raise AssertionError("claude has no list command")
        self.assertEqual(["opus", "sonnet", "haiku"], [m["id"] for m in list_models("claude", runner=fail, which=FOUND)])

    def test_failures_and_unknown_providers_return_empty(self):
        self.assertEqual([], list_models("codex", runner=runner_for("not json"), which=FOUND))
        self.assertEqual([], list_models("codex", runner=runner_for(CODEX_JSON, code=1), which=FOUND))
        self.assertEqual([], list_models("antigravity", runner=runner_for(AGY_TEXT), which=lambda name: None))
        self.assertEqual([], list_models("other", runner=runner_for(""), which=FOUND))
