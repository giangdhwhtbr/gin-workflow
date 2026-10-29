from pathlib import Path
import tempfile
import unittest

from tests.gin_orchestrator import paths  # noqa: F401

from workflow_core.assignments import (  # noqa: E402
    AssignmentManifest,
    AssignmentRequest,
    AssignmentResolutionError,
    RouteCandidate,
    write_assignment_manifest,
)
from workflow_core.models import EffectiveConfig  # noqa: E402
from workflow_core.provider_config import ProviderModelConfig  # noqa: E402
from gin_orchestrator.routes import (  # noqa: E402
    resolve_all_assignments,
    resolve_assignment,
)


def effective(repository: Path, extra: dict | None = None) -> EffectiveConfig:
    data = {
        "schema_version": "2.9",
        "harness": "claude",
        "routing": {
            "roles": {
                "backend": {
                    "preferred": ["claude", "claude"],
                    "fallback": ["main_harness", "codex"],
                }
            }
        },
    }
    if extra:
        data.update(extra)
    return EffectiveConfig(data, repository)


def local():
    return {
        "claude": ProviderModelConfig("claude", "claude"),
        "codex": ProviderModelConfig("codex", "codex"),
    }


class ProviderRoutesTests(unittest.TestCase):
    def test_routes_resolve_by_catalog_rank_across_harnesses(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = EffectiveConfig(
                {
                    "schema_version": "2.9",
                    "harness": "claude",
                    "models": {
                        "claude": {
                            "models": ["haiku", "sonnet", "opus"],
                            "efforts": ["low", "medium", "high", "xhigh", "max"],
                        },
                        "antigravity": {
                            "models": ["a1", "a2", "a3"],
                        },
                        "codex": {
                            "models": ["gpt-6-astra"],
                            "efforts": ["low", "medium", "high", "xhigh"],
                        },
                    },
                    "orchestrator": {
                        "roles": {
                            "backend": {
                                "preferred": ["claude"],
                                "by_tier": {
                                    "low": ["codex"],
                                    "medium": ["antigravity"],
                                    "high": ["codex"],
                                },
                            }
                        }
                    },
                },
                Path(directory),
            )
            local_map = {
                "claude": ProviderModelConfig("claude", "claude"),
                "antigravity": ProviderModelConfig("antigravity", "agy"),
                "codex": ProviderModelConfig("codex", "codex"),
            }
            # sonnet/medium track resolves to antigravity/a2/None
            sonnet_req = AssignmentRequest("t-sonnet", "backend", "sonnet", "medium", "claude", "wf-1")
            sonnet_routes = resolve_assignment(sonnet_req, cfg, local_map)
            self.assertEqual("antigravity", sonnet_routes[0].provider)
            self.assertEqual("a2", sonnet_routes[0].model)
            self.assertIsNone(sonnet_routes[0].effort)

            # a haiku track uses by_tier.low
            haiku_req = AssignmentRequest("t-haiku", "backend", "haiku", "low", "claude", "wf-1")
            haiku_routes = resolve_assignment(haiku_req, cfg, local_map)
            self.assertEqual("codex", haiku_routes[0].provider)

            # a codex target with opus/max gets xhigh
            opus_req = AssignmentRequest("t-opus", "backend", "opus", "max", "claude", "wf-1")
            opus_routes = resolve_assignment(opus_req, cfg, local_map)
            self.assertEqual("codex", opus_routes[0].provider)
            self.assertEqual("xhigh", opus_routes[0].effort)

    def test_batch_resolution_fails_before_any_manifest_write(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            cfg = EffectiveConfig(
                {
                    "schema_version": "2.9",
                    "harness": "claude",
                    "routing": {
                        "roles": {
                            "backend": {
                                "preferred": ["claude"],
                                "fallback": ["missing"],
                            }
                        }
                    },
                },
                repository,
            )
            requests = (
                AssignmentRequest("first", "backend", "opus", None, "claude", "wf-batch"),
                AssignmentRequest("second", "backend", "opus", None, "claude", "wf-batch"),
            )

            with self.assertRaisesRegex(
                AssignmentResolutionError, "missing local provider mapping: missing"
            ):
                resolve_all_assignments(requests, cfg, local())

            self.assertFalse(
                (repository / ".agent-workflow/runtime/assignments").exists()
            )

    def test_batch_resolution_reports_all_machine_local_errors_in_task_order(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            cfg = EffectiveConfig(
                {
                    "schema_version": "2.9",
                    "harness": "claude",
                    "routing": {
                        "roles": {
                            "role-a": {"preferred": ["missing-a", "codex"]},
                            "role-b": {"preferred": ["missing-b", "codex"]},
                        }
                    },
                },
                repository,
            )
            requests = (
                AssignmentRequest("first", "role-a", "opus", None, "claude", "wf-batch"),
                AssignmentRequest("second", "role-b", "opus", None, "claude", "wf-batch"),
            )
            only_claude = {"claude": local()["claude"]}

            with self.assertRaises(AssignmentResolutionError) as caught:
                resolve_all_assignments(
                    requests, cfg, only_claude
                )

        message = str(caught.exception)
        self.assertLess(message.index("first"), message.index("second"))
        self.assertIn("missing local provider mapping: missing-a", message)
        self.assertIn("missing local provider mapping: missing-b", message)
        self.assertIn("missing local provider mapping: codex", message)

    def test_public_assignment_boundaries_reject_non_antigravity_provider_default(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            cfg = EffectiveConfig(
                {
                    "schema_version": "2.9",
                    "harness": "claude",
                    "models": {
                        "claude": {"models": ["haiku", "sonnet", "opus"]},
                        "codex": {"models": ["provider_default"]},
                    },
                    "routing": {
                        "roles": {
                            "backend": {"preferred": ["codex"]},
                        }
                    },
                },
                repository,
            )
            request = AssignmentRequest(
                "api", "backend", "opus", None, "claude", "wf-batch"
            )

            with self.assertRaisesRegex(
                AssignmentResolutionError,
                "provider_default is only supported for antigravity and opencode",
            ):
                resolve_assignment(request, cfg, local())
            with self.assertRaisesRegex(
                AssignmentResolutionError,
                "provider_default is only supported for antigravity and opencode",
            ):
                resolve_all_assignments((request,), cfg, local())
            with self.assertRaisesRegex(
                AssignmentResolutionError,
                "provider_default is only supported for antigravity and opencode",
            ):
                RouteCandidate("codex", "provider_default", False)

    def test_batch_resolution_returns_manifests_only_after_every_route_resolves(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            requests = (
                AssignmentRequest("first", "backend", "opus", None, "claude", "wf-batch"),
                AssignmentRequest("second", "backend", "sonnet", None, "claude", "wf-batch"),
            )

            manifests = resolve_all_assignments(
                requests, effective(repository), local()
            )

        self.assertEqual(("first", "second"), tuple(item.request.task_id for item in manifests))
        self.assertEqual(("wf-batch", "wf-batch"), tuple(item.workflow_id for item in manifests))

    def test_resolver_expands_main_harness_deduplicates_and_preserves_same_tier(self):
        with tempfile.TemporaryDirectory() as directory:
            routes = resolve_assignment(
                AssignmentRequest("api", "backend", "opus", None, "claude"),
                effective(Path(directory)),
                local(),
            )

        self.assertEqual(
            (("claude", "opus", False), ("codex", "gpt-6-astra", True)),
            tuple((route.provider, route.model, route.fallback) for route in routes),
        )

    def test_resolver_by_tier_replaces_preferred_for_that_tier_only(self):
        with tempfile.TemporaryDirectory() as directory:
            role = {"preferred": ["claude"], "by_tier": {"low": ["codex"]}}
            config = EffectiveConfig({"harness": "claude", "routing": {"roles": {"backend": role}}}, Path(directory))
            low = resolve_assignment(AssignmentRequest("api", "backend", "haiku", None, "claude"), config, local())
            high = resolve_assignment(AssignmentRequest("api", "backend", "opus", None, "claude"), config, local())

        self.assertEqual(
            (("codex", "gpt-6-astra", False),),
            tuple((route.provider, route.model, route.fallback) for route in low),
        )
        self.assertEqual("claude", high[0].provider)

    def test_resolver_rejects_missing_role_provider_mapping_and_invalid_tier(self):
        with tempfile.TemporaryDirectory() as directory:
            config = effective(Path(directory))
            with self.assertRaisesRegex(AssignmentResolutionError, "unknown provider role"):
                resolve_assignment(AssignmentRequest("api", "frontend", "opus", None, "claude"), config, local())
            with self.assertRaisesRegex(AssignmentResolutionError, "missing local provider mapping"):
                resolve_assignment(AssignmentRequest("api", "backend", "opus", None, "claude"), config, {"codex": local()["codex"]})
            with self.assertRaises(Exception):
                resolve_assignment(AssignmentRequest("api", "backend", "extreme", None, "claude"), config, local())

    def test_manifest_is_immutable_deterministic_and_written_under_runtime_only(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            request = AssignmentRequest("api-auth", "backend", "opus", "high", "claude")
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
            self.assertIn(b"model: opus", content)
            with self.assertRaises((AttributeError, TypeError)):
                manifest.candidates[0].provider = "changed"

            other_request = AssignmentRequest("ui", "backend", "sonnet", "medium", "claude")
            other = AssignmentManifest(
                "wf-1",
                other_request,
                resolve_assignment(other_request, effective(repository), local()),
            )
            write_assignment_manifest(repository, other)
            loaded = __import__("yaml").safe_load(first.read_text(encoding="utf-8"))
            self.assertEqual(
                ["api-auth", "ui"],
                [assignment["task_id"] for assignment in loaded["assignments"]],
            )

    def test_resolve_assignment_treats_main_harness_without_local_mapping_as_default_model(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            cfg = EffectiveConfig(
                {
                    "schema_version": "2.9",
                    "harness": "claude",
                    "provider_mode": "single",
                    "routing": {
                        "roles": {
                            "backend": {
                                "preferred": ["main_harness"],
                            }
                        }
                    },
                },
                repository,
            )
            for harness, model, effort in (
                ("claude", "sonnet", "medium"),
                ("antigravity", "provider_default", None),
                ("opencode", "provider_default", None),
                ("codex", "gpt-6-astra", "medium"),
            ):
                with self.subTest(harness=harness):
                    request = AssignmentRequest("task-1", "backend", model, effort, harness, "wf-1")
                    candidates = resolve_assignment(request, cfg, {})
                    self.assertEqual(1, len(candidates))
                    self.assertEqual(harness, candidates[0].provider)
                    self.assertEqual(model, candidates[0].model)
                    self.assertEqual(effort, candidates[0].effort)

    def test_resolve_assignment_falls_back_to_harness_default_even_when_other_providers_present(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            cfg = EffectiveConfig(
                {
                    "schema_version": "2.9",
                    "harness": "claude",
                    "provider_mode": "single",
                    "routing": {
                        "roles": {
                            "backend": {
                                "preferred": ["main_harness"],
                            }
                        }
                    },
                },
                repository,
            )
            # local has opencode configured, but NOT claude
            other_local = {
                "opencode": ProviderModelConfig(
                    provider="opencode",
                    executable="opencode",
                )
            }
            request = AssignmentRequest("task-1", "backend", "sonnet", None, "claude", "wf-1")
            candidates = resolve_assignment(request, cfg, other_local)
            self.assertEqual(1, len(candidates))
            self.assertEqual("claude", candidates[0].provider)
            self.assertEqual("sonnet", candidates[0].model)


if __name__ == "__main__":
    unittest.main()
