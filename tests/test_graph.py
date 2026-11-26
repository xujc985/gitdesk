# -*- coding: utf-8 -*-
"""彩色历史布局与 Git 路径解析的回归测试。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from git_backend import Commit
from graph_layout import layout_commits


def c(sha, parents=()):
    return Commit(sha, sha[:7], sha, "测试", "t@example.com", "", parents=list(parents))


class GraphLayoutTest(unittest.TestCase):
    def test_linear_history(self):
        rows, lanes = layout_commits([c("c", ["b"]), c("b", ["a"]), c("a")])
        self.assertEqual([r.column for r in rows], [0, 0, 0])
        self.assertEqual([r.color_index for r in rows], [0, 0, 0])
        self.assertEqual(lanes, 1)
        self.assertEqual(rows[0].edges[0].to_row, 1)

    def test_diverged_branches_have_distinct_colors(self):
        rows, lanes = layout_commits([
            c("d", ["b"]), c("c", ["a"]), c("b", ["a"]), c("a")])
        self.assertGreaterEqual(lanes, 2)
        self.assertNotEqual(rows[0].color_index, rows[1].color_index)
        self.assertEqual(rows[2].column, rows[0].column)

    def test_merge_connects_both_parents(self):
        rows, _ = layout_commits([
            c("m", ["b", "c"]), c("c", ["a"]), c("b", ["a"]), c("a")])
        self.assertTrue(rows[0].merge)
        self.assertEqual(len(rows[0].edges), 2)
        self.assertEqual({e.to_row for e in rows[0].edges}, {1, 2})
        self.assertEqual(rows[0].edges[0].to_col, rows[2].column)
        self.assertEqual(rows[0].edges[1].to_col, rows[1].column)

    def test_sibling_merge_uses_distinct_second_parent_lane(self):
        rows, lanes = layout_commits([
            c("h", ["a"]), c("m", ["a", "b"]), c("a"), c("b")])
        merge = rows[1]
        self.assertEqual(merge.edges[0].to_col, 0)
        self.assertNotEqual(merge.edges[1].to_col, merge.column)
        self.assertGreaterEqual(lanes, 3)
        self.assertEqual(merge.edges[1].to_row, 3)

    def test_empty_and_truncated_history(self):
        rows, lanes = layout_commits([])
        self.assertEqual((rows, lanes), ([], 1))
        rows, _ = layout_commits([c("c", ["not-loaded"])])
        self.assertEqual(rows[0].edges[0].to_row, -1)


if __name__ == "__main__":
    unittest.main()
