"""`gin specs trace --all` joins the cases of the real gin-qa CLI."""

from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "plugins/gin-qa/src/scripts"))

from qa_fixtures import QA_LAUNCHER, TOOLS_PATH, case  # noqa: E402
from test_cases_cli import QaCase  # noqa: E402
from workflow_core import cli as gin_cli  # noqa: E402


@unittest.skipIf(os.name == "nt", "runs the gin-qa launcher through its #! line")
class TestTraceJoinsCases(QaCase):
    def test_a_pinned_case_shows_with_its_effective_result(self):
        self.write_cases(case("TC-AUTH-001", self.ref("REQ-AUTH-001")))
        search = os.pathsep.join([str(self.bin), str(QA_LAUNCHER.parent), TOOLS_PATH])
        out = io.StringIO()
        with mock.patch.dict(os.environ, {"PATH": search}), contextlib.redirect_stdout(out):
            code = gin_cli.main(["specs", "trace", "--all", "--repository", str(self.root), "--format", "json"])
        self.assertEqual(0, code)
        rows = {row["id"]: row for row in json.loads(out.getvalue())["requirements"]}
        self.assertEqual([{"id": "TC-AUTH-001", "effective_result": "not run"}], rows["REQ-AUTH-001"]["cases"])
        self.assertEqual([], rows["REQ-AUTH-002"]["cases"])
