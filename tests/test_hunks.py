# -*- coding: utf-8 -*-
"""逐块 diff 的边界回归测试。"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from diff_hunks import parse_hunks, patch_for_hunks


class DiffHunksTest(unittest.TestCase):
    DIFF = """diff --git a/a.txt b/a.txt
index 1111111..2222222 100644
--- a/a.txt
+++ b/a.txt
@@ -1,2 +1,2 @@
-old1
+new1
 same
@@ -10,2 +10,2 @@
-old2
+new2
 same2
"""

    def test_selected_hunk_keeps_file_header_and_only_selection(self):
        patch = patch_for_hunks(self.DIFF, [1])
        self.assertIn("diff --git", patch)
        self.assertIn("-old2", patch)
        self.assertNotIn("-old1", patch)
        self.assertIn("@@ -10,2 +10,2 @@", patch)

    def test_no_selection_and_empty_diff(self):
        self.assertEqual(parse_hunks(""), [])
        with self.assertRaises(ValueError):
            patch_for_hunks(self.DIFF, [])

    def test_no_newline_at_end_of_file_is_preserved(self):
        text = self.DIFF + "\\ No newline at end of file\n"
        patch = patch_for_hunks(text, [1])
        self.assertIn("\\ No newline at end of file", patch)


if __name__ == "__main__":
    unittest.main()
