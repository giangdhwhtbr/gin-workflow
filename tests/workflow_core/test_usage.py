"""Usage summaries: prices, cost, quality signals, collect into bead metadata, and reports (fake bd)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import calls, fake_cli, git, path_with, write  # noqa: E402
from workflow_core import usage  # noqa: E402
from workflow_core.events import WorkflowEvent, WorkflowEventStore  # noqa: E402
from workflow_core.setup_service import refresh  # noqa: E402
from workflow_core.usage_logs import UsageRecord  # noqa: E402

DAY = datetime(2026, 10, 4, tzinfo=timezone.utc)
SECRET = "SECRET PROMPT"


def at(hour: float) -> datetime:
    return DAY + timedelta(hours=hour)


def iso(hour: float) -> str:
    return at(hour).isoformat().replace("+00:00", "Z")


def record(model: str = "m1", stage_hour: float = 1, role: str = "main", **tokens) -> UsageRecord:
    values = {"input": 1000, "output": 100, "cache_read": 10000, "cache_write": 0, **tokens}
    return UsageRecord(at(stage_hour), "claude_code", model, "s", "/r", "", **values, role=role)


class PriceTests(unittest.TestCase):
    def test_load_prices(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            defaults = usage.load_prices(repo)
            self.assertEqual(usage.Price(4, 20, 0.2, 5, "default"), defaults["claude-opus-5-5"])
            for model in ("claude-fable-5-1", "claude-haiku-5-5", "gpt-5.6-sol", "gpt-6-astra", "gemini-2.5-pro"):
                self.assertEqual("default", defaults[model].source, model)
            write(repo, usage.PRICES_FILE, "prices:\n  claude-opus-5-5: {input: 3, output: 15, cache_read: 0.3, cache_write: 3.75}\n  m1: {input: 1, output: 2, cache_read: 0, cache_write: 0}\n")
            prices = usage.load_prices(repo)
            self.assertEqual(usage.Price(3, 15, 0.3, 3.75, "repo"), prices["claude-opus-5-5"])
            self.assertEqual("repo", prices["m1"].source)
            self.assertEqual(prices["claude-sonnet-4-5"], usage.price_for(prices, "claude-sonnet-4-5-20250929"))
            self.assertEqual(prices["m1"], usage.price_for(prices, "m1-2"))
            self.assertIsNone(usage.price_for(prices, "m10"))
            self.assertIsNone(usage.price_for(prices, "codex-auto-review"))
            write(repo, usage.PRICES_FILE, "prices:\n  m1: {input: lots, output: 15, cache_read: 0, cache_write: 0}\n")
            with self.assertRaises(usage.UsageError):
                usage.load_prices(repo)
            write(repo, usage.PRICES_FILE, "- not a mapping\n")
            with self.assertRaises(usage.UsageError):
                usage.load_prices(repo)

    def test_cost(self):
        totals = {"input": 1_000_000, "output": 100_000, "cache_read": 2_000_000, "cache_write": 0}
        self.assertEqual(usage.cost(totals, usage.Price(3, 15, 0.3, 3.75)), 5.1)
        self.assertIsNone(usage.cost(totals, None))


class SummarizeTests(unittest.TestCase):
    def test_document_shape_and_unpriced_models(self):
        prices = {"m1": usage.Price(3, 15, 0.3, 3.75)}
        by_stage = {"execute": [record("m1", role="main"), record("m2", role="subagent")], "review": [record("m1", role="main")]}
        quality = usage.empty_quality()
        doc = usage.summarize(by_stage, prices, quality, {"claude_code": "ok", "codex": "not_found"}, 2, at(5))
        self.assertEqual(doc["version"], 1)
        self.assertEqual(doc["collected_at"], iso(5))
        self.assertEqual(doc["models"]["m1"], {"input": 2000, "output": 200, "cache_read": 20000, "cache_write": 0,
                                               "cost": 0.015, "price_source": "repo"})
        self.assertIsNone(doc["models"]["m2"]["cost"])
        self.assertEqual("none", doc["models"]["m2"]["price_source"])
        self.assertEqual("repo", doc["models"]["m1"]["price_source"])
        self.assertEqual(doc["roles"]["main"]["m1"], {"input": 2000, "output": 200, "cache_read": 20000, "cache_write": 0,
                                                      "cost": 0.015, "price_source": "repo"})
        self.assertEqual(doc["roles"]["subagent"]["m2"], {"input": 1000, "output": 100, "cache_read": 10000, "cache_write": 0,
                                                          "cost": None, "price_source": "none"})
        self.assertEqual(doc["stages"]["execute"], {"tokens": 22200, "cost": 0.0075})
        self.assertEqual(doc["cost"], 0.015)
        self.assertEqual(doc["unpriced"], ["m2"])
        self.assertEqual(doc["sources"], {"claude_code": "ok", "codex": "not_found"})
        self.assertEqual(doc["skipped_lines"], 2)
        self.assertEqual(doc["quality"], quality)
        self.assertNotIn("unattributed", doc)

    def test_nothing_priced_gives_null_cost(self):
        doc = usage.summarize({"execute": [record("m2")]}, {}, usage.empty_quality(), {}, 0, at(5))
        self.assertIsNone(doc["cost"])
        self.assertIsNone(doc["stages"]["execute"]["cost"])
        empty = usage.summarize({}, {}, usage.empty_quality(), {}, 0, at(5), unattributed=[record("m2")])
        self.assertEqual(empty["cost"], 0.0)
        self.assertEqual(empty["unattributed"], {"tokens": 11100, "cost": None})


def ledger(*actions_and_hours, findings=None) -> str:
    events = [{"event_id": f"EV-{i}", "action": action, "timestamp": iso(hour)}
              for i, (action, hour) in enumerate(actions_and_hours)]
    return json.dumps({"events": events, "findings": findings or {}})


class Fixture(unittest.TestCase):
    """A git repo with worktree .planning/worktrees/ep1, epic ep1 with tracks ep1.1 and ep1.2, logs, and fake bd."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(os.path.realpath(self.tmp.name))
        self.repo = base / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "x")
        self.tree = self.repo / ".planning/worktrees/ep1"
        git(self.repo, "worktree", "add", "-q", "-b", "feat/ep1", str(self.tree))
        write(self.repo, ".agent-workflow/config.yaml", "schema_version: '2.8'\nproviders:\n  task_tracking: beads\n")
        refresh(self.repo)
        write(self.repo, usage.PRICES_FILE, "prices:\n  m1: {input: 1, output: 1, cache_read: 1, cache_write: 1}\n")
        store = WorkflowEventStore(self.repo / ".agent-workflow/runtime/events.jsonl")
        approved = {"action": "plan_approved", "decision": {"status": "approved"}}
        for event_type, hour, payload in (("requirement.confirmed", 1, {}), ("approval.recorded", 2, approved),
                                          ("orchestration.ready", 3, {"epic": "ep1"}), ("gate.waived", 3.5, {}),
                                          ("verification.passed", 12, {})):
            store.append(WorkflowEvent.create(event_type=event_type, workflow_id="wf", payload=payload,
                                              timestamp=iso(hour)))
        write(self.tree, ".planning/reviews/ep1.1/review.json",
              ledger(("review-requested", 9.5), ("review-started", 9.55), ("changes-requested", 9.6),
                     ("review-requested", 9.7), ("review-started", 9.72), ("review-approved", 9.75),
                     findings={"F1": {"severity": "IMPORTANT"}, "F2": {"severity": "MINOR"}}))
        self.claude = base / "claude"
        slug = re.sub(r"[^A-Za-z0-9]", "-", str(self.repo))

        def line(msg, hour, cwd, tokens=100):
            return json.dumps({"type": "assistant", "timestamp": iso(hour), "sessionId": "s", "cwd": str(cwd),
                               "gitBranch": "x", "requestId": msg,
                               "message": {"id": msg, "model": "m1", "content": [{"text": SECRET}],
                                           "usage": {"input_tokens": tokens, "output_tokens": 0,
                                                     "cache_read_input_tokens": 0,
                                                     "cache_creation_input_tokens": 0}}}) + "\n"
        write(self.claude, f"{slug}/s.jsonl",
              line("a", 0.5, self.repo, 1) + line("b", 9.25, self.tree, 10) + line("c", 9.6, self.tree, 100)
              + line("d", 10.75, self.tree, 1000) + line("e", 13, self.repo, 10000)
              + line("f", 0.1, self.repo, 100000))
        self.codex = base / "codex-empty"
        self.bin = base / "bin"
        track = {"issue_type": "task", "parent": "ep1"}
        self.rules = [
            {"argv": ["show", "ep1"], "stdout": [{"id": "ep1", "issue_type": "epic", "title": "Epic",
                                                 "started_at": None, "closed_at": None}]},
            {"argv": ["show", "ep1.1"], "stdout": [{"id": "ep1.1", "title": "T1", **track,
                                                   "started_at": iso(9.1), "closed_at": iso(10)}]},
            {"argv": ["show", "ep1.2"], "stdout": [{"id": "ep1.2", "title": "T2", **track,
                                                   "started_at": iso(10.5), "closed_at": iso(11)}]},
            {"argv": ["history", "ep1"], "stdout": []},
            {"argv": ["history", "ep1.1"], "stdout": [
                {"Issue": {"status": "closed", "started_at": iso(9.1)}},
                {"Issue": {"status": "open", "started_at": iso(9.1)}},
                {"Issue": {"status": "closed", "started_at": iso(9)}},
                {"Issue": {"status": "in_progress", "started_at": iso(9)}},
                {"Issue": {"status": "open"}}]},
            {"argv": ["history", "ep1.2"], "stdout": [{"Issue": {"status": "closed", "started_at": iso(10.5)}}]},
            {"argv": ["dep", "list", "ep1", "--direction=up", "--type", "parent-child"],
             "stdout": [{"id": "ep1.1"}, {"id": "ep1.2"}]},
            {"argv": ["dep", "list", "ep1.1", "--direction=up", "--type", "discovered-from"],
             "stdout": [{"id": "b1", "issue_type": "bug"}, {"id": "t9", "issue_type": "task"}]},
            {"argv": ["dep", "list", "ep1.2", "--direction=up", "--type", "discovered-from"], "stdout": []},
            {"argv": ["dep", "list", "ep1", "--direction=up", "--type", "discovered-from"], "stdout": []},
            {"argv": ["update"], "stdout": ""},
        ]
        fake = fake_cli(self.bin, "bd", self.rules)
        patcher = mock.patch.dict(os.environ, path_with(self.bin))
        patcher.start()
        self.addCleanup(patcher.stop)
        resolved = mock.patch("workflow_core.usage.tool", return_value=str(fake))
        resolved.start()
        self.addCleanup(resolved.stop)

    def collect(self, bead: str) -> dict:
        return usage.collect(self.repo, bead, now=at(14), claude_root=self.claude, codex_root=self.codex)

    def written(self) -> list[dict]:
        out = []
        for argv in calls(self.bin):
            if argv[1] == "update":
                self.assertEqual(argv[3], "--set-metadata")
                key, _, value = argv[4].partition("=")
                self.assertEqual(key, "ai_usage")
                out.append((argv[2], value))
        return out


class QualityTests(Fixture):
    def test_quality_of_a_track(self):
        q = usage.quality(self.repo, "ep1.1", workflows={"ep1.1"})
        self.assertEqual(q, {"reopens": 1, "bugs": 1, "review_cycles": 2, "rejections": 1,
                             "findings": {"critical": 0, "important": 1, "minor": 1, "suggestion": 0},
                             "waivers": 0})

    def test_no_ledger_and_waivers_from_workflow(self):
        q = usage.quality(self.repo, "ep1", workflows={"ep1", "wf"})
        self.assertEqual((q["review_cycles"], q["rejections"], q["waivers"]), (0, 0, 1))
        self.assertEqual(q["findings"], usage.empty_quality()["findings"])


class CollectTests(Fixture):
    def test_track_summary_is_written_once_per_run_and_identical(self):
        first = self.collect("ep1.1")
        self.assertEqual(first["stages"], {"execute": {"tokens": 10, "cost": 0.0}, "review": {"tokens": 100, "cost": 0.0001}})
        self.assertEqual(first["quality"]["reopens"], 1)
        self.assertEqual(first["sources"], {"claude_code": "ok", "codex": "not_found"})
        self.collect("ep1.1")
        writes = self.written()
        self.assertEqual([bead for bead, _ in writes], ["ep1.1", "ep1.1"])
        self.assertEqual(writes[0][1], writes[1][1])
        self.assertEqual(json.loads(writes[0][1]), first)
        self.assertNotIn(SECRET, writes[0][1])

    def test_epic_owns_its_stages_children_and_unattributed_in_span(self):
        doc = self.collect("ep1")
        self.assertEqual({stage: value["tokens"] for stage, value in doc["stages"].items()},
                         {"discuss": 100001, "execute": 1010, "review": 100, "ship": 10000})
        self.assertEqual(doc["quality"]["bugs"], 1)
        self.assertEqual(doc["quality"]["review_cycles"], 2)
        self.assertEqual(doc["quality"]["waivers"], 1)
        self.assertEqual(doc["children"], ["ep1.1", "ep1.2"])
        self.assertEqual(doc["unattributed"], {"tokens": 0, "cost": 0.0})

    def test_closed_epic_counts_unattributed_only_until_it_closed(self):
        self.rules[0]["stdout"][0]["closed_at"] = iso(12.5)
        for rule in self.rules:
            if rule["argv"] == ["history", "ep1"]:
                rule["stdout"] = [{"Issue": {"status": "closed"}}]
        fake_cli(self.bin, "bd", self.rules)
        store = WorkflowEventStore(self.repo / ".agent-workflow/runtime/events.jsonl")
        store.append(WorkflowEvent.create(event_type="requirement.confirmed", workflow_id="wf2", timestamp=iso(12.8)))
        doc = self.collect("ep1")
        self.assertNotIn("ship", doc["stages"])
        self.assertEqual(doc["unattributed"], {"tokens": 0, "cost": 0.0})

    def test_collect_from_inside_a_worktree_matches_the_main_checkout(self):
        from_tree = usage.collect(self.tree, "ep1.1", now=at(14), claude_root=self.claude, codex_root=self.codex)
        self.assertEqual(from_tree, self.collect("ep1.1"))
        self.assertEqual(from_tree["stages"]["review"]["tokens"], 100)

    def test_removed_worktree_still_names_its_bead(self):
        git(self.repo, "worktree", "remove", "--force", str(self.tree))
        doc = self.collect("ep1.1")
        # the ledger went with the worktree, so the review-time record counts as execute
        self.assertEqual(doc["stages"], {"execute": {"tokens": 110, "cost": 0.0001}})

    def test_missing_bd_is_a_usage_error(self):
        with mock.patch.dict(os.environ, {"PATH": str(Path(self.tmp.name) / "none")}), \
                mock.patch("workflow_core.usage.tool", return_value=None):
            with self.assertRaises(usage.UsageError):
                self.collect("ep1.1")


class ReportTests(Fixture):
    def rows(self):
        def meta(cost):
            return {"ai_usage": json.dumps({"version": 1, "cost": cost, "models": {"m1": {"input": 1, "output": 0,
                    "cache_read": 0, "cache_write": 0, "cost": cost}}, "stages": {"execute": {"tokens": 1, "cost": cost}},
                    "unpriced": [], "quality": usage.empty_quality(), "unattributed": {"tokens": 5, "cost": 0.5}})}
        return [
            {"id": "ep1", "title": "Epic", "issue_type": "epic", "status": "open", "metadata": meta(3.0)},
            {"id": "ep1.1", "title": "T1", "issue_type": "task", "parent": "ep1", "status": "closed",
             "closed_at": iso(10), "metadata": meta(1.0)},
            {"id": "ep1.2", "title": "T2", "issue_type": "task", "parent": "ep1", "status": "closed",
             "closed_at": iso(11)},
            {"id": "x1", "title": "Other", "issue_type": "task", "status": "closed", "closed_at": "2026-09-01T00:00:00Z",
             "metadata": meta(7.0)},
        ]

    def setUp(self):
        super().setUp()
        self.rules.insert(0, {"argv": ["list", "--all"], "stdout": self.rows()})
        fake_cli(self.bin, "bd", self.rules)

    def test_epic_report_counts_children_inside_the_epic(self):
        out = usage.report(self.repo, epic="ep1")
        self.assertEqual([row["bead"] for row in out["beads"]], ["ep1", "ep1.1"])
        self.assertEqual(out["not_collected"], ["ep1.2"])
        self.assertEqual(out["totals"]["cost"], 3.0)
        self.assertEqual(out["unattributed"], {"tokens": 5, "cost": 0.5})

    def test_milestone_report_covers_its_epics_and_their_tracks(self):
        rows = self.rows()
        rows.append({"id": "m1", "title": "M1", "issue_type": "milestone", "status": "open", "labels": None})
        rows[0]["parent"] = "m1"
        rows.append({"id": "ep2", "title": "Next", "issue_type": "epic", "status": "open", "parent": "m2"})
        rows.append({"id": "ep4", "title": "Unassigned", "issue_type": "epic", "status": "open"})
        self.rules[0]["stdout"] = rows
        fake_cli(self.bin, "bd", self.rules)
        out = usage.report(self.repo, milestone="m1")
        self.assertEqual(["ep1", "ep1.1"], [row["bead"] for row in out["beads"]])
        self.assertEqual(["ep1.2"], out["not_collected"])
        self.assertEqual(3.0, out["totals"]["cost"])
        with self.assertRaisesRegex(usage.UsageError, "ep4 is not a milestone"):
            usage.report(self.repo, milestone="ep4")
        with self.assertRaisesRegex(usage.UsageError, "m9 is not a milestone"):
            usage.report(self.repo, milestone="m9")

    def test_total_is_null_when_nothing_is_priced(self):
        self.rules[0]["stdout"] = [{"id": "u1", "title": "U", "issue_type": "task", "status": "closed",
                                    "metadata": {"ai_usage": json.dumps({"cost": None, "models": {"m9": {
                                        "input": 5, "output": 0, "cache_read": 0, "cache_write": 0, "cost": None}},
                                        "stages": {}, "unpriced": ["m9"]})}}]
        fake_cli(self.bin, "bd", self.rules)
        out = usage.report(self.repo)
        self.assertIsNone(out["totals"]["cost"])
        self.assertEqual(out["unattributed"], {"tokens": 0, "cost": 0.0})
        self.assertEqual(out["unpriced"], ["m9"])

    def test_unpriced_unattributed_cost_is_null(self):
        doc = {"cost": None, "models": {}, "stages": {}, "unpriced": [], "unattributed": {"tokens": 7, "cost": None}}
        self.rules[0]["stdout"] = [{"id": "e9", "title": "E", "issue_type": "epic", "status": "closed",
                                    "metadata": {"ai_usage": json.dumps(doc)}}]
        fake_cli(self.bin, "bd", self.rules)
        self.assertEqual(usage.report(self.repo)["unattributed"], {"tokens": 7, "cost": None})

    def test_since_and_bead(self):
        self.assertEqual([row["bead"] for row in usage.report(self.repo, since=date(2026, 10, 1))["beads"]],
                         ["ep1.1"])
        one = usage.report(self.repo, bead="x1")
        self.assertEqual((one["totals"]["cost"], one["not_collected"]), (7.0, []))

    def test_report_sums_roles_and_skips_beads_without_roles(self):
        doc_with_roles = {
            "version": 1,
            "cost": 2.0,
            "models": {"m1": {"input": 10, "output": 5, "cache_read": 0, "cache_write": 0, "cost": 2.0}},
            "roles": {
                "main": {"m1": {"input": 6, "output": 3, "cache_read": 0, "cache_write": 0, "cost": 1.2}},
                "subagent": {"m1": {"input": 4, "output": 2, "cache_read": 0, "cache_write": 0, "cost": 0.8}},
            },
            "stages": {"execute": {"tokens": 15, "cost": 2.0}},
            "unpriced": [],
            "quality": usage.empty_quality(),
            "unattributed": {"tokens": 0, "cost": 0.0},
        }
        self.rules[0]["stdout"] = [
            {"id": "b1", "title": "B1", "issue_type": "task", "status": "closed",
             "metadata": {"ai_usage": json.dumps(doc_with_roles)}},
            {"id": "b2", "title": "B2", "issue_type": "task", "status": "closed",
             "metadata": {"ai_usage": json.dumps({"version": 1, "cost": 1.0, "models": {"m1": {"input": 1, "output": 0,
                                                   "cache_read": 0, "cache_write": 0, "cost": 1.0}},
                                                   "stages": {"execute": {"tokens": 1, "cost": 1.0}},
                                                   "unpriced": [], "quality": usage.empty_quality(),
                                                   "unattributed": {"tokens": 0, "cost": 0.0}})}},
        ]
        fake_cli(self.bin, "bd", self.rules)
        out = usage.report(self.repo)
        self.assertEqual(out["totals"]["roles"]["main"]["m1"],
                         {"input": 6, "output": 3, "cache_read": 0, "cache_write": 0, "cost": 1.2})
        self.assertEqual(out["totals"]["roles"]["subagent"]["m1"],
                         {"input": 4, "output": 2, "cache_read": 0, "cache_write": 0, "cost": 0.8})


class BudgetTests(Fixture):
    def budget(self, value):
        write(self.repo, ".agent-workflow/config.yaml",
              f"schema_version: '2.8'\nproviders:\n  task_tracking: beads\nusage:\n  budget_usd: {value}\n")

    def test_us2_status_thresholds(self):
        self.assertEqual(usage.budget_status(5.0, [], 10.0), "ok")
        self.assertEqual(usage.budget_status(8.0, [], 10.0), "warn")
        self.assertEqual(usage.budget_status(11.99, [], 10.0), "warn")
        self.assertEqual(usage.budget_status(12.0, [], 10.0), "stop")
        self.assertEqual(usage.budget_status(None, [], 10.0), "ok")

    def test_us2_unpriced_model_makes_the_budget_unenforceable(self):
        self.assertEqual(usage.budget_status(None, ["m9"], 10.0), "unenforceable")
        self.assertEqual(usage.budget_status(50.0, ["m9"], 10.0), "unenforceable")

    def test_us2_epic_collect_stores_the_budget_block(self):
        self.budget(1)
        doc = self.collect("ep1")
        self.assertEqual(doc["budget"], {"budget_usd": 1.0, "cost": doc["cost"], "status": "ok"})
        stored = json.loads(self.written()[-1][1])
        self.assertEqual(stored["budget"], doc["budget"])

    def test_us2_child_collect_writes_no_budget(self):
        self.budget(1)
        self.assertNotIn("budget", self.collect("ep1.1"))

    def test_us2_no_budget_means_no_budget_block(self):
        self.assertNotIn("budget", self.collect("ep1"))
        self.assertIsNone(usage.budget_usd(self.repo))

    def test_us2_budget_must_be_positive(self):
        self.budget(0)
        with self.assertRaises(usage.UsageError):
            usage.budget_usd(self.repo)


if __name__ == "__main__":
    unittest.main()
