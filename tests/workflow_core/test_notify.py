from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import urllib.parse
import urllib.request

SCRIPTS = Path(__file__).resolve().parents[2] / "plugins/gin-workflow/src/scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_core import notify
from workflow_core.setup_service import refresh


class _FakeResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class TestNotify(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.cfg_dir = self.root / ".agent-workflow"
        self.cfg_dir.mkdir(parents=True, exist_ok=True)
        config_content = (
            "harness: claude\n"
            "schema_version: '2.8'\n"
        )
        (self.cfg_dir / "config.yaml").write_text(config_content, encoding="utf-8")
        refresh(self.root)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _enable_telegram(self) -> None:
        config_path = self.cfg_dir / "config.yaml"
        current = config_path.read_text(encoding="utf-8")
        config_path.write_text(current + "notifications:\n  telegram: true\n", encoding="utf-8")
        refresh(self.root)

    def test_off_never_calls_opener_and_returns_none(self) -> None:
        calls = []

        def recording_opener(request: urllib.request.Request, **kwargs):
            calls.append(request)
            return _FakeResponse(200)

        result = notify.notify(self.root, "needs_input", "plan ready", opener=recording_opener)
        self.assertIsNone(result)
        self.assertEqual([], calls)

    def test_on_missing_credentials_returns_warning(self) -> None:
        self._enable_telegram()
        result = notify.notify(self.root, "needs_input", "plan ready", environ={})
        self.assertIsNotNone(result)
        self.assertIn("telegram_credentials_missing", result)

    def test_on_success_sends_expected_request(self) -> None:
        self._enable_telegram()
        calls = []

        def fake_opener(request: urllib.request.Request, **kwargs):
            calls.append(request)
            return _FakeResponse(200)

        environ = {"TELEGRAM_BOT_TOKEN": "TOKEN", "TELEGRAM_CHAT_ID": "42"}
        result = notify.notify(self.root, "needs_input", "plan ready", environ=environ, opener=fake_opener)
        self.assertIsNone(result)
        self.assertEqual(1, len(calls))
        req = calls[0]
        self.assertEqual("https://api.telegram.org/botTOKEN/sendMessage", req.full_url)
        params = urllib.parse.parse_qs(req.data.decode())
        self.assertEqual(["42"], params.get("chat_id"))
        self.assertEqual([f"[{self.root.name}] needs_input: plan ready"], params.get("text"))

    def test_on_http_error_warning_contains_status_code_not_token(self) -> None:
        self._enable_telegram()

        def error_opener(request: urllib.request.Request, **kwargs):
            raise urllib.error.HTTPError(request.full_url, 500, "boom", {}, None)

        environ = {"TELEGRAM_BOT_TOKEN": "TOKEN", "TELEGRAM_CHAT_ID": "42"}
        warning = notify.notify(self.root, "needs_input", "plan ready", environ=environ, opener=error_opener)
        self.assertIsNotNone(warning)
        self.assertIn("500", warning)
        self.assertNotIn("TOKEN", warning)

    def test_on_url_error_warning_present_not_token(self) -> None:
        self._enable_telegram()

        def error_opener(request: urllib.request.Request, **kwargs):
            raise urllib.error.URLError("down")

        environ = {"TELEGRAM_BOT_TOKEN": "TOKEN", "TELEGRAM_CHAT_ID": "42"}
        warning = notify.notify(self.root, "needs_input", "plan ready", environ=environ, opener=error_opener)
        self.assertIsNotNone(warning)
        self.assertNotIn("TOKEN", warning)

    def test_unknown_event_raises_value_error(self) -> None:
        with self.assertRaises(ValueError):
            notify.notify(self.root, "bogus", "x")

    def test_cli_dispatch(self) -> None:
        with self.assertRaises(SystemExit) as cm:
            notify.main(["--event", "bogus", "x"])
        self.assertEqual(2, cm.exception.code)

        self._enable_telegram()
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("TELEGRAM_")}
        stderr = io.StringIO()
        with patch.dict("os.environ", clean_env, clear=True), patch("sys.stderr", stderr):
            code = notify.main(["--event", "needs_input", "--repository", str(self.root), "hi"])
        self.assertEqual(0, code)
        self.assertIn("telegram_credentials_missing", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
