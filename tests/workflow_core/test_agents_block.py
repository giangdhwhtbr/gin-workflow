"""Tests for workflow_core.agents_block."""

from pathlib import Path
import stat
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugins/gin-workflow/src/scripts"))

from workflow_core import agents_block  # noqa: E402


class AgentsBlockTests(unittest.TestCase):
    def test_render_lists_only_configured_checks_in_order(self):
        config = {
            "verify": {
                "checks": {
                    "lint": "ruff check .",
                    "test": "pytest",
                    "typecheck": "",
                }
            }
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            rendered = agents_block.render(Path(temp_dir), config)
            self.assertIn("- Checks (git hooks): lint `ruff check .` · test `pytest`", rendered)
            self.assertNotIn("typecheck", rendered)

    def test_render_without_checks_says_none_configured(self):
        config = {"verify": {"checks": {}}}
        with tempfile.TemporaryDirectory() as temp_dir:
            rendered = agents_block.render(Path(temp_dir), config)
            self.assertIn(
                "- Checks: none configured yet; `gin-workflow setup doctor` reports them once sources exist.",
                rendered,
            )

    def test_render_docs_links_only_existing_paths_legacy(self):
        config = {}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".planning").mkdir(parents=True, exist_ok=True)
            (root / ".planning/roadmap.md").write_text("roadmap", encoding="utf-8")
            rendered = agents_block.render(root, config)
            self.assertIn("- Roadmap: `.planning/roadmap.md`", rendered)
            self.assertNotIn("Codebase docs", rendered)

        with tempfile.TemporaryDirectory() as empty_dir:
            rendered_empty = agents_block.render(Path(empty_dir), config)
            self.assertNotIn("Roadmap:", rendered_empty)
            self.assertNotIn("Codebase docs:", rendered_empty)

    def test_render_docs_links_sdd_layout(self):
        config = {"artifacts": {"layout": "sdd", "codebase": "docs/cb"}}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "docs").mkdir(parents=True, exist_ok=True)
            (root / "docs/roadmap.md").write_text("roadmap", encoding="utf-8")
            (root / "docs/cb").mkdir(parents=True, exist_ok=True)
            rendered = agents_block.render(root, config)
            self.assertIn("- Roadmap: `docs/roadmap.md` · Codebase docs: `docs/cb/`", rendered)

    def test_locate_broken_markers_raise(self):
        # missing END
        with self.assertRaises(agents_block.AgentsBlockError):
            agents_block.locate(f"{agents_block.START}\nsome content")

        # duplicate START
        with self.assertRaises(agents_block.AgentsBlockError):
            agents_block.locate(f"{agents_block.START}\n{agents_block.START}\n{agents_block.END}")

        # END before START
        with self.assertRaises(agents_block.AgentsBlockError):
            agents_block.locate(f"{agents_block.END}\n{agents_block.START}")

    def test_create_on_empty_repo_writes_agents_and_claude(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writes = agents_block.planned_writes(root, {}, create=True)
            agents = root / "AGENTS.md"
            claude = root / "CLAUDE.md"
            self.assertEqual(set(writes.keys()), {agents, claude})
            self.assertEqual(writes[claude], b"@AGENTS.md\n")
            self.assertTrue(writes[agents].startswith(agents_block.START.encode("utf-8")))
            self.assertTrue(writes[agents].endswith((agents_block.END + "\n").encode("utf-8")))

    def test_create_preserves_outside_bytes_crlf(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            agents = root / "AGENTS.md"
            claude = root / "CLAUDE.md"
            agents.write_bytes(b"# Mine\r\nkeep\r\n")
            claude.write_bytes(b"# Notes\r\n")
            writes = agents_block.planned_writes(root, {}, create=True)
            self.assertTrue(writes[agents].startswith(b"# Mine\r\nkeep\r\n"))
            self.assertIn(b"\r\n", writes[agents])
            self.assertNotIn(b"\n## gin-workflow", writes[agents].replace(b"\r\n", b""))
            self.assertEqual(writes[claude], b"@AGENTS.md\r\n\r\n# Notes\r\n")

    def test_second_run_is_noop(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writes = agents_block.planned_writes(root, {}, create=True)
            agents_block.write(writes)
            self.assertEqual(agents_block.planned_writes(root, {}, create=True), {})
            self.assertEqual(agents_block.planned_writes(root, {}, create=False), {})

    def test_refresh_never_creates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writes = agents_block.planned_writes(root, {}, create=False)
            self.assertEqual(writes, {})
            self.assertFalse((root / "AGENTS.md").exists())
            self.assertFalse((root / "CLAUDE.md").exists())

    def test_status_states(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            # absent (no file)
            self.assertEqual(agents_block.status(root, {}), "absent")
            # absent (file without block)
            (root / "AGENTS.md").write_text("# Custom notes\n", encoding="utf-8")
            self.assertEqual(agents_block.status(root, {}), "absent")
            # ok after write
            writes = agents_block.planned_writes(root, {}, create=True)
            agents_block.write(writes)
            self.assertEqual(agents_block.status(root, {}), "ok")
            # stale after creating .planning/roadmap.md
            (root / ".planning").mkdir(parents=True, exist_ok=True)
            (root / ".planning/roadmap.md").write_text("roadmap", encoding="utf-8")
            self.assertEqual(agents_block.status(root, {}), "stale")
            # invalid with a lone START
            (root / "AGENTS.md").write_text(f"{agents_block.START}\nsome notes\n", encoding="utf-8")
            self.assertEqual(agents_block.status(root, {}), "invalid")

    def test_new_file_mode_is_0644(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            writes = agents_block.planned_writes(root, {}, create=True)
            agents_block.write(writes)
            agents = root / "AGENTS.md"
            claude = root / "CLAUDE.md"
            self.assertEqual(stat.S_IMODE(agents.stat().st_mode), 0o644)
            self.assertEqual(stat.S_IMODE(claude.stat().st_mode), 0o644)

    def test_claude_symlink_to_agents_is_left_alone(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            claude = root / "CLAUDE.md"
            agents = root / "AGENTS.md"
            claude.symlink_to("AGENTS.md")
            writes = agents_block.planned_writes(root, {}, create=True)
            self.assertNotIn(claude, writes)
            self.assertIn(agents, writes)
            self.assertNotIn("@AGENTS.md", writes[agents].decode("utf-8"))

    def test_claude_symlink_elsewhere_or_dangling_is_left_alone(self):
        for target in ("docs/x.md", "nowhere.md"):
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                (root / "docs").mkdir()
                (root / "docs/x.md").write_text("# x\n", encoding="utf-8")
                (root / "CLAUDE.md").symlink_to(target)
                writes = agents_block.planned_writes(root, {}, create=True)
                self.assertEqual([root / "AGENTS.md"], list(writes))
                agents_block.write(writes)
                self.assertTrue((root / "CLAUDE.md").is_symlink())

    def test_symlinked_agents_needing_a_write_raises(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "real.md").write_text("# mine\n", encoding="utf-8")
            (root / "AGENTS.md").symlink_to("real.md")
            with self.assertRaises(agents_block.AgentsBlockError):
                agents_block.planned_writes(root, {}, create=True)

    def test_status_of_symlinked_agents_with_stale_block_is_invalid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "real.md").write_text(f"{agents_block.START}\nold\n{agents_block.END}\n", encoding="utf-8")
            (root / "AGENTS.md").symlink_to("real.md")
            self.assertEqual("invalid", agents_block.status(root, {}))

    def test_roadmap_and_tech_doc_skills_remind_refresh(self):
        for relative in (
            "plugins/gin-workflow/src/skills/roadmap/SKILL.md",
            "plugins/gin-workflow/src/skills/tech-doc/SKILL.md",
        ):
            with self.subTest(path=relative):
                text = (ROOT / relative).read_text(encoding="utf-8")
                self.assertIn("gin-workflow setup refresh", text)


    def test_render_names_the_configured_task_backend(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            beads = agents_block.render(Path(temp_dir), {"providers": {"task_tracking": "beads"}})
            markdown = agents_block.render(Path(temp_dir), {"providers": {"task_tracking": "markdown"}})
        self.assertIn("- Track work in Beads (`bd`). Stages:", beads)
        self.assertNotIn("`bd`", markdown)
        self.assertIn("- Track work with `gin-workflow task` (local Markdown tasks in `.planning/tasks/`). Stages:",
                      markdown)

if __name__ == "__main__":
    unittest.main()

