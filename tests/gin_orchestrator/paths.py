"""Put both script directories on `sys.path` so the worker library and `workflow_core` import."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CORE_SCRIPTS = ROOT / "plugins/gin-workflow/src/scripts"
ORCH_SCRIPTS = ROOT / "plugins/gin-orchestrator/src/scripts"
for path in (CORE_SCRIPTS, ORCH_SCRIPTS):
    sys.path.insert(0, str(path))
