import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest


SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core.bundles import BundleError, export_bundle, verify_bundle  # noqa: E402


class BundleTests(unittest.TestCase):
    def make_repository(self, root: Path) -> Path:
        workflow = root / ".agent-workflow"
        generated = workflow / "generated"
        generated.mkdir(parents=True)
        (generated / "effective-config.yaml").write_text(
            "schema_version: '2.1'\nreferences:\n  - docs/reference.md\n  - .agent-workflow/runtime/secret.txt\n  - docs/archive.zip\n",
            encoding="utf-8",
        )
        (generated / "config-provenance.yaml").write_text(
            "schema_version: '2.1'\nfields: {}\n",
            encoding="utf-8",
        )
        (root / "docs").mkdir()
        (root / "docs/reference.md").write_text("portable reference\n", encoding="utf-8")
        (root / "docs/archive.zip").write_bytes(b"not permitted")
        (workflow / "runtime").mkdir()
        (workflow / "runtime/secret.txt").write_text("runtime-secret\n", encoding="utf-8")
        return workflow

    def rewrite_integrity(self, output: Path, payload: dict) -> None:
        files = payload["files"]
        for entry in files.values():
            entry["sha256"] = hashlib.sha256(entry["content"].encode("utf-8")).hexdigest()
        canonical = json.dumps(files, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        payload["bundle_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        output.write_text(json.dumps(payload), encoding="utf-8")

    def test_bundle_contains_generated_files_and_safe_declared_references_only(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.make_repository(repository)
            output = repository / "workflow-bundle.json"

            result = export_bundle(repository, output)

            self.assertEqual("exported", result["status"])
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(
                [
                    ".agent-workflow/generated/config-provenance.yaml",
                    ".agent-workflow/generated/effective-config.yaml",
                    "docs/reference.md",
                ],
                sorted(payload["files"]),
            )
            serialized = output.read_text(encoding="utf-8")
            self.assertNotIn("runtime-secret", serialized)
            self.assertNotIn("not permitted", serialized)
            self.assertEqual("valid", verify_bundle(output)["status"])

    def test_bundle_verification_detects_hash_and_schema_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.make_repository(repository)
            output = repository / "workflow-bundle.json"
            export_bundle(repository, output)
            payload = json.loads(output.read_text(encoding="utf-8"))

            payload["files"]["docs/reference.md"]["content"] = "tampered\n"
            output.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(BundleError, "hash mismatch"):
                verify_bundle(output)

            payload["bundle_schema_version"] = "99"
            output.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(BundleError, "schema version"):
                verify_bundle(output)

    def test_verification_rejects_schema_invalid_embedded_generated_files_with_valid_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.make_repository(repository)
            output = repository / "workflow-bundle.json"
            export_bundle(repository, output)
            payload = json.loads(output.read_text(encoding="utf-8"))

            for relative, invalid_content in (
                (".agent-workflow/generated/effective-config.yaml", "schema_version: '99'\n"),
                (
                    ".agent-workflow/generated/config-provenance.yaml",
                    "schema_version: '99'\nfields: {}\n",
                ),
            ):
                with self.subTest(relative=relative):
                    current = json.loads(json.dumps(payload))
                    current["files"][relative]["content"] = invalid_content
                    self.rewrite_integrity(output, current)
                    with self.assertRaisesRegex(BundleError, "schema"):
                        verify_bundle(output)

    def test_export_rejects_literal_secret_without_writing_partial_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.make_repository(repository)
            reference = repository / "docs/reference.md"
            reference.write_text("api_key: sk-literal-value\n", encoding="utf-8")
            output = repository / "workflow-bundle.json"

            with self.assertRaisesRegex(BundleError, "literal secret"):
                export_bundle(repository, output)

            self.assertFalse(output.exists())

    def test_export_rejects_plain_credential_assignments_in_declared_references(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            self.make_repository(repository)
            reference = repository / "docs/reference.md"
            output = repository / "workflow-bundle.json"

            for credential in ("PASSWORD=hunter2\n", "AWS_SECRET_ACCESS_KEY=plainsecret\n"):
                with self.subTest(credential=credential):
                    reference.write_text(credential, encoding="utf-8")
                    with self.assertRaisesRegex(BundleError, "literal credential"):
                        export_bundle(repository, output)
                    self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
