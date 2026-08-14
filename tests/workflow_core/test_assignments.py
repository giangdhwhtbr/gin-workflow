from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.assignments import (  # noqa: E402
    AssignmentManifest,
    AssignmentRequest,
    AssignmentResolutionError,
    resolve_assignment,
    write_assignment_manifest,
)
from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.provider_config import ProviderModelConfig  # noqa: E402


def effective(repository: Path) -> EffectiveConfig:
    return EffectiveConfig(
        {
            "schema_version": "2.2",
            "harness": "codex",
            "routing": {
                "roles": {
                    "backend": {
                        "preferred": ["claude", "claude"],
                        "fallback": ["main_harness", "codex"],
                    }
                }
            },
        },
        repository,
    )


def local():
    return {
        "claude": ProviderModelConfig(
            "claude",
            "claude",
            {"low": "haiku", "medium": "sonnet", "high": "opus"},
        ),
        "codex": ProviderModelConfig(
            "codex",
            "codex",
            {"low": "mini", "medium": "coding", "high": "reasoning"},
        ),
    }


class AssignmentTests(unittest.TestCase):
    def test_planning_and_orchestration_contracts_require_portable_route_guidance(self):
        plugin = SCRIPTS.parent
        schema = (plugin / "skills/writing-plans/plan-schema.md").read_text(encoding="utf-8")
        writing = (plugin / "skills/writing-plans/SKILL.md").read_text(encoding="utf-8")
        planning = (plugin / "skills/plan/SKILL.md").read_text(encoding="utf-8")
        orchestrate = (plugin / "skills/orchestrate/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("**Provider role**: `backend`", schema)
        self.assertIn("**Reasoning**: `low` | `medium` | `high`", schema)
        self.assertIn("complex architecture, security, migration, or concurrency", schema)
        self.assertIn("Do not name a concrete provider or model", writing)
        self.assertIn("provider role and reasoning", planning)
        self.assertIn("write_assignment_manifest", orchestrate)

    def test_resolver_expands_main_harness_deduplicates_and_preserves_same_tier(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = resolve_assignment(
                AssignmentRequest("api", "backend", "high", "codex"),
                effective(Path(directory)),
                local(),
            )

        self.assertEqual(
            (("claude", "opus", False), ("codex", "reasoning", True)),
            tuple((route.provider, route.model, route.fallback) for route in routes),
        )

    def test_resolver_rejects_missing_role_provider_mapping_and_invalid_tier(self):
        with tempfile.TemporaryDirectory() as directory:
            config = effective(Path(directory))
            with self.assertRaisesRegex(AssignmentResolutionError, "unknown provider role"):
                resolve_assignment(AssignmentRequest("api", "frontend", "high", "codex"), config, local())
            with self.assertRaisesRegex(AssignmentResolutionError, "missing local provider mapping"):
                resolve_assignment(AssignmentRequest("api", "backend", "high", "codex"), config, {"claude": local()["claude"]})
            with self.assertRaisesRegex(AssignmentResolutionError, "reasoning"):
                resolve_assignment(AssignmentRequest("api", "backend", "extreme", "codex"), config, local())

    def test_manifest_is_immutable_deterministic_and_written_under_runtime_only(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            request = AssignmentRequest("api-auth", "backend", "high", "codex")
            routes = resolve_assignment(request, effective(repository), local())
            manifest = AssignmentManifest("wf-1", request, routes)

            first = write_assignment_manifest(repository, manifest)
            content = first.read_bytes()
            second = write_assignment_manifest(repository, manifest)

            self.assertEqual(
                repository / ".agent-workflow/runtime/assignments/wf-1.yaml",
                first,
            )
            self.assertEqual(content, second.read_bytes())
            self.assertIn(b"provider_role: backend", content)
            self.assertIn(b"provider: claude", content)
            self.assertIn(b"model: reasoning", content)
            with self.assertRaises((AttributeError, TypeError)):
                manifest.candidates[0].provider = "changed"


if __name__ == "__main__":
    unittest.main()
