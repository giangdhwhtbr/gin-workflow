from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.manifests import ContextRequest, create_context_manifest  # noqa: E402
from workflow_core.approvals import (  # noqa: E402
    ApprovalAction,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
)
from workflow_core import schemas  # noqa: E402


class ContextManifestTests(unittest.TestCase):
    def test_redacts_secret_like_scalar_under_neutral_content_key(self):
        manifest = create_context_manifest(
            "implement",
            {"required": [{"name": "credential note", "content": "sk-secret"}]},
        )

        serialized = manifest.to_json()

        self.assertIn('"content": "[REDACTED]"', serialized)
        self.assertNotIn("sk-secret", serialized)

    def test_manifest_schema_requires_every_context_category(self):
        manifest = create_context_manifest("verify", {"required": []})
        self.assertEqual("2.3", manifest.to_dict()["schema_version"])
        schemas.validate_context_manifest(manifest.to_dict())
        invalid = manifest.to_dict()
        del invalid["categories"]["reference"]

        with self.assertRaises(ValueError):
            schemas.validate_context_manifest(invalid)

    def test_serializes_all_categories_without_copying_parent_context(self):
        request = ContextRequest(
            required=({"name": "requirement", "content": "implement core"},),
            conditional=({"name": "migration", "when": "legacy config exists"},),
            discoverable=({"name": "symbols", "query": "resolve_effective_config"},),
            reference=({"name": "plan", "path": ".planning/plans/core.md"},),
            prohibited=({"name": "parent transcript", "content": "must not leak"},),
            parent_context={"conversation": "copied parent context"},
        )

        manifest = create_context_manifest("implement", request)
        serialized = manifest.to_dict()

        self.assertEqual(
            {"required", "conditional", "discoverable", "reference", "prohibited"},
            set(serialized["categories"]),
        )
        self.assertEqual("implement core", serialized["categories"]["required"][0]["content"])
        self.assertTrue(serialized["categories"]["prohibited"][0]["redacted"])
        self.assertNotIn("must not leak", repr(serialized))
        self.assertNotIn("copied parent context", repr(serialized))

    def test_redacts_secrets_and_excludes_private_or_unrelated_context(self):
        request = {
            "required": [
                {
                    "name": "task",
                    "content": "bounded requirement",
                    "api_key": "sk-secret",
                    "private_reasoning": "hidden chain",
                    "history": ["unrelated old turn"],
                    "unrelated_tasks": ["other task"],
                    "nested": {"password": "literal-password"},
                }
            ],
            "conditional": [],
            "discoverable": [],
            "reference": [],
            "prohibited": [],
            "parent_context": {"secret": "parent secret"},
        }

        serialized = create_context_manifest("review", request).to_json()

        self.assertIn("[REDACTED]", serialized)
        self.assertNotIn("sk-secret", serialized)
        self.assertNotIn("hidden chain", serialized)
        self.assertNotIn("unrelated old turn", serialized)
        self.assertNotIn("other task", serialized)
        self.assertNotIn("literal-password", serialized)
        self.assertNotIn("parent secret", serialized)


class ApprovalModelTests(unittest.TestCase):
    def test_approval_request_and_decision_have_valid_portable_serialization(self):
        request = ApprovalRequest(
            request_id="approval-1",
            action=ApprovalAction.DISABLE_ISOLATION,
            workflow_id="wf-1",
            reason="legacy environment limitation",
            details={"workspace": "worker-1"},
        )
        decision = ApprovalDecision(
            request_id="approval-1",
            status=ApprovalStatus.APPROVED,
            decided_by="user-1",
            decided_at="2026-08-09T00:00:00Z",
        )

        schemas.validate_approval_request(request.to_dict())
        schemas.validate_approval_decision(decision.to_dict())
        self.assertTrue(decision.approved)
        with self.assertRaises(TypeError):
            request.details["workspace"] = "changed"


if __name__ == "__main__":
    unittest.main()
