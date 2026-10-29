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
    resolve_main_harness,
    validate_plan_assignments,
    write_assignments,
)
from workflow_core.models import EffectiveConfig  # noqa: E402


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
        # Track beads are created before routes resolve, so the routes file is keyed by their real ids
        self.assertLess(
            orchestrate.index("gin-workflow task create"),
            orchestrate.index("routes resolve"),
        )

    def test_parent_deliverable_vs_track_bead_and_handoff_contracts(self):
        plugin = SCRIPTS.parent
        orchestrate = (plugin / "skills/orchestrate/SKILL.md").read_text(encoding="utf-8")
        planning = (plugin / "skills/plan/SKILL.md").read_text(encoding="utf-8")
        execute = (plugin / "skills/execute/SKILL.md").read_text(encoding="utf-8")

        # Parent Bead vs Track Bead separation
        self.assertIn("Parent Bead (Deliverable", orchestrate)
        self.assertIn("Track Beads (Work Units", orchestrate)
        self.assertIn("remain open until human-confirmed merge", orchestrate)
        self.assertIn("Distinguish Parent Bead (Deliverable) vs Track Beads (Work Units)", orchestrate)
        self.assertIn("Distinguish the Parent Bead", planning)

        # Handoff contracts and PR merge claim prohibition live in the execute skill
        self.assertIn("waiting for PR merge", execute)
        self.assertIn("Xin lệnh tạo PR từ nhánh feature đã push", execute)
        self.assertIn("Giữ nhánh feature đã push", execute)

        # Routed tracks dispatch to their provider; orchestrate hands off a /goal
        self.assertIn("provider other than the main harness", execute)
        self.assertIn("/goal", orchestrate)

    def test_plan_validation_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = effective(Path(directory))
            errors = validate_plan_assignments(
                (
                    {"task_id": "first", "provider_role": "frontend", "model": "haiku", "effort": "low"},
                    {"task_id": "second", "provider_role": "backend", "model": "unknown_model", "effort": "low"},
                    {"task_id": "third", "provider_role": "backend", "model": "sonnet", "effort": "bad_effort"},
                    {"task_id": "fourth", "provider_role": "backend", "reasoning": "high"},
                ),
                cfg,
            )

        self.assertIn("track first: unknown provider role: frontend", errors)
        self.assertTrue(any("track second: model 'unknown_model' is not in the catalog" in e for e in errors), errors)
        self.assertTrue(any("track third: effort 'bad_effort' is not in the catalog" in e for e in errors), errors)
        self.assertIn("track fourth: reasoning is replaced by model and effort", errors)

    def test_plan_validation_effort_on_antigravity_is_diagnostic(self):
        cfg = EffectiveConfig(
            {
                "schema_version": "2.9",
                "harness": "antigravity",
                "routing": {"roles": {"backend": {}}},
            },
            Path("/tmp"),
        )
        errors = validate_plan_assignments(
            [{"task_id": "t1", "provider_role": "backend", "model": "provider_default", "effort": "low"}],
            cfg,
        )
        self.assertEqual(
            ["track t1: effort 'low' given, but the catalog lists no efforts"],
            errors,
        )

    def test_route_candidate_accepts_high_effort_for_claude(self):
        candidate = RouteCandidate("claude", "sonnet", False, effort="high")
        self.assertEqual("claude", candidate.provider)
        self.assertEqual("sonnet", candidate.model)
        self.assertEqual("high", candidate.effort)

    def test_opencode_accepts_provider_default_and_records_selection_mode(self):
        candidate = RouteCandidate("opencode", "provider_default", False)
        payload = AssignmentManifest(
            "wf-default", AssignmentRequest("api", "backend", "provider_default", None, "opencode"), (candidate,)
        ).to_dict()

        self.assertEqual(
            {"provider": "opencode", "selection_mode": "provider_default"}, payload["resolved"]
        )

    def test_provider_default_manifest_records_selection_mode_without_claiming_model(self):
        request = AssignmentRequest("api", "backend", "provider_default", None, "antigravity")
        payload = AssignmentManifest(
            "wf-default",
            request,
            (RouteCandidate("antigravity", "provider_default", False),),
        ).to_dict()

        self.assertEqual(
            {"provider": "antigravity", "selection_mode": "provider_default"},
            payload["resolved"],
        )

    def test_resolve_main_harness_uses_the_requested_model_and_effort(self):
        req_claude = AssignmentRequest("t1", "backend", "sonnet", "medium", "claude", "wf-1")
        routes_claude = resolve_main_harness(req_claude)
        self.assertEqual(
            (("claude", "sonnet", False, "medium"),),
            tuple((r.provider, r.model, r.fallback, r.effort) for r in routes_claude),
        )

        req_codex = AssignmentRequest("t2", "backend", "gpt-6-astra", "high", "codex", "wf-1")
        routes_codex = resolve_main_harness(req_codex)
        self.assertEqual(
            (("codex", "gpt-6-astra", False, "high"),),
            tuple((r.provider, r.model, r.fallback, r.effort) for r in routes_codex),
        )

    def test_resolve_main_harness_rejects_an_unknown_harness(self):
        req = AssignmentRequest("t1", "backend", "sonnet", "medium", "unknown-harness", "wf-1")
        with self.assertRaisesRegex(AssignmentResolutionError, "unknown main harness: unknown-harness"):
            resolve_main_harness(req)

    def test_write_assignments_merges_by_task_id(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            entry2 = {"task_id": "t2", "resolved": {"provider": "claude"}}
            entry1 = {"task_id": "t1", "resolved": {"provider": "claude", "model": "sonnet"}}
            path = write_assignments(repository, "wf-merge", [entry2])
            write_assignments(repository, "wf-merge", [entry1])

            import yaml
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(data["workflow_id"], "wf-merge")
            self.assertEqual([a["task_id"] for a in data["assignments"]], ["t1", "t2"])

            entry1_updated = {"task_id": "t1", "resolved": {"provider": "claude", "model": "opus"}}
            write_assignments(repository, "wf-merge", [entry1_updated])
            data2 = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual([a["task_id"] for a in data2["assignments"]], ["t1", "t2"])
            self.assertEqual(data2["assignments"][0]["resolved"]["model"], "opus")


if __name__ == "__main__":
    unittest.main()
