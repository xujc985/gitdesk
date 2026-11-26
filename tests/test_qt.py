# -*- coding: utf-8 -*-
"""Qt 无头集成测试：QApplication + 真实仓库 + 实际后台线程。"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import git_backend as gb


class QtIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        # offscreen 使用 Qt 自带字体目录，避免扫描系统字体导致插件警告。
        from PySide6.QtWidgets import QApplication
        cls.qt = QApplication.instance() or QApplication([])
        from ui_qt import theme
        theme.apply(cls.qt)

    def setUp(self):
        import ui_qt.main as main_mod
        self.main_mod = main_mod
        self.temp = tempfile.mkdtemp(prefix="gitdesk-qt-")
        self.addCleanup(shutil.rmtree, self.temp, True)
        self.path = os.path.join(self.temp, "repo")
        os.makedirs(self.path)
        gb.Repo.init(self.path)
        self.repo = gb.Repo(self.path)
        self.repo.config_set("user.name", "Qt 测试")
        self.repo.config_set("user.email", "qt@test.local")
        self.repo.config_set("commit.gpgsign", "false")
        self.repo.git(["symbolic-ref", "HEAD", "refs/heads/master"])
        with open(os.path.join(self.path, "readme.md"), "w", encoding="utf-8") as f:
            f.write("# Qt\n")
        self.repo.stage_all()
        self.repo.commit("初始提交")
        main_mod.SETTINGS = os.path.join(self.temp, "settings.json")
        self.window = main_mod.MainWindow()
        self.addCleanup(self._close)
        self.assertTrue(self.window.open_repo(self.path))
        self.wait()

    def _close(self):
        self.window.runner.shutdown()
        self.window.close()
        self.window.deleteLater()
        self.qt.processEvents()

    def wait(self, seconds=0.1, condition=None, timeout=15):
        deadline = time.monotonic() + timeout
        until = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.qt.processEvents()
            if condition and condition():
                return
            if not condition and time.monotonic() > until:
                return
            time.sleep(0.015)
        if condition:
            self.fail("等待 Qt 后台任务超时")

    def test_application_icon_and_platform_assets(self):
        from ui_qt.platform import app_icon, platform_font_families, ASSETS
        self.assertFalse(app_icon().isNull())
        self.assertFalse(self.window.windowIcon().isNull())
        self.assertTrue((ASSETS / "gitdesk.svg").is_file())
        self.assertTrue((ASSETS / "gitdesk.png").is_file())
        self.assertTrue((ASSETS / "gitdesk.ico").is_file())
        self.assertEqual(self.window.windowIcon().pixmap(64, 64).width(), 64)
        ui, mono = platform_font_families()
        self.assertTrue(ui and mono)

    def test_all_pages_and_history(self):
        self.assertEqual(self.window.tabs.count(), 5)
        log = self.window.pages[1]
        self.wait(condition=lambda: len(log.commits) == 1)
        self.assertEqual(log.table.model().rowCount(), 1)
        self.assertEqual(len(log.graph.rows), 1)
        self.wait(condition=lambda: self.window.branch.currentText() == "master")
        self.assertIn("master", self.window.branch.currentText())

    def test_change_commit_workflow(self):
        with open(os.path.join(self.path, "new.txt"), "w", encoding="utf-8") as f:
            f.write("new content\n")
        page = self.window.pages[0]
        page.refresh()
        self.wait(condition=lambda: page.status is not None and bool(page.status.untracked))
        self.assertEqual(len(page.status.untracked), 1)
        self.repo.stage_all()
        page.refresh()
        self.wait(condition=lambda: page.status is not None and bool(page.status.staged))
        page.message.setPlainText("Qt 新增文件")
        page.commit()
        self.wait(condition=lambda: page.message.toPlainText() == "")
        self.wait(condition=lambda: not self.window.runner.busy)
        self.assertEqual(page.message.toPlainText(), "")
        self.assertEqual(self.repo.log(all_refs=False)[0].subject, "Qt 新增文件")

    def test_branches_stash_tags(self):
        self.repo.create_branch("feature/ui", checkout=False)
        self.repo.create_tag("v1.0", message="首版")
        with open(os.path.join(self.path, "readme.md"), "a", encoding="utf-8") as f:
            f.write("stash\n")
        self.repo.stash_push("测试贮藏")
        for index in (2, 3, 4):
            self.window.pages[index].refresh()
        self.wait(condition=lambda: self.window.pages[2].tree.topLevelItemCount() > 0)
        self.wait(condition=lambda: self.window.pages[3].tree.topLevelItemCount() == 1)
        self.wait(condition=lambda: self.window.pages[4].tree.topLevelItemCount() == 1)
        branches = self.window.pages[2]
        self.assertEqual(branches.tree.topLevelItem(0).childCount(), 2)
        self.assertEqual(self.window.pages[3].tree.topLevelItem(0).text(0).find("测试贮藏") >= 0, True)
        self.assertEqual(self.window.pages[4].tree.topLevelItem(0).text(0), "v1.0")

    def test_long_history_virtualization_and_diff_limit(self):
        log = self.window.pages[1]
        self.assertEqual(log.history_limit, 200)
        log.load_more()
        self.assertEqual(log.history_limit, 400)
        from ui_qt.widgets import MAX_PREVIEW
        diff = self.window.pages[0].diff
        diff.set_content("x" * (MAX_PREVIEW + 100))
        self.assertLess(len(diff.toPlainText()), MAX_PREVIEW + 200)
        self.assertIn("已截断", diff.toPlainText())

    def test_worker_actually_runs_off_gui_thread(self):
        from PySide6.QtCore import QThread
        seen = []
        self.window.run("线程验证", lambda: seen.append(QThread.currentThread()) or "ok",
                        lambda _result: seen.append(QThread.currentThread()))
        self.wait(condition=lambda: len(seen) == 2 and not self.window.runner.busy)
        self.assertIsNot(seen[0], self.qt.thread())
        self.assertIs(seen[1], self.qt.thread())
        self.assertFalse(self.window.runner.busy)

    def test_legacy_geometry_is_ignored(self):
        import json
        with open(self.main_mod.SETTINGS, "w", encoding="utf-8") as f:
            json.dump({"geometry": "1280x800+0+0", "recent": []}, f)
        window = self.main_mod.MainWindow()
        self.addCleanup(lambda: (window.runner.shutdown(), window.close(), window.deleteLater()))
        self.assertNotIn("geometry", window.settings)

    def test_new_repo_callbacks_are_not_dropped(self):
        other = os.path.join(self.temp, "other")
        gb.Repo.init(other)
        repo = gb.Repo(other)
        repo.config_set("user.name", "Other")
        repo.config_set("user.email", "other@test.local")
        repo.git(["symbolic-ref", "HEAD", "refs/heads/main"])
        with open(os.path.join(other, "other.txt"), "w", encoding="utf-8") as f:
            f.write("other\n")
        repo.stage_all()
        repo.commit("另一个仓库")
        self.assertTrue(self.window.open_repo(other))
        self.wait(condition=lambda: len(self.window.pages[1].commits) == 1)
        self.assertEqual(self.window.pages[1].commits[0].subject, "另一个仓库")
        self.wait(condition=lambda: self.window.branch.currentText() == "main")
        self.assertEqual(os.path.realpath(self.window.repo.path), os.path.realpath(other))

    def test_failed_commit_keeps_message(self):
        page = self.window.pages[0]
        with open(os.path.join(self.path, "will-fail.txt"), "w", encoding="utf-8") as f:
            f.write("制造一次真实提交，验证身份错误时保留输入\n")
        page.refresh()
        self.wait(condition=lambda: page.status is not None
                  and any(f.path == "will-fail.txt" for f in page.status.untracked))
        page.message.setPlainText("不能丢失的提交说明")
        self.repo.config_set("user.name", "")
        errors = []
        page.app.error = errors.append
        import ui_qt.changes as changes_mod
        original_confirm = changes_mod.confirm
        changes_mod.confirm = lambda *args, **kwargs: True
        self.addCleanup(lambda: setattr(changes_mod, "confirm", original_confirm))
        page.commit()
        self.wait(condition=lambda: not self.window.runner.busy)
        self.assertEqual(page.message.toPlainText(), "不能丢失的提交说明")
        self.assertTrue(page.commit_button.isEnabled())
        self.assertTrue(errors)

    def test_shutdown_drains_queued_tasks(self):
        from ui_qt.tasks import TaskRunner
        runner = TaskRunner()
        runner.set_repo(self.repo)
        completed = []
        for i in range(3):
            runner.run(f"退出队列{i}", lambda i=i: completed.append(i),
                       lambda _result: None)
        runner.shutdown()
        self.assertEqual(completed, [0, 1, 2])
        self.assertFalse(runner.thread.isRunning())
        self.assertFalse(runner.busy)

    def test_graph_keeps_edges_when_scrolling_history(self):
        from graph_layout import GraphRow, GraphEdge
        rows = [GraphRow(f"new", 0, 0, [GraphEdge(0, 0, 70, 0)])]
        rows += [GraphRow(f"c{i}", 0, 0, [GraphEdge(0, 0, i + 1, 0)]) for i in range(1, 70)]
        rows += [GraphRow("old", 0, 0, [])]
        graph = self.window.pages[1].graph
        graph.set_rows(rows, 1)
        graph.resize(80, 240)
        graph.scroll_to_row(55)
        self.assertGreater(len(graph.scene().items()), 0)
        from PySide6.QtWidgets import QGraphicsPathItem
        paths = [item for item in graph.scene().items() if isinstance(item, QGraphicsPathItem)]
        self.assertTrue(paths, "滚动后仍应存在跨屏分支连线")
        self.assertEqual(graph.verticalScrollBar().value(), 55 * graph.ROW)

    def test_conflict_ui_resolution(self):
        self.repo.create_branch("side")
        with open(os.path.join(self.path, "readme.md"), "w") as f:
            f.write("side\n")
        self.repo.stage_all()
        self.repo.commit("side")
        self.repo.checkout("master")
        with open(os.path.join(self.path, "readme.md"), "w") as f:
            f.write("master\n")
        self.repo.stage_all()
        self.repo.commit("master")
        with self.assertRaises(gb.GitError):
            self.repo.merge("side")
        page = self.window.pages[0]
        page.refresh()
        self.wait(condition=lambda: page.status is not None and bool(page.status.conflicted))
        page.tree.topLevelItem(0).child(0).setSelected(True)
        import ui_qt.changes as changes_mod
        original_confirm = changes_mod.confirm
        changes_mod.confirm = lambda *args, **kwargs: True
        self.addCleanup(lambda: setattr(changes_mod, "confirm", original_confirm))
        self.assertTrue(page.ours_button.isVisible() or not page.ours_button.isHidden())
        page._resolve("theirs")
        self.wait(condition=lambda: not self.repo.status().conflicted)
        with open(os.path.join(self.path, "readme.md"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "side\n")

    def test_color_graph_merge(self):
        self.repo.create_branch("feature")
        with open(os.path.join(self.path, "feature.txt"), "w") as f:
            f.write("feature\n")
        self.repo.stage_all()
        self.repo.commit("功能分支")
        self.repo.checkout("master")
        with open(os.path.join(self.path, "main.txt"), "w") as f:
            f.write("main\n")
        self.repo.stage_all()
        self.repo.commit("主线提交")
        self.repo.merge("feature", no_ff=True, message="合并功能")
        log = self.window.pages[1]
        log.refresh()
        self.wait(condition=lambda: len(log.commits) >= 4)
        self.assertTrue(any(row.merge for row in log.graph.rows))
        self.assertGreaterEqual(len(log.graph.rows[0].edges), 2)


if __name__ == "__main__":
    unittest.main()
