"""Skills and agents reach task tracking through `gin-workflow task`, so the markdown backend works without `bd`."""

from pathlib import Path
import re
import unittest

SRC = Path(__file__).resolve().parents[1] / "plugins/gin-workflow/src"
BEADS_ONLY = {"beads-migration", "team-setup", "gin-team"}


class TestNoDirectBd(unittest.TestCase):
    def test_skills_and_agents_do_not_call_bd_directly(self):
        offenders = []
        for path in sorted([*SRC.glob("skills/*/*.md"), *SRC.glob("agents/*.md")]):
            if path.parent.name in BEADS_ONLY:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if re.search(r"`bd\b", line):
                    offenders.append(f"{path.relative_to(SRC)}:{number}")
        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
