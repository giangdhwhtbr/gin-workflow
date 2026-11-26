"""Tests run as in CI: without the id of the Claude Code session that may have started them."""

import os

os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
