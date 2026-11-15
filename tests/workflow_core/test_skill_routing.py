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

    def test_roadmap_manager_view_and_milestone_plan(self):
        roadmap = SRC / "skills/roadmap"
        text = (roadmap / "SKILL.md").read_text(encoding="utf-8")
        for needle in ("[manager view](references/manager-view.md)", "[milestone plan](references/milestone-plan.md)",
                       "`Features:`", "`Legacy:`", "13-CAPABILITIES.md"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        present = text[text.index("4. **Present the roadmap**"):text.index("5. **Write**")]
        capabilities = present[present.index("`Capabilities:`"):present.index("`Depends on:`")]
        self.assertLess(capabilities.index("13-CAPABILITIES.md"), capabilities.index("02-FEATURES.md"))
        view = (roadmap / "references/manager-view.md").read_text(encoding="utf-8")
        for needle in ("## Legacy coverage", "`planned`", "`not migrated: <reason>`", "`unplanned`",
                       "no file paths", "never in Beads"):
            with self.subTest(needle=needle):
                self.assertIn(needle, view)
        self.assertIn("written by `/milestone-close`", view)
        plan = (roadmap / "references/milestone-plan.md").read_text(encoding="utf-8")
        for needle in ("gin milestone create", "gin milestone move", "gin milestone estimate", "Beads wins",
                       "## Unassigned", "Deadline:"):
            with self.subTest(needle=needle):
                self.assertIn(needle, plan)
        write = plan[plan.index("## Write"):plan.index("## Re-run")]
        self.assertLess(write.index("gin milestone create"), write.index("gin milestone move"))
        self.assertLess(write.index("gin milestone move"), write.index("gin milestone estimate"))
        self.assertIn("existed before this run", write)
        self.assertIn("`Depends on:` dependencies", write)
        milestone = text[text.index("## With --milestone <id>"):text.index("## Steps")]
        step2 = next(line for line in milestone.splitlines() if line.startswith("2. "))
        self.assertIn("Estimates block of [milestone plan](references/milestone-plan.md)", step2)
        estimates = plan[plan.index("## Estimates"):plan.index("## Plan")]
        for needle in ("`requirement.confirmed`", "`(assumed)`", "never ask the PM for estimates"):
            with self.subTest(needle=needle):
                self.assertIn(needle, estimates)
        allocation = plan[plan.index("## Allocation"):plan.index("## Write")]
        self.assertIn("adoption rule of `--milestone` step 3", allocation)
        self.assertIn("never a closed one", allocation)

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
                       "<name>.md", "--legacy", "frozen", "CLAUDE.md", "Cite REQ-IDs", "Never commit"):
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


    def test_allocate_creates_prep_tasks_without_inherited_labels(self):
        text = (SRC / "skills/allocate/SKILL.md").read_text(encoding="utf-8")
        for needle in ("--no-inherit-labels --labels prep,prep:<type>", "team.beads_sync",
                       "gin milestone show <id> --json", "[gin answer] <prep-id>:"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertNotIn("gin-ba", text)

    def test_prep_catalog_lists_the_five_types(self):
        text = (SRC / "skills/allocate/references/prep-catalog.md").read_text(encoding="utf-8")
        for kind in ("capture", "mockup", "spike", "question", "other"):
            with self.subTest(kind=kind):
                self.assertIn(f"`{kind}`", text)

    def test_retro_records_one_comment_on_an_open_milestone(self):
        text = (SRC / "skills/retro/SKILL.md").read_text(encoding="utf-8")
        for needle in ("[gin retro] <milestone-id> <member>", "Went well:", "Slowed us:", "Change next:",
                       "gin task comment <milestone-id>", "gin milestone show <id> --json",
                       "`status` is `active`", "project.team.me", "gin team sync",
                       "Write nothing until the member confirms", "the newest one counts",
                       "its close already read the retros", "Never translate the labels"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertLess(text.index("Went well:"), text.index("Slowed us:"))
        self.assertLess(text.index("Slowed us:"), text.index("Change next:"))
        for banned in ("sonnet", "opus", "haiku"):
            self.assertNotIn(banned, text.lower())

    def test_milestone_close_moves_spillover_and_records_the_result(self):
        text = (SRC / "skills/milestone-close/SKILL.md").read_text(encoding="utf-8")
        for needle in ("[gin close] <milestone-id>", "Delivered:", "Spillover:", "Outcome:", "Demo:", "Retros:",
                       "Action:", "earliest `start` after", "`status` is `closed`", "team.permissions.milestone",
                       "Write nothing until the person running the close confirms", "no retros",
                       "reason (retro|asked)", "Reconcile steps of the `learn` skill", "gin task remember",
                       "milestone-close/<milestone-id>", "Never translate the labels",
                       "## Metrics", "Metrics: completion <closed>/<total>; estimate_accuracy", "capacity_used",
                       "cost_per_epic", "rework", "never per member", "no earlier metrics", "- Metrics:"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        metrics = text[text.index("Metrics: completion"):].split("\n", 1)[0]
        keys = [metrics.index(key) for key in ("completion", "estimate_accuracy", "capacity_used", "cost_per_epic", "rework")]
        self.assertEqual(sorted(keys), keys)
        write = text[text.index("## Write"):]
        order = [write.index(step) for step in ("gin milestone create", "gin milestone move", "gin milestone estimate",
                                                "gin task comment", "gin milestone close")]
        self.assertEqual(sorted(order), order)
        for banned in ("sonnet", "opus", "haiku"):
            self.assertNotIn(banned, text.lower())

    def test_execute_excludes_prep_tasks(self):
        lines = (SRC / "skills/execute/SKILL.md").read_text(encoding="utf-8").splitlines()
        self.assertEqual(lines[13].count("--exclude-label prep"), 2)
        self.assertIn("team ready --exclude-label prep", lines[14])
        self.assertEqual(len([line for line in lines if "project.team" in line]), 1)

    def test_ship_skips_prep_tasks_in_ledger_checks_and_closes_them(self):
        text = (SRC / "skills/ship/SKILL.md").read_text(encoding="utf-8")
        ledger = next(line for line in text.splitlines() if "review-ledger.py validate" in line)
        self.assertIn("`prep`", ledger)
        self.assertIn("closed without review", ledger)
        self.assertIn("not needed: <epic> shipped", text)
        self.assertIn("gin task ready --exclude-label prep", text)

    def test_discuss_reads_prep_tasks(self):
        text = (SRC / "skills/discuss/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("--label prep --all --json", text)

    def test_ready_work_excludes_prep_tasks(self):
        for name in ("orchestrate", "progress", "parallel-agents"):
            text = (SRC / f"skills/{name}/SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=name):
                self.assertIn("gin task ready --exclude-label prep", text)

    def test_progress_reports_milestone_approvals_and_qa_state(self):
        text = (SRC / "skills/progress/SKILL.md").read_text(encoding="utf-8")
        for needle in (
            "gin milestone show <id> --json",
            "plain-language",
            "--area <name>",
            "waiting on another area",
            "gin team pending",
            "approvals unknown:",
            "QA state",
            "--exclude-label prep",
            "[gin question]",
            "waived(",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)
        self.assertNotIn("gin-qa", text)

    def test_qa_track_defines_qa_state(self):
        text = (SRC / "skills/qa-track/SKILL.md").read_text(encoding="utf-8")
        for needle in (
            "## QA state",
            "gin-qa cases plan --change <epic> --format json",
            "QA state skipped:",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)

    def test_roadmap_cadence_points_to_allocate(self):
        text = (SRC / "skills/roadmap/references/way-of-working.md").read_text(encoding="utf-8")
        self.assertIn("/allocate --milestone <id>", text)

    def test_implementation_complete_ignores_prep_children(self):
        text = (SRC / "references/stage-contract.md").read_text(encoding="utf-8")
        self.assertIn("not labelled `prep`", text)

    def test_learn_comments_from_every_stage(self):
        read = lambda p: (SRC / p).read_text(encoding="utf-8")
        learn = read("skills/learn/SKILL.md")
        for needle in ("[gin learn] <stage> <track-id|->:", "## Learnings", "knowledge_candidates", "Reconcile (ship, before the options)"):
            with self.subTest(needle=needle):
                self.assertIn(needle, learn)
        self.assertIn("write no comment except `[gin learn]`", read("skills/discuss/SKILL.md"))
        plan = next(l for l in read("skills/plan/SKILL.md").splitlines() if l.startswith("1. Require"))
        self.assertIn("other than `[gin learn]`", plan)
        self.assertIn("as `[gin learn]` per `learn`", read("skills/execute/SKILL.md"))
        self.assertIn("`Learnings`", read("agents/developer.md"))
        contract = read("skills/execute/references/result-contract.md")
        self.assertIn("fact", contract)
        self.assertIn("evidence", contract)

    def test_ship_writes_knowledge_before_the_options(self):
        lines = (SRC / "skills/ship/SKILL.md").read_text(encoding="utf-8").splitlines()
        allowed = next(l for l in lines if "may touch only" in l)
        self.assertIn(".planning/knowledge/", allowed)
        reconcile = next(i for i, l in enumerate(lines) if "reconcile knowledge per `learn`" in l)
        present = next(i for i, l in enumerate(lines) if l.startswith("4. Present"))
        self.assertLess(reconcile, present)

    def test_workspace_skills_use_child_aware_commands(self):
        def read(rel):
            return (SRC / rel).read_text(encoding="utf-8")

        self.assertIn("gin hooks status --all-repos", read("skills/ship/SKILL.md"))
        setup = read("skills/setup/SKILL.md")
        self.assertIn("gin workspace add", setup)
        self.assertIn("gin team init --all-repos", setup)
        self.assertNotIn("gin hooks install --all-repos", setup)
        for skill in ("tech-doc", "explain", "discuss"):
            with self.subTest(skill=skill):
                text = read(f"skills/{skill}/SKILL.md")
                self.assertIn("gin workspace clone <path>", text)
                self.assertIn("gin workspace status --json", text)

    def test_team_branch_model_is_in_the_skills(self):
        def read(rel):
            return (SRC / rel).read_text(encoding="utf-8")

        self.assertIn("references/workspace.md", read("skills/team/SKILL.md"))
        ref = read("skills/team/references/workspace.md")
        for needle in ("gin team claim <bead>", "gin team complete <epic>",
                       "git pull --rebase", "origin/<default_branch>"):
            with self.subTest(needle=needle):
                self.assertIn(needle, ref)
        orchestrate = read("skills/orchestrate/SKILL.md")
        self.assertIn("gin team claim", orchestrate)
        self.assertIn("default branch after the spec and plan pull requests merge", orchestrate)
        self.assertIn("committed on `plan/<topic>`", read("skills/plan/SKILL.md"))
        review = next(l for l in read("skills/review/SKILL.md").splitlines()
                      if "parent" in l and ".planning/reviews/" in l and "workspace" in l)
        self.assertIn("review-ledger.py", review)
        self.assertIn("gin team complete <epic>", read("skills/ship/SKILL.md"))
