"""Token budget measurement and limits for packaged gin-workflow instructions."""

from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from workflow_core.budget import STAGES, description_chars, stage_chain, stage_chars

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "plugins/gin-workflow/src"
BANNED = ("ContextManifest", "ArtifactRegistry", "ApprovalDecision", "load_effective_config")


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class TestBudgetMeasurement(unittest.TestCase):
    def test_chain_includes_command_skill_and_linked_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write(src, "commands/execute.md", "---\ndescription: x\n---\nUse the `execute` skill.\n")
            _write(src, "skills/execute/SKILL.md", "Follow references/stage-contract.md.\nSee [w](references/worker-lifecycle.md).\n")
            _write(src, "references/stage-contract.md", "contract")
            _write(src, "skills/execute/references/worker-lifecycle.md", "lifecycle")
            _write(src, "references/unrelated.md", "unused")
            names = sorted(p.relative_to(src.resolve()).as_posix() for p in stage_chain(src, "execute"))
            self.assertEqual(
                [
                    "commands/execute.md",
                    "references/stage-contract.md",
                    "skills/execute/SKILL.md",
                    "skills/execute/references/worker-lifecycle.md",
                ],
                names,
            )
            self.assertEqual(sum(len(p.read_text()) for p in stage_chain(src, "execute")), stage_chars(src, "execute"))

    def test_chain_follows_named_methodology_skill_and_its_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write(src, "commands/plan.md", "Use the `writing-plans` methodology skill.\n")
            _write(src, "skills/writing-plans/SKILL.md", "See [s](plan-schema.md).\n")
            _write(src, "skills/writing-plans/plan-schema.md", "schema")
            _write(src, "skills/other/SKILL.md", "not named")
            names = sorted(p.relative_to(src.resolve()).as_posix() for p in stage_chain(src, "plan"))
            self.assertEqual(
                ["commands/plan.md", "skills/writing-plans/SKILL.md", "skills/writing-plans/plan-schema.md"],
                names,
            )

    def test_conditionally_named_skill_in_stage_skill_is_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write(src, "commands/execute.md", "Use the `execute` skill.\n")
            _write(src, "skills/execute/SKILL.md", "Failures route to the `gin-debugging` skill.\n")
            _write(src, "skills/gin-debugging/SKILL.md", "debug")
            names = sorted(p.relative_to(src.resolve()).as_posix() for p in stage_chain(src, "execute"))
            self.assertEqual(["commands/execute.md", "skills/execute/SKILL.md"], names)

    def test_description_chars_sums_frontmatter_descriptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp)
            _write(src, "skills/a/SKILL.md", "---\nname: a\ndescription: abcd\n---\n")
            _write(src, "agents/b.md", "---\nname: b\ndescription: ef\n---\n")
            _write(src, "commands/c.md", "---\ndescription: g\n---\n")
            self.assertEqual(7, description_chars(src))


class TestBudgetLimits(unittest.TestCase):
    def test_each_stage_chain_within_budget(self):
        for stage in STAGES:
            with self.subTest(stage=stage):
                self.assertLessEqual(stage_chars(SRC, stage), 12_000)

    def test_quick_chain_within_8000(self):
        self.assertLessEqual(stage_chars(SRC, "quick"), 8_000)

    def test_rule_pack_bodies_within_budget(self):
        from workflow_core.rules import load_plugin_packs

        packs = load_plugin_packs(SRC / "rules")
        self.assertEqual({"core", "typescript", "python", "react", "nextjs", "fastapi", "node-api"}, set(packs))
        for pack in packs.values():
            with self.subTest(pack=pack.id):
                self.assertLessEqual(pack.body_chars, pack.body_limit)

    def test_commands_agents_and_shared_skills_within_budget(self):
        limits = [("agents/*.md", 4_000), ("skills/gin-*/SKILL.md", 6_000), ("references/shape-*.md", 1_500)]
        for pattern, limit in limits:
            paths = sorted(SRC.glob(pattern))
            self.assertTrue(paths, pattern)
            for path in paths:
                with self.subTest(path=path.name):
                    self.assertLessEqual(len(path.read_text(encoding="utf-8")), limit)

    def test_no_command_shadows_a_same_name_skill(self):
        # Claude Code resolves /gin-workflow:<name> to a same-name command, so the skill never loads.
        for path in SRC.glob("commands/*.md"):
            with self.subTest(command=path.name):
                self.assertFalse((SRC / "skills" / path.stem / "SKILL.md").is_file())

    def test_stage_skills_inline_setup_guard_and_contract_read(self):
        # A one-line "follow the contract" pointer is not followed by models (gin-workflow-hei);
        # the setup stop must be inline and the contract read must be an explicit first step.
        for stage in STAGES:
            text = (SRC / "skills" / stage / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(stage=stage):
                self.assertLess(text.index("## Before you start"), text.index("\n# "))
                self.assertIn("`.agent-workflow/generated/effective-config.yaml` does not exist", text)
                self.assertIn("run `/setup` once and do nothing else", text)
                self.assertIn("Read [references/stage-contract.md](../../references/stage-contract.md) now", text)

    def test_descriptions_within_budget(self):
        self.assertLessEqual(description_chars(SRC), 4_000)

    def test_no_abstract_contract_tokens(self):
        for path in [*SRC.glob("commands/*.md"), *SRC.glob("skills/**/SKILL.md")]:
            text = path.read_text(encoding="utf-8")
            for token in BANNED:
                with self.subTest(path=str(path.relative_to(SRC)), token=token):
                    self.assertNotIn(token, text)


if __name__ == "__main__":
    unittest.main()
