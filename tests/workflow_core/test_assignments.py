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
    RouteCandidate,
    resolve_all_assignments,
    resolve_assignment,
    validate_plan_assignments,
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
        schema = (plugin / "skills/plan/plan-schema.md").read_text(encoding="utf-8")
        planning = (plugin / "skills/plan/SKILL.md").read_text(encoding="utf-8")
        orchestrate = (plugin / "skills/orchestrate/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("**Provider role**: `backend`", schema)
        self.assertIn("**Reasoning**: `low` | `medium` | `high`", schema)
        self.assertIn("complex architecture, security, migration, or concurrency", schema)
        self.assertIn("Do not name a concrete provider or model", planning)
        self.assertIn("provider role and reasoning", planning)
        self.assertIn("every track has a configured role and low/medium/high reasoning", planning)
        self.assertLess(
            orchestrate.index("resolve_all_assignments"),
            orchestrate.index("bd create"),
        )

    def test_parent_deliverable_vs_track_bead_and_handoff_contracts(self):
        plugin = SCRIPTS.parent
        root = SCRIPTS.parents[3]
        orchestrate = (plugin / "skills/orchestrate/SKILL.md").read_text(encoding="utf-8")
        planning = (plugin / "skills/plan/SKILL.md").read_text(encoding="utf-8")
        handoff_doc = (root / "docs/verification-and-handoff-workflow.md").read_text(encoding="utf-8")
        handoff_ref = (plugin / "references/verification-and-handoff-workflow.md").read_text(encoding="utf-8")
        execute = (plugin / "skills/execute/SKILL.md").read_text(encoding="utf-8")

        # Parent Bead vs Track Bead separation
        self.assertIn("Parent Bead (Deliverable", orchestrate)
        self.assertIn("Track Beads (Work Units", orchestrate)
        self.assertIn("remain open until human-confirmed merge", orchestrate)
        self.assertIn("Distinguish Parent Bead (Deliverable) vs Track Beads (Work Units)", orchestrate)
        self.assertIn("Distinguish the Parent Bead", planning)

        # Handoff contracts and PR merge claim prohibition
        self.assertEqual(handoff_doc, handoff_ref)
        self.assertIn("waiting for PR merge", handoff_doc)
        self.assertIn("Strict Prohibition on \"Waiting for PR Merge\"", handoff_doc)
        self.assertIn("Xin lệnh tạo PR từ nhánh feature đã push", handoff_doc)
        self.assertIn("Giữ nhánh feature đã push", handoff_doc)
        self.assertIn("Xin lệnh tạo PR từ nhánh feature đã push", execute)

    def test_plan_validation_reports_every_role_and_tier_error_in_task_order(self):
        with tempfile.TemporaryDirectory() as directory:
            errors = validate_plan_assignments(
                (
                    {"task_id": "first", "provider_role": "frontend", "reasoning": "extreme"},
                    {"task_id": "second", "provider_role": "backend", "reasoning": "unknown"},
                    {"task_id": "third", "provider_role": "devops", "reasoning": "high"},
                ),
                effective(Path(directory)),
            )

        self.assertEqual(
            (
                ("first", "provider_role", "unknown provider role: frontend"),
                ("first", "reasoning", "reasoning must be one of: low, medium, high"),
                ("second", "reasoning", "reasoning must be one of: low, medium, high"),
                ("third", "provider_role", "unknown provider role: devops"),
            ),
            tuple((error.task_id, error.field, error.message) for error in errors),
        )

    def test_batch_resolution_fails_before_any_manifest_write(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            requests = (
                AssignmentRequest("first", "backend", "high", "codex", "wf-batch"),
                AssignmentRequest("second", "backend", "high", "missing", "wf-batch"),
            )

            with self.assertRaisesRegex(
                AssignmentResolutionError, "missing local provider mapping: missing"
            ):
                resolve_all_assignments(requests, effective(repository), local())

            self.assertFalse(
                (repository / ".agent-workflow/runtime/assignments").exists()
            )

    def test_batch_resolution_reports_all_machine_local_errors_in_task_order(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            requests = (
                AssignmentRequest("first", "backend", "high", "missing-a", "wf-batch"),
                AssignmentRequest("second", "backend", "high", "missing-b", "wf-batch"),
            )
            only_claude = {"claude": local()["claude"]}

            with self.assertRaises(AssignmentResolutionError) as caught:
                resolve_all_assignments(
                    requests, effective(repository), only_claude
                )

        message = str(caught.exception)
        self.assertLess(message.index("first"), message.index("second"))
        self.assertIn("missing local provider mapping: missing-a", message)
        self.assertIn("missing local provider mapping: missing-b", message)
        self.assertIn("missing local provider mapping: codex", message)

    def test_public_assignment_boundaries_reject_non_antigravity_provider_default(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            codex_default = {
                **local(),
                "codex": ProviderModelConfig(
                    "codex", "codex", {
                        "low": "provider_default",
                        "medium": "provider_default",
                        "high": "provider_default",
                    }
                ),
            }
            request = AssignmentRequest(
                "api", "backend", "high", "codex", "wf-batch"
            )

            with self.assertRaisesRegex(
                AssignmentResolutionError,
                "provider_default is only supported for antigravity",
            ):
                resolve_assignment(request, effective(repository), codex_default)
            with self.assertRaisesRegex(
                AssignmentResolutionError,
                "provider_default is only supported for antigravity",
            ):
                resolve_all_assignments(
                    (request,), effective(repository), codex_default
                )
            with self.assertRaisesRegex(
                AssignmentResolutionError,
                "provider_default is only supported for antigravity",
            ):
                RouteCandidate("codex", "provider_default", False)

    def test_batch_resolution_returns_manifests_only_after_every_route_resolves(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            requests = (
                AssignmentRequest("first", "backend", "high", "codex", "wf-batch"),
                AssignmentRequest("second", "backend", "medium", "codex", "wf-batch"),
            )

            manifests = resolve_all_assignments(
                requests, effective(repository), local()
            )

        self.assertEqual(("first", "second"), tuple(item.request.task_id for item in manifests))
        self.assertEqual(("wf-batch", "wf-batch"), tuple(item.workflow_id for item in manifests))

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

            other_request = AssignmentRequest("ui", "backend", "medium", "codex")
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

    def test_provider_default_manifest_records_selection_mode_without_claiming_model(self):
        request = AssignmentRequest("api", "backend", "high", "codex")
        payload = AssignmentManifest(
            "wf-default",
            request,
            (RouteCandidate("antigravity", "provider_default", False),),
        ).to_dict()

        self.assertEqual(
            {"provider": "antigravity", "selection_mode": "provider_default"},
            payload["resolved"],
        )


if __name__ == "__main__":
    unittest.main()
