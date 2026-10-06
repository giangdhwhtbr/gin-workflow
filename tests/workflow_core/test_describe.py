"""`gin-workflow describe`: collect the graph from Beads, lay it out, render the fixed template (fake bd)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from team_fixtures import calls, fake_cli, path_with  # noqa: E402
from workflow_core import describe  # noqa: E402

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)
PCH, BLK, DISC = "parent-child", "blocks", "discovered-from"


def issue(bead_id: str, title: str | None = None, parent: str | None = None, deps=(), **fields) -> dict:
    row = {"id": bead_id, "title": title or bead_id.upper(), "issue_type": "task", "status": "open", "priority": 2}
    row.update(fields)
    if parent:
        row["parent"] = parent
    row["dependencies"] = [{"id": d, "title": d.upper(), "status": "open", "dependency_type": kind}
                           for d, kind in deps]
    return row


def show_rule(*ids: str, rows: list[dict]) -> dict:
    return {"argv": ["show", *ids, "--json", "--include-comments"], "stdout": rows}


def up_rule(kind: str, *ids: str, rows: list[dict]) -> dict:
    return {"argv": ["dep", "list", *ids, "--direction=up", "--type", kind, "--json"],
            "stdout": [{"id": row, "dependency_type": kind} for row in rows]}


def fixture_rules(*, cycle: bool = False) -> list[dict]:
    g = issue("g", parent=None, issue_type="epic")
    p = issue("p", parent="g", deps=[("g", PCH)])
    e = issue("e", parent="p", deps=[("p", PCH)], issue_type="epic", description="Epic body\n\nline two",
              design="D", acceptance_criteria="A", notes="N", assignee="an", owner="o@x", labels=["l1", "l2"],
              metadata={"k": "v"}, created_at="2026-10-01T00:00:00Z", updated_at="2026-10-02T00:00:00Z",
              close_reason=None,
              comments=[{"id": "c1", "issue_id": "e", "author": "bob", "text": "hello", "created_at": "t1"}])
    e1 = issue("e.1", parent="e", deps=[("e", PCH)])
    e2 = issue("e.2", parent="e", deps=[("e", PCH), ("e.1", BLK), ("x", BLK)])
    e11 = issue("e.1.1", parent="e.1", deps=[("e.1", PCH)])
    b1 = issue("b1", deps=[("e.1.1", DISC)], issue_type="bug")
    b2 = issue("b2", deps=[("e.1", DISC), ("e.2", DISC)], issue_type="bug")
    return [
        show_rule("e", rows=[e]), show_rule("p", rows=[p]), show_rule("g", rows=[g]),
        show_rule("e.1", "e.2", rows=[e1, e2]), show_rule("e.1.1", rows=[e11]),
        show_rule("b1", "b2", rows=[b1, b2]),
        up_rule(PCH, "e", rows=["e.1", "e.2"]), up_rule(PCH, "e.1", "e.2", rows=["e.1.1"]),
        up_rule(PCH, "e.1.1", rows=["e"] if cycle else []),
        up_rule(DISC, "e", "e.1", "e.1.1", "e.2", rows=["b1", "b2"]),
    ]


class CollectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        self.bin = Path(self.tmp.name) / "bin"

    def run_collect(self, rules=None, root="e", **kwargs):
        fake_cli(self.bin, "bd", fixture_rules() if rules is None else rules)
        with mock.patch.dict(os.environ, path_with(self.bin)):
            return describe.collect(self.repo, root, now=NOW, **kwargs)

    def test_collects_tree_ancestors_bugs_and_edges(self):
        graph = self.run_collect()
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertEqual(set(nodes), {"g", "p", "e", "e.1", "e.2", "e.1.1", "b1", "b2"})
        self.assertEqual([node["id"] for node in graph["nodes"]], sorted(nodes))
        roles = {key: node["role"] for key, node in nodes.items()}
        self.assertEqual(roles, {"g": "ancestor", "p": "ancestor", "e": "root", "e.1": "descendant",
                                 "e.2": "descendant", "e.1.1": "descendant", "b1": "bug", "b2": "bug"})
        edges = {(edge["kind"], edge["from"], edge["to"]) for edge in graph["edges"]}
        self.assertEqual(edges, {
            ("parent", "g", "p"), ("parent", "p", "e"), ("parent", "e", "e.1"), ("parent", "e", "e.2"),
            ("parent", "e.1", "e.1.1"), ("blocks", "e.1", "e.2"),
            ("discovered", "e.1.1", "b1"), ("discovered", "e.1", "b2"), ("discovered", "e.2", "b2")})
        self.assertEqual(graph["edges"], sorted(graph["edges"], key=lambda x: (x["kind"], x["from"], x["to"])))
        self.assertEqual(graph["meta"], {"root": "e", "generated_at": "2026-10-05T00:00:00Z", "repo": "repo"})

    def test_node_fields_and_detail(self):
        graph = self.run_collect()
        nodes = {node["id"]: node for node in graph["nodes"]}
        root = nodes["e"]
        self.assertEqual((root["title"], root["type"], root["status"], root["priority"]), ("E", "epic", "open", 2))
        self.assertEqual(root["detail"], {
            "description": "Epic body\n\nline two", "design": "D", "acceptance_criteria": "A", "notes": "N",
            "assignee": "an", "owner": "o@x", "labels": ["l1", "l2"], "metadata": {"k": "v"},
            "created_at": "2026-10-01T00:00:00Z", "updated_at": "2026-10-02T00:00:00Z",
            "comments": [{"author": "bob", "text": "hello", "created_at": "t1"}]})
        self.assertEqual(nodes["e.1"]["detail"], {})

    def test_outside_blockers_are_listed_not_drawn(self):
        graph = self.run_collect()
        nodes = {node["id"]: node for node in graph["nodes"]}
        self.assertNotIn("x", nodes)
        self.assertNotIn("s", nodes)
        self.assertEqual(nodes["e.2"]["detail"]["external_blockers"],
                         [{"id": "x", "title": "X", "status": "open"}])
        self.assertNotIn("external_blockers", nodes["e.1"]["detail"])

    def test_batches_one_show_and_one_dep_list_per_level(self):
        self.run_collect()
        argvs = calls(self.bin)
        shows = [a[2:-2] for a in argvs if a[1] == "show"]
        self.assertEqual(sorted(shows), sorted([["e"], ["p"], ["g"], ["e.1", "e.2"], ["e.1.1"], ["b1", "b2"]]))
        kinds = [a[-2] for a in argvs if a[1] == "dep"]
        self.assertEqual(kinds.count(PCH), 3)
        self.assertEqual(kinds.count(DISC), 1)
        self.assertNotIn(["s"], shows)

    def test_parent_child_cycle_terminates(self):
        graph = self.run_collect(fixture_rules(cycle=True))
        roles = {node["id"]: node["role"] for node in graph["nodes"]}
        self.assertEqual(roles["e"], "root")
        self.assertEqual(len(graph["nodes"]), 8)

    def test_too_large_raises_before_fetching_the_level(self):
        with self.assertRaises(describe.GraphTooLarge) as caught:
            self.run_collect(max_nodes=4)
        self.assertGreater(caught.exception.count, 4)
        self.assertEqual(caught.exception.limit, 4)
        self.assertIn("more than 4 nodes", str(caught.exception))
        self.assertNotIn(["show", "e.1", "e.2", "--json", "--include-comments"], calls(self.bin))

    def test_single_bead_has_one_node_and_no_edges(self):
        graph = self.run_collect([show_rule("t1", rows=[issue("t1")]), up_rule(PCH, "t1", rows=[]),
                                  up_rule(DISC, "t1", rows=[])], root="t1")
        self.assertEqual([node["id"] for node in graph["nodes"]], ["t1"])
        self.assertEqual(graph["edges"], [])

    def test_rows_and_dependencies_without_an_id_are_skipped(self):
        root = issue("t1")
        root["dependencies"] += [{"dependency_type": BLK, "title": "no id"},
                                 {"id": "x", "title": "X", "status": "open", "dependency_type": BLK}]
        graph = self.run_collect([show_rule("t1", rows=[root, {"title": "no id"}]), up_rule(PCH, "t1", rows=[]),
                                  up_rule(DISC, "t1", rows=[])], root="t1")
        self.assertEqual([node["id"] for node in graph["nodes"]], ["t1"])
        self.assertEqual(graph["nodes"][0]["detail"]["external_blockers"],
                         [{"id": "x", "title": "X", "status": "open"}])

    def test_errors(self):
        missing = {"argv": ["show", "zz"], "exit": 1,
                   "stderr": 'Error fetching zz: no issue found matching "zz"\n'}
        with self.assertRaisesRegex(describe.DescribeError, "bd show zz: no such bead"):
            self.run_collect([missing], root="zz")
        with self.assertRaisesRegex(describe.DescribeError, "bd show zz: no such bead"):
            self.run_collect([{"argv": ["show", "zz"], "stdout": []}], root="zz")
        with self.assertRaisesRegex(describe.DescribeError, "printed invalid JSON"):
            self.run_collect([{"argv": ["show"], "stdout": "not json"}])
        with self.assertRaisesRegex(describe.DescribeError, "bd show e failed"):
            self.run_collect([{"argv": ["show"], "exit": 1, "stderr": "boom"}])
        with mock.patch.dict(os.environ, {"PATH": str(Path(self.tmp.name) / "nothing")}):
            with self.assertRaisesRegex(describe.DescribeError, "bd is not installed"):
                describe.collect(self.repo, "e", now=NOW)


class LayoutTests(unittest.TestCase):
    def graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            fake_cli(bin_dir, "bd", fixture_rules())
            with mock.patch.dict(os.environ, path_with(bin_dir)):
                return describe.collect(Path(tmp), "e", now=NOW)

    def positions(self, graph):
        return {node["id"]: (node["x"], node["y"]) for node in graph["nodes"]}

    def test_layout_is_deterministic(self):
        self.assertEqual(self.positions(describe.layout(self.graph())), self.positions(describe.layout(self.graph())))

    def test_rows_slots_and_centering(self):
        at = self.positions(describe.layout(self.graph()))
        self.assertEqual(len(set(at.values())), len(at), "two nodes share a position")
        self.assertEqual(at["e"][1], 0)
        self.assertEqual((at["g"][1], at["p"][1]), (-2, -1))
        self.assertEqual(at["g"][0], at["e"][0])
        self.assertEqual(at["p"][0], at["e"][0])
        self.assertEqual(at["e"][0], (at["e.1"][0] + at["e.2"][0]) / 2)
        self.assertEqual(at["e.1"][0], (at["e.1.1"][0] + at["b2"][0]) / 2)
        self.assertEqual(at["e.1.1"][1], 2)

    def test_a_bug_sits_below_its_smallest_discoverer(self):
        at = self.positions(describe.layout(self.graph()))
        self.assertEqual(at["b1"][1], at["e.1.1"][1] + 1)
        self.assertEqual(at["b2"][1], at["e.1"][1] + 1)

    def test_single_node(self):
        graph = {"meta": {"root": "t"}, "nodes": [{"id": "t", "role": "root"}], "edges": []}
        self.assertEqual(self.positions(describe.layout(graph)), {"t": (0, 0)})

    def test_corrupt_parent_cycle_still_places_every_node(self):
        graph = {"meta": {"root": "r"}, "edges": [{"from": "a", "to": "b", "kind": "parent"},
                                                  {"from": "b", "to": "a", "kind": "parent"}],
                 "nodes": [{"id": "r", "role": "root"}, {"id": "a", "role": "descendant"},
                           {"id": "b", "role": "descendant"}]}
        at = self.positions(describe.layout(graph))
        self.assertEqual(set(at), {"r", "a", "b"})
        self.assertEqual(len(set(at.values())), 3)


class RenderTests(unittest.TestCase):
    PAGE = "<html><script>const DATA = " + describe.PLACEHOLDER + ";</script></html>"

    def test_data_is_embedded_and_html_is_escaped(self):
        title = "</script><img src=x onerror=alert(1)> & <!--"
        graph = {"meta": {"root": "t"}, "edges": [], "nodes": [{"id": "t", "title": title, "role": "root"}]}
        html = describe.render(graph, self.PAGE)
        self.assertNotIn(describe.PLACEHOLDER, html)
        self.assertNotIn("</script><img", html)
        self.assertNotIn("<!--", html)
        self.assertIn("\\u003c/script\\u003e", html)
        start = html.index("const DATA = ") + len("const DATA = ")
        self.assertEqual(json.loads(html[start:html.index(";</script>", start)]), graph)

    def test_template_needs_exactly_one_placeholder(self):
        for page in ("<html></html>", describe.PLACEHOLDER * 2):
            with self.assertRaisesRegex(describe.DescribeError, "placeholder once"):
                describe.render({}, page)

    def test_the_fixed_template_is_offline_and_has_no_html_sinks(self):
        text = describe.template()
        self.assertEqual(text.count(describe.PLACEHOLDER), 1)
        for pattern in (r"""(?:src|href)\s*=\s*["']?https?:""", r"@import", r"""url\(\s*["']?https?:""",
                        r"<link\b", r"<script[^>]+src\s*="):
            self.assertIsNone(re.search(pattern, text), pattern)
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function"):
            self.assertNotIn(sink, text)
        self.assertIn("Back to root", text)
        self.assertIn("white-space: pre-wrap", text)

    def test_the_fixed_template_renders_a_real_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"
            fake_cli(bin_dir, "bd", fixture_rules())
            with mock.patch.dict(os.environ, path_with(bin_dir)):
                graph = describe.layout(describe.collect(Path(tmp), "e", now=NOW))
        html = describe.render(graph, describe.template())
        self.assertNotIn(describe.PLACEHOLDER, html)
        self.assertIn('"root": "e"', html)


if __name__ == "__main__":
    unittest.main()
