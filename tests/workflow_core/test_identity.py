from dataclasses import replace
from pathlib import Path
import sys
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.identity import AcceptanceIdentity, RepositorySnapshot  # noqa: E402


class AcceptanceIdentityTests(unittest.TestCase):
    def snapshot(self, repository_id: str = "primary") -> RepositorySnapshot:
        return RepositorySnapshot(
            repository_id=repository_id,
            source_scope_hash=f"scope-{repository_id}",
            source_tree_hash=f"tree-{repository_id}",
            checkpoint_sha=f"commit-{repository_id}",
            checkpoint_ref=f"refs/gin/review/{repository_id}",
        )

    def identity(self) -> AcceptanceIdentity:
        return AcceptanceIdentity(
            workflow_id="workflow-1",
            attempt_id="attempt-1",
            task_id="task-1",
            repositories=(self.snapshot(),),
        )

    def test_rejects_blank_identity_and_repository_fields(self):
        for field_name in ("workflow_id", "attempt_id", "task_id"):
            with self.subTest(field=field_name), self.assertRaisesRegex(
                ValueError, f"{field_name} is required"
            ):
                replace(self.identity(), **{field_name: "  "})

        for field_name in (
            "repository_id",
            "source_scope_hash",
            "source_tree_hash",
            "checkpoint_sha",
            "checkpoint_ref",
        ):
            with self.subTest(field=field_name), self.assertRaisesRegex(
                ValueError, f"{field_name} is required"
            ):
                replace(self.snapshot(), **{field_name: ""})

        with self.assertRaisesRegex(ValueError, "repositories must not be empty"):
            replace(self.identity(), repositories=())

    def test_rejects_duplicate_repository_ids(self):
        with self.assertRaisesRegex(ValueError, "duplicate repository_id: primary"):
            replace(self.identity(), repositories=(self.snapshot(), self.snapshot()))

    def test_serializes_repositories_in_deterministic_id_order(self):
        identity = replace(
            self.identity(),
            repositories=(self.snapshot("zeta"), self.snapshot("alpha")),
        )

        self.assertEqual(("alpha", "zeta"), tuple(x.repository_id for x in identity.repositories))
        self.assertEqual(
            ["alpha", "zeta"],
            [item["repository_id"] for item in identity.to_dict()["repositories"]],
        )

    def test_round_trips_losslessly_through_portable_mapping(self):
        original = replace(
            self.identity(),
            repositories=(self.snapshot("secondary"), self.snapshot("primary")),
        )

        restored = AcceptanceIdentity.from_mapping(original.to_dict())

        self.assertEqual(original, restored)
        self.assertEqual(original.to_dict(), restored.to_dict())

    def test_exact_match_checks_every_top_level_and_repository_field(self):
        original = self.identity()
        for field_name in ("workflow_id", "attempt_id", "task_id"):
            changed = replace(original, **{field_name: f"different-{field_name}"})
            with self.subTest(field=field_name), self.assertRaisesRegex(
                ValueError, f"acceptance identity mismatch: {field_name}"
            ):
                original.require_exact_match(changed)

        for field_name in (
            "repository_id",
            "source_scope_hash",
            "source_tree_hash",
            "checkpoint_sha",
            "checkpoint_ref",
        ):
            changed_snapshot = replace(
                original.repositories[0], **{field_name: f"different-{field_name}"}
            )
            changed = replace(original, repositories=(changed_snapshot,))
            with self.subTest(field=field_name), self.assertRaisesRegex(
                ValueError, "acceptance identity mismatch: repositories"
            ):
                original.require_exact_match(changed)

        original.require_exact_match(AcceptanceIdentity.from_mapping(original.to_dict()))


if __name__ == "__main__":
    unittest.main()
