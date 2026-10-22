from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.ext import (  # noqa: E402
    AssignmentRequest,
    EffectiveConfig,
    ProviderModelConfig,
    TierModelTarget,
)
from workflow_core.migrations import migrate_config  # noqa: E402
from workflow_providers.config import (  # noqa: E402
    orchestrator_section,
    roles,
    validate_orchestrator_config,
)
from workflow_providers.routes import resolve_assignment  # noqa: E402


class OrchestratorConfigTests(unittest.TestCase):
    def test_roles_prefer_orchestrator_entries(self):
        config = {
            "routing": {
                "roles": {
                    "backend": {"preferred": ["claude"]},
                    "frontend": {"preferred": ["claude"]},
                }
            },
            "orchestrator": {
                "roles": {
                    "backend": {"preferred": ["codex"]},
                }
            },
        }
        all_roles = roles(config)
        self.assertEqual(all_roles["backend"]["preferred"], ["codex"])
        self.assertEqual(all_roles["frontend"]["preferred"], ["claude"])

    def test_defaults_fill_missing_policy(self):
        config = {
            "orchestrator": {
                "concurrency": {"claude": 2},
                "circuit_breaker": {"failure_threshold": 5},
            }
        }
        section = orchestrator_section(config)
        self.assertEqual(section["concurrency"], {"claude": 2})
        self.assertEqual(section["circuit_breaker"]["failure_threshold"], 5)
        self.assertEqual(section["queue"], {"max_wait_seconds": 600})
        self.assertEqual(section["worker"], {"max_retries": 2})

    def test_validation_reports_unknown_provider_and_bad_tier(self):
        config = {
            "harness": "claude",
            "orchestrator": {
                "concurrency": {"claude": 2},
                "roles": {
                    "backend": {
                        "preferred": ["main_harness"],
                        "by_tier": {
                            "extreme": ["codex"],
                        },
                    }
                },
            },
        }
        with self.assertRaises(ValueError) as ctx:
            validate_orchestrator_config(config)
        err = str(ctx.exception)
        self.assertIn("extreme", err)
        self.assertIn("codex", err)

    def test_validation_reports_malformed_role_lists_as_value_errors(self):
        config = {
            "harness": "claude",
            "orchestrator": {
                "concurrency": {"codex": 1},
                "roles": {
                    "backend": {"preferred": "codex"},
                    "review": {"preferred": ["codex"], "by_tier": ["codex"]},
                },
            },
        }
        with self.assertRaises(ValueError) as ctx:
            validate_orchestrator_config(config)
        self.assertNotIn("unknown provider 'c'", str(ctx.exception))

    def test_routes_resolve_from_the_orchestrator_section(self):
        legacy = {
            "schema_version": "2.7",
            "workflow_version": "2.7",
            "setup_cli_version": "2.7",
            "harness": "claude",
            "routing": {
                "concurrency": {"claude": 2, "codex": 1},
                "queue": {"max_wait_seconds": 600},
                "worker": {"max_retries": 2},
                "circuit_breaker": {"failure_threshold": 3},
                "review": {"max_cycles": 3, "role": "review"},
                "roles": {
                    "backend": {
                        "preferred": ["main_harness"],
                        "by_tier": {"high": ["codex"]},
                        "fallback": ["main_harness"],
                    },
                    "review": {"preferred": ["main_harness"]},
                },
            },
        }
        migrated = migrate_config(legacy, "2.8")
        effective = EffectiveConfig(migrated, Path("."))
        local = {
            "claude": ProviderModelConfig(
                "claude",
                "claude",
                {"low": "haiku", "medium": "sonnet", "high": "opus"},
            ),
            "codex": ProviderModelConfig(
                "codex",
                "codex",
                {
                    "low": TierModelTarget("gpt-6-astra", "low"),
                    "medium": TierModelTarget("gpt-6-astra", "medium"),
                    "high": TierModelTarget("gpt-6-astra", "high"),
                },
            ),
        }
        request = AssignmentRequest(
            task_id="t1",
            provider_role="backend",
            reasoning="high",
            main_harness="claude",
            workflow_id="wf-1",
        )
        candidates = resolve_assignment(request, effective, local)
        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0].provider, "codex")
        self.assertFalse(candidates[0].fallback)
        self.assertEqual(candidates[1].provider, "claude")
        self.assertTrue(candidates[1].fallback)


if __name__ == "__main__":
    unittest.main()
