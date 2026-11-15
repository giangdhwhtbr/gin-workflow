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
        review = next(l for l in read("skills/review/ledger.md").splitlines()
                      if "parent" in l and ".planning/reviews/" in l and "workspace" in l)
        self.assertIn("review-ledger.py", review)
        self.assertIn("gin team complete <epic>", read("skills/ship/SKILL.md"))


def read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def line_with(text: str, *needles: str) -> str:
    return next((line for line in text.splitlines() if all(n in line for n in needles)), "")


class LeanLifecycleSkillTests(unittest.TestCase):
    """The skills follow project.run_at, review_ledger, review, and worktree (gin-workflow-ws-ship-records)."""

    def test_review_skill_names_the_ledger_only_when_it_is_on(self):
        review = read("skills/review/SKILL.md")
        for command in ("init --repo-id", "checkpoint --repo-id", "transition-requested"):
            with self.subTest(command=command):
                self.assertNotIn(command, review)
        self.assertTrue(line_with(review, "`ledger.md`", "`project.review_ledger: true`"))
        self.assertTrue(line_with(review, "`project.review_ledger: false`", "review-ledger.py", ".planning/reviews/"))
        self.assertTrue(line_with(review, "`project.review: self_check`", "secrets"))
        self.assertTrue(line_with(review, "`project.max_cycles`", "ask the user"))
        self.assertIn("Never manufacture approval", review)

    def test_ledger_reference_keeps_every_ledger_command(self):
        ledger = read("skills/review/ledger.md")
        for needle in ("python3 review-ledger.py <cmd> --bead-id <bead-id>", "init --repo-id", "--max-cycles",
                       "checkpoint --repo-id", "transition-requested --to review-requested --actor-role worker",
                       "transition-requested --to implementation-in-progress", "start-review --actor-id",
                       "--force-takeover", "resync-lease --lease-id", "validate", "add-finding --finding-id",
                       "verify-finding", "reopen-finding --reason", "approve --actor-id",
                       "transition-requested --to changes-requested --actor-role reviewer", "`reject`", "render",
                       "release-lease --actor-id", "literal flags", "max review cycles (N) reached",
                       "human_decision_required", "record-human-decision --question", "never hand-write"):
            with self.subTest(needle=needle):
                self.assertIn(needle, ledger)
        self.assertNotIn("gin evidence run", ledger)
        self.assertIn("Run steps 1 and 2 before the `review` skill's Requesting step 1, and step 3 "
                      "(`transition-requested`) after it.", ledger)
        requesting = ledger[ledger.index("## Requesting"):ledger.index("## Reviewing")]
        self.assertIn("3. `transition-requested --to review-requested", requesting)

    def test_review_tests_follow_run_at(self):
        review = read("skills/review/SKILL.md")
        self.assertTrue(line_with(review, "`project.run_at: track`", "gin evidence run"))
        self.assertTrue(line_with(review, "`project.run_at: track`", "gin evidence check"))
        self.assertTrue(line_with(review, "`push` or `host`", "tests of the changed code"))

    def test_review_response_and_reviewer_use_the_ledger_only_when_on(self):
        for rel in ("skills/review-response/SKILL.md", "agents/code-reviewer.md"):
            with self.subTest(path=rel):
                self.assertIn("`project.review_ledger: true`", read(rel))
        reviewer = read("agents/code-reviewer.md")
        self.assertIn("`approved` or `changes requested`", reviewer)
        self.assertIn("`Id`", reviewer)

    def test_execute_follows_worktree_ledger_and_run_at(self):
        execute = read("skills/execute/SKILL.md")
        self.assertTrue(line_with(execute, "`project.worktree: always`", "`parallel`", "`feat/<topic>`"))
        self.assertTrue(line_with(execute, "push-refs", "`project.review_ledger: true`"))
        self.assertTrue(line_with(execute, "`gin rules` output", "`project.run_at`"))
        close = line_with(execute, "gin task close <id>")
        for needle in ("reviewer", "cycle", "finding"):
            with self.subTest(needle=needle):
                self.assertIn(needle, close)
        for command in ("`init`", "`checkpoint`", "transition-requested"):
            with self.subTest(command=command):
                self.assertNotIn(command, execute)

    def test_orchestrate_and_worktrees_follow_the_settings(self):
        orchestrate = read("skills/orchestrate/SKILL.md")
        self.assertTrue(line_with(orchestrate, "`project.worktree`", "`always`", "`parallel`", "`feat/<topic>`"))
        self.assertNotIn("Isolate by default", orchestrate)
        worktrees = read("skills/worktrees/SKILL.md")
        baseline = worktrees[worktrees.index("## 3. Baseline"):worktrees.index("## Cleanup")]
        self.assertIn("`project.run_at: track`", baseline)
        self.assertIn("`push` or `host`", baseline)

    def test_ship_runs_the_suite_once_with_push(self):
        ship = read("skills/ship/SKILL.md")
        modes = line_with(ship, "Tests follow `project.run_at`")
        for mode in ("`push`", "`track`", "`host`"):
            with self.subTest(mode=mode):
                self.assertIn(mode, modes)
        self.assertNotIn("Do not run tests: the", ship)
        merge = ship[ship.index("**Merge:**"):ship.index("**PR:**")]
        self.assertLess(merge.index("review-ledger.py cleanup"), merge.index("gin evidence run"))
        self.assertLess(merge.index("gin evidence run"), merge.index('git merge "$FEATURE_BRANCH"'))
        self.assertIn("stops ship before the merge", merge)
        pr = ship[ship.index("**PR:**"):ship.index("**Keep:**")]
        self.assertLess(pr.index("gin evidence run"), pr.index("git push -u origin"))
        self.assertIn("`project.run_at: push`", pr)

    def test_tracks_push_only_in_team_mode(self):
        execute = read("skills/execute/SKILL.md")
        self.assertTrue(line_with(execute, "In team mode a track pushes its branch (its PR)"))
        self.assertTrue(line_with(execute, "merged at ship and not pushed, so the suite runs once"))
        self.assertTrue(line_with(execute, "Commit any remaining changes (stage-contract Git)."))
        self.assertTrue(line_with(execute, "`feat/<topic>`", "a standalone bead: `feat/<bead-id>` from the base"))
        self.assertTrue(line_with(read("references/stage-contract.md"), "`execute` pushes", "team mode"))

    def test_review_commits_before_requesting(self):
        review = read("skills/review/SKILL.md")
        step = line_with(review, "1. Commit the track's changes")
        self.assertIn("`checkpoint` in `ledger.md`", step)
        self.assertLess(step.index("Commit"), step.index("gin evidence run"))
        self.assertTrue(line_with(review, "its sections say where their commands go"))
        self.assertTrue(line_with(review, "absolute path of this skill's `ledger.md`"))
        self.assertIn("the `ledger.md` path", read("agents/code-reviewer.md"))
        self.assertIn("Without the ledger, answer each in your report", read("skills/review-response/SKILL.md"))

    def test_ship_merge_tests_the_feature_branch_before_the_base(self):
        ship = read("skills/ship/SKILL.md")
        self.assertTrue(line_with(ship, "review-ledger.py cleanup", "`project.review_ledger`"))
        merge = ship[ship.index("**Merge:**"):ship.index("**PR:**")]
        self.assertIn("in `MAIN_ROOT` when `IS_WORKTREE=no`", merge)
        self.assertLess(merge.index("gin evidence run"), merge.index("git checkout <base>"))
        workspace = merge[merge.index("Workspace:"):]
        self.assertLess(workspace.index("merge its track branches"), workspace.index("gin evidence run"))
        self.assertLess(workspace.index("gin evidence run"), workspace.index("merge `feat/<topic>` into `<default_branch>`"))

    def test_team_and_roadmap_handle_host_approvals(self):
        team = read("skills/team/SKILL.md")
        self.assertNotIn("lists roles", team)
        self.assertNotIn("(or roles)", team)
        self.assertTrue(line_with(team, "With `host`, ask no approver", "branch protection enforces approvals"))
        self.assertTrue(line_with(team, "(roles, `{all, any}`, `area_lead`, or `host`)"))
        review = team[team.index("## review"):team.index("## ship")]
        for needle in ("`project.review: self_check`", "Without the ledger", "review on the track's PR",
                       "`review-response`", "naming the reviewer", "`project.review_ledger: true`"):
            with self.subTest(needle=needle):
                self.assertIn(needle, review)
        roadmap = read("skills/roadmap/SKILL.md")
        self.assertFalse(line_with(roadmap, "`team.approvals.roadmap`", "lists roles"))
        self.assertTrue(line_with(roadmap, "`team.approvals.roadmap`", "`host`"))
        self.assertNotIn("lists roles", read("skills/roadmap/references/milestone-plan.md"))

    def test_developer_tests_follow_run_at(self):
        developer = read("agents/developer.md")
        run = line_with(developer, "`project.run_at`", "`track`")
        self.assertIn("`push` or `host`", run)
        self.assertIn("tests of what you changed", run)

    def test_progress_team_and_orchestrate_name_the_ledger_setting(self):
        progress = read("skills/progress/SKILL.md")
        self.assertTrue(line_with(progress, "review-ledger.py status", "`project.review_ledger: true`"))
        self.assertTrue(line_with(progress, "close reason"))
        team = read("skills/team/SKILL.md")
        self.assertTrue(line_with(team, "`start-review`", "`project.review_ledger: true`"))
        self.assertTrue(line_with(team, "track owner", "another member"))
        self.assertTrue(line_with(read("skills/orchestrate/SKILL.md"), "review ledgers", "`project.review_ledger: true`"))

    def test_quick_scopes_tests_by_run_at(self):
        quick = read("skills/quick/SKILL.md")
        scope = line_with(quick, "`project.run_at`", "changed files")
        self.assertIn("`push`", scope)
        self.assertIn("`host`", scope)
        self.assertTrue(line_with(quick, "`allowed`", "`run_at`", "`review`"))

    def test_setup_team_setup_workflow_and_contract(self):
        self.assertIn("--set verify.run_at=host", read("skills/setup/SKILL.md"))
        self.assertTrue(line_with(read("skills/setup/SKILL.md"), "**Host CI**", "CI on pull requests"))
        team_setup = read("skills/team-setup/SKILL.md")
        self.assertTrue(line_with(team_setup, "`host`", "`requirement_confirmed`", "`plan_approved`", "`ship`",
                                  "`roadmap`"))
        self.assertTrue(line_with(team_setup, "branch protection", "required status checks"))
        self.assertNotIn("ttl_seconds", read("skills/workflow/SKILL.md"))
        contract = read("references/stage-contract.md")
        self.assertTrue(line_with(contract, "review ledger", "`project.review_ledger`"))
        self.assertTrue(line_with(contract, "`project.run_at: host`", "pre-push"))
        self.assertIn("`project.review_ledger: true`", read("skills/team/references/workspace.md"))
