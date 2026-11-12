"""Tests for routing instructions across workflow skills and agents."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "plugins/gin-workflow/src"


class SkillRoutingTests(unittest.TestCase):
    def test_execute_skill_delegates_via_routes_dispatch(self):
        text = (SRC / "skills/execute/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("three or fewer", text)
        self.assertNotIn("Execute directly", text)
        self.assertIn("routes dispatch", text)
        self.assertIn("gin:developer", text)
        self.assertIn("needs_clarification", text)
        self.assertIn("--escalate", text)
        self.assertIn("routes dispatch --workflow-id <w> --task-id <id> --escalate", text)
        self.assertNotIn("notify --event", text)

    def test_review_skill_uses_model_and_effort(self):
        text = (SRC / "skills/review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--model", text)
        self.assertIn("gin:code-reviewer", text)
        self.assertNotIn("--tier", text)

    def test_plan_skill_and_schema_use_catalog_routes(self):
        for path in (SRC / "skills/plan/SKILL.md", SRC / "skills/plan/plan-schema.md"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIn("Model:", text)
                self.assertIn("Effort:", text)
                self.assertIn("Why:", text)
                self.assertNotIn("Reasoning", text)
                self.assertNotIn("Model Guidance", text)
                self.assertNotIn("high_reasoning", text)
                self.assertNotIn("standard_impl", text)
                self.assertNotIn("cheap_simple", text)

    def test_orchestrate_skill_tracks_file_format(self):
        text = (SRC / "skills/orchestrate/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"model", "effort"', text)
        self.assertNotIn('"reasoning"', text)
        self.assertNotIn("model names never enter", text)

    def test_discuss_and_plan_delegate_exploration_to_researcher(self):
        for path in (SRC / "skills/discuss/SKILL.md", SRC / "skills/plan/SKILL.md"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIn("gin:agent-researcher", text)

    def test_discuss_and_plan_use_confirmed_glossary_terms(self):
        for path in (SRC / "skills/discuss/SKILL.md", SRC / "skills/plan/SKILL.md"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIn("`11-GLOSSARY.md`", text)
                self.assertIn("`confirmed` English terms", text)

    def test_roadmap_names_capabilities_per_epic(self):
        text = (SRC / "skills/roadmap/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`Capabilities:`", text)
        self.assertIn("`(new)`", text)
        self.assertIn("02-FEATURES.md", text)
        self.assertLess(text.index("`Capabilities:`"), text.index("5. **Write**"))

    def test_sdd_discuss_confirms_capabilities_before_ids(self):
        text = (SRC / "skills/sdd/SKILL.md").read_text(encoding="utf-8")
        discuss = text[text.index("## discuss"):text.index("## plan")]
        for needle in ("Capabilities affected", "`ui` holds only", "`(new)`", "renumbering",
                       "## Capabilities Affected", "`specs assets add <cap> <files...> [--date <YYYY-MM-DD>]`", "README.md",
                       "<specs>/<cap>/assets/<YYYY-MM-DD>/<file>", "`--legacy`",
                       "`legacy/`", "Never edit an older dated folder",
                       "`<specs>/<cap>/diagrams/<feature>-activity.md`", "`specs template activity.md`",
                       "`specs template state.md`", "three or more states", "`## Data Flow`",
                       "`## Diagrams`", "`<specs>/<cap>/use-cases/<slug>.md`", "`specs template use-case.md`",
                       "`## Use Cases`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, discuss)
        self.assertLess(discuss.index("Capabilities affected"), discuss.index("`specs new <slug> --epic <epic>`"))
        self.assertLessEqual(len(text), 6_000)

    def test_sdd_discuss_reads_and_cites_confirmed_inputs(self):
        text = (SRC / "skills/sdd/SKILL.md").read_text(encoding="utf-8")
        discuss = text[text.index("## discuss"):text.index("## plan")]
        for needle in ("`description.md`", "`mockup/index.html`", "`Confirmed: <date>`", "`Confirmed: no`",
                       "`## Open questions`", "`Source:`", "`#<screen-id>`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, discuss)
        self.assertLess(discuss.index("Never edit an older dated folder"), discuss.index("`Source:`"))
        self.assertLessEqual(len(text), 6_000)

    def test_sdd_names_the_srs_export(self):
        text = (SRC / "skills/sdd/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`specs export <cap>`", text)
        self.assertIn("`--all`", text)
        self.assertLessEqual(len(text), 6_000)

    def test_explain_skill_runs_the_cli_with_a_narrative(self):
        text = (SRC / "skills/explain/SKILL.md").read_text(encoding="utf-8")
        for needle in ("`gin specs explain <name> --narrative", "`project.layout: sdd`", "`/gin:migrate-specs`",
                       ".agent-workflow/runtime/explain/<name>.narrative.md", "Cite REQ-IDs", "Never commit"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertLessEqual(len(text), 6_000)

    def test_review_response_skill_routes_to_same_route(self):
        text = (SRC / "skills/review-response/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("same route", text)
        self.assertNotIn("same-reasoning", text)

    def test_developer_agent_reports_normalized_status(self):
        text = (SRC / "agents/developer.md").read_text(encoding="utf-8")
        self.assertNotIn("routes dispatch", text)
        self.assertIn("section 2 (Implement)", text)
        for status in ("done", "needs_clarification", "failed", "blocked"):
            with self.subTest(status=status):
                self.assertIn(status, text)

    def test_execute_references_use_dispatch_and_normalized_statuses(self):
        ref_dir = SRC / "skills/execute/references"
        contract = (ref_dir / "result-contract.md").read_text(encoding="utf-8")
        dispatch = (ROOT / "plugins/gin-orchestrator/src/scripts/gin_orchestrator/worker_dispatch.py").read_text(encoding="utf-8")
        self.assertIn("status must be completed, failed, or cancelled", dispatch)
        self.assertIn("`status`: `completed`, `failed`, or `cancelled`", contract)
        policy = (ref_dir / "delegation-policy.md").read_text(encoding="utf-8")
        for status in ("done", "needs_clarification", "failed", "blocked"):
            with self.subTest(status=status):
                self.assertIn(status, policy)
        self.assertIn("never lowered", policy)
        self.assertIn("one isolated worktree per worker", policy)

        for path in (ref_dir / "worker-lifecycle.md", ref_dir / "delegation-policy.md"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIn("routes dispatch", text)

    def test_skills_reference_orchestrator_dispatch(self):
        paths = [
            SRC / "skills/execute/references/worker-lifecycle.md",
            SRC / "skills/execute/SKILL.md",
            SRC / "skills/review/SKILL.md",
            SRC / "skills/discuss/SKILL.md",
            SRC / "skills/plan/SKILL.md",
            SRC / "skills/tech-doc/SKILL.md",
        ]
        for path in paths:
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertIn("gin-orchestrator dispatch", text)

