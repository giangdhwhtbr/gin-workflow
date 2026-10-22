"""`workflow_core` reaches the worker library only through the orchestrator CLI contract."""

from pathlib import Path
import re
import unittest

SRC = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src"
CORE = SRC / "scripts/workflow_core"
PROVIDERS = SRC / "scripts/workflow_providers"


class TestImportBoundary(unittest.TestCase):
    def test_workflow_core_does_not_import_workflow_providers(self):
        offenders = []
        for path in sorted(CORE.rglob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if re.match(r"^\s*(from|import)\s+(workflow_providers|gin_orchestrator)\b", line):
                    offenders.append(f"{path.relative_to(SRC)}:{number}")
        self.assertEqual([], offenders)

    def test_worker_library_imports_only_the_facade(self):
        offenders = []
        for path in sorted(PROVIDERS.glob("*.py")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                match = re.match(r"^\s*(from|import)\s+(workflow_core(?:\.\w+)?)\b", line)
                if match and match.group(2) != "workflow_core.ext":
                    offenders.append(f"{path.relative_to(SRC)}:{number}")
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
