# -*- coding: utf-8 -*-
"""GitDesk Qt 主窗口。"""
from __future__ import annotations

import json
import os
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QApplication, QComboBox, QFileDialog, QHBoxLayout,
                               QLabel, QMainWindow, QMessageBox, QPushButton,
                               QProgressBar, QTabWidget, QVBoxLayout, QWidget)

from git_backend import Repo, GitError
from ui_qt import theme
from ui_qt.widgets import form
from ui_qt.tasks import TaskRunner
from ui_qt.changes import ChangesPage
from ui_qt.log import LogPage
from ui_qt.pages import BranchesPage, StashPage, TagsPage

SETTINGS = Path.home() / ".gitdesk" / "settings.json"


class MainWindow(QMainWindow):
    def __init__(self, repo_path: str = ""):
        super().__init__()
        self._closing = False
        self.setWindowTitle("GitDesk")
        from ui_qt.platform import app_icon
        self.setWindowIcon(app_icon())
        self.resize(1360, 860)
        self.setMinimumSize(980, 650)
        self.settings = self._settings()
        self.repo = None
        self.runner = TaskRunner()
        self.runner.task_finished.connect(self._task_done)
        self._pending: dict[str, int] = {}
        self._build_actions()
        self._build_toolbar()
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)
        central_layout.addWidget(self.toolbar_host)
        self.setCentralWidget(central)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.currentChanged.connect(self._page_changed)
        central_layout.addWidget(self.tabs, 1)
        self.pages = []
        self.progress = QProgressBar()
        self.progress.setMaximumWidth(160)
        self.progress.setMaximumHeight(4)
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.memory_label = QLabel("Qt Widgets · 原生轻量")
        self.memory_label.setProperty("muted", True)
        self.statusBar().addPermanentWidget(self.memory_label)
        self.status_label = QLabel("就绪")
        self.statusBar().addWidget(self.status_label, 1)
        self.statusBar().addPermanentWidget(self.progress)
        self._show_welcome()
        geometry = self.settings.get("geometry")
        if geometry:
            try:
                # 旧 tkinter 配置是 "1280x800+0+0"，Qt 需要十六进制；
                # 非 Qt 数据或损坏配置应忽略而不是让启动直接失败。
                self.restoreGeometry(bytes.fromhex(geometry))
            except (ValueError, TypeError):
                self.settings.pop("geometry", None)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(10000)
        self.refresh_timer.timeout.connect(self.refresh_light)
        self.refresh_timer.start()
        if repo_path or self.settings.get("last_repo"):
            self.open_repo(repo_path or self.settings["last_repo"], quiet=True)

    def _settings(self) -> dict:
        try:
            return json.loads(Path(SETTINGS).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_settings(self) -> None:
        try:
            settings_path = Path(SETTINGS)
            settings_path.parent.mkdir(exist_ok=True)
            self.settings["geometry"] = str(self.saveGeometry().toHex(), "ascii")
            settings_path.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        except OSError:
            pass

    def _build_actions(self) -> None:
        for text, shortcut, slot, menu in (
            ("打开仓库…", "Ctrl+O", self.open_dialog, "文件"),
            ("克隆仓库…", "", self.clone_dialog, "文件"),
            ("初始化新仓库…", "", self.init_dialog, "文件"),
            ("刷新", "F5", self.refresh_all, "仓库"),
            ("拉取", "", self.pull_dialog, "仓库"),
            ("推送", "", self.push_dialog, "仓库"),
            ("获取", "", self.fetch, "仓库"),
            ("新建分支…", "Ctrl+Shift+N", self.new_branch_dialog, "分支"),
            ("检出分支…", "", self.checkout_dialog, "分支"),
            ("继续变基", "", self.continue_rebase, "仓库"),
            ("中止合并 / 变基", "", self.abort_operation, "仓库"),
            ("远程仓库管理…", "", self.remote_dialog, "仓库"),
        ):
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(slot)
            menu_bar = self.menuBar()
            # 简化菜单收集：第一次按标题创建，之后直接拿。
            if not hasattr(self, "_menus"):
                self._menus = {}
            if menu not in self._menus:
                self._menus[menu] = menu_bar.addMenu(menu)
            self._menus[menu].addAction(action)
            if shortcut:
                self.addAction(action)

    def _build_toolbar(self) -> None:
        bar = QWidget()
        bar.setObjectName("Toolbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(12, 7, 12, 7)
        row.setSpacing(6)
        actions = [("打开", self.open_dialog), ("克隆", self.clone_dialog),
                   ("刷新", self.refresh_all), ("↓ 拉取", self.pull_dialog),
                   ("↑ 推送", self.push_dialog), ("⇅ 获取", self.fetch),
                   ("＋ 分支", self.new_branch_dialog)]
        for text, slot in actions:
            button = QPushButton(text)
            button.clicked.connect(slot)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            row.addWidget(button)
        row.addStretch()
        self.sync_label = QLabel("")
        self.sync_label.setProperty("muted", True)
        row.addWidget(self.sync_label)
        self.branch = QComboBox()
        self.branch.setMinimumWidth(170)
        self.branch.setToolTip("当前分支 / 检出分支")
        self.branch.activated.connect(self._checkout_selected)
        row.addWidget(self.branch)
        # 工具栏由中央容器持有，不能引用临时 wrapper（会被立即销毁）。
        self.toolbar_host = bar

    def _show_welcome(self) -> None:
        self.runner.set_repo(None)
        for page in self.pages:
            page.set_repo(None)
            self.repo = None
        self.tabs.clear()
        self.pages = []
        self.sync_label.clear()
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        title = QLabel("GitDesk")
        from ui_qt.platform import app_icon, ASSETS
        from PySide6.QtGui import QPixmap
        brand = QLabel()
        brand.setPixmap(QPixmap(str(ASSETS / "gitdesk.png")).scaled(
            92, 92, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(brand)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size:34px;font-weight:600;color:#e3e7ee;")
        layout.addWidget(title)
        subtitle = QLabel("原生 Qt 桌面客户端 · 专注、轻量、好看的 Git 工作流")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setProperty("muted", True)
        layout.addWidget(subtitle)
        layout.addSpacing(24)
        for text, slot in (("打开本地仓库…", self.open_dialog),
                           ("克隆远程仓库…", self.clone_dialog),
                           ("初始化新仓库…", self.init_dialog)):
            button = QPushButton(text)
            button.setFixedWidth(260)
            button.clicked.connect(slot)
            layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
        recent = self.settings.get("recent", [])
        if recent:
            layout.addSpacing(18)
            label = QLabel("最近打开")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setProperty("muted", True)
            layout.addWidget(label)
            for path in recent[:4]:
                button = QPushButton(path)
                button.setMaximumWidth(600)
                button.clicked.connect(lambda _checked=False, p=path: self.open_repo(p))
                layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(2)
        self.tabs.addTab(page, "GitDesk")
        self.branch.clear()
        self.branch.addItem("未打开仓库")

    def _page_changed(self, index):
        if self.repo and 0 <= index < len(self.pages):
            self.pages[index].refresh()

    def open_repo(self, path: str, quiet: bool = False) -> bool:
        if not path or not os.path.isdir(path) or not Repo.is_repo(path):
            if not quiet:
                QMessageBox.warning(self, "GitDesk", f"{path}\n不是有效的 Git 仓库。")
            return False
        repo = Repo(path)
        self.repo = repo
        self.runner.set_repo(repo)
        self.settings["last_repo"] = repo.path
        self.settings["recent"] = [repo.path] + [p for p in self.settings.get("recent", []) if p != repo.path]
        self.settings["recent"] = self.settings["recent"][:8]
        self._save_settings()
        self.tabs.clear()
        self.pages = [ChangesPage(self), LogPage(self), BranchesPage(self),
                      StashPage(self), TagsPage(self)]
        for page, title in zip(self.pages, ("变更", "历史", "分支", "Stash", "标签")):
            self.tabs.addTab(page, title)
        self.setWindowTitle(f"GitDesk — {os.path.basename(repo.path)}")
        for page in self.pages:
            page.set_repo(repo)
        self.refresh_header()
        return True

    def run(self, name, fn, on_ok=None, on_err=None, write=False, coalesce=False):
        if self._closing:
            return None
        if on_err is None:
            on_err = self._error
        task = self.runner.run(name, fn, on_ok, on_err, write, coalesce)
        if task:
            self._pending[name] = self._pending.get(name, 0) + 1
            self.status(name + "…")
            if write:
                self.progress.setRange(0, 0)
                self.progress.show()
        return task

    def _task_done(self, name):
        self._pending[name] = max(0, self._pending.get(name, 0) - 1)
        if not self.runner.busy:
            self.progress.hide()
            self.status("就绪")

    def status(self, text):
        self.status_label.setText(text)

    def _error(self, exc):
        message = str(exc)
        self.status("操作失败")
        QMessageBox.critical(self, "Git 操作失败", message)

    def error(self, exc):
        self._error(exc)

    def write(self, name, fn):
        if not self.repo:
            return
        repo = self.repo

        def ok(result):
            self.status(f"{name}完成")
            if repo is self.repo:
                self.refresh_all()

        def failed(exc):
            self.status(f"{name}失败")
            if repo is self.repo:
                self.refresh_all()
            self.error(exc)
        self.run(name, lambda: fn(repo), ok, on_err=failed, write=True)

    def refresh_all(self):
        if not self.repo:
            return
        for page in self.pages:
            page.refresh()
        self.refresh_header()

    def refresh_light(self):
        if self.repo and not self.runner.busy:
            self.pages[0].refresh()
            self.refresh_header()
            if self.tabs.currentIndex() > 0:
                self.pages[self.tabs.currentIndex()].refresh()

    def refresh_header(self):
        repo = self.repo
        if not repo:
            return

        def work():
            return repo.status(), repo.branches(), repo.current_branch()

        def ok(result):
            if repo is not self.repo:
                return
            status, branches, current = result
            self.sync_label.setText(f"↑{status.ahead} ↓{status.behind}  {status.upstream}")
            self.branch.blockSignals(True)
            self.branch.clear()
            self.branch.addItems([b.name for b in branches[0]])
            self.branch.setCurrentText(current)
            self.branch.blockSignals(False)
        self.run("读取状态", work, ok, coalesce=True)

    def _checkout_selected(self, index):
        if self.repo and self.branch.itemText(index):
            name = self.branch.itemText(index)
            self.write("检出分支", lambda r: r.checkout(name))

    def open_dialog(self):
        path = QFileDialog.getExistingDirectory(self, "选择 Git 仓库")
        if path:
            self.open_repo(path)

    def init_dialog(self):
        path = QFileDialog.getExistingDirectory(self, "选择要初始化的目录")
        if path:
            try:
                Repo.init(path)
                self.open_repo(path)
            except GitError as exc:
                self._error(exc)

    def clone_dialog(self):
        result = form(self, "克隆仓库", [("url", "仓库地址", ""), ("dir", "目标目录", "")], "克隆")
        if not result or not result["url"] or not result["dir"]:
            return
        self.status("正在克隆仓库…")
        self.progress.setRange(0, 0)
        self.progress.show()
        self.run("克隆仓库", lambda: Repo.clone(result["url"], result["dir"]),
                 self.open_repo, write=True)

    def pull_dialog(self):
        if not self.repo:
            return
        result = form(self, "拉取", [("rebase", "使用 rebase", False)], "拉取")
        if result is not None:
            self.write("拉取", lambda r: r.pull(rebase=result["rebase"]))

    def push_dialog(self):
        if not self.repo:
            return
        result = form(self, "推送", [("remote", "远程", "origin"),
                                   ("branch", "目标分支", self.repo.current_branch()),
                                   ("upstream", "设置上游", True),
                                   ("tags", "同时推送标签", False),
                                   ("force", "安全强推 (--force-with-lease)", False)], "推送")
        if result:
            branch = result["branch"]
            if branch.startswith("("):
                branch = "HEAD:refs/heads/master"
            self.write("推送", lambda r: r.push(remote=result["remote"], branch=branch,
                                               set_upstream=result["upstream"], tags=result["tags"], force=result["force"]))

    def fetch(self):
        if self.repo:
            self.write("获取", lambda r: r.fetch())

    def new_branch_dialog(self):
        if self.repo:
            result = form(self, "新建分支", [("name", "分支名", ""), ("start", "起点", ""),
                                           ("checkout", "立即检出", True)])
            if result and result["name"]:
                self.write("新建分支", lambda r: r.create_branch(result["name"], result["start"] or None, result["checkout"]))

    def checkout_dialog(self):
        if self.repo:
            local, remote = self.repo.branches()
            result = form(self, "检出分支", [("target", "目标", "", [b.name for b in local + remote])])
            if result and result["target"]:
                name = result["target"]
                if any(b.name == name and b.remote for b in remote):
                    self.write("检出远程分支", lambda r: r.checkout_remote(name))
                else:
                    self.write("检出分支", lambda r: r.checkout(name))

    def remote_dialog(self):
        if not self.repo:
            return
        result = form(self, "远程仓库", [("action", "操作", "添加", ["添加", "删除", "修改地址"]),
                                      ("name", "名称", "origin"), ("url", "地址", "")])
        if not result:
            return
        def work(repo):
            if result["action"] == "添加":
                return repo.add_remote(result["name"], result["url"])
            if result["action"] == "删除":
                return repo.remove_remote(result["name"])
            return repo.set_remote_url(result["name"], result["url"])
        self.write("远程仓库管理", work)

    def continue_rebase(self):
        if self.repo:
            self.write("继续变基", lambda r: r.rebase_continue())

    def abort_operation(self):
        if not self.repo:
            return
        status = self.repo.status()
        if status.merging:
            self.write("中止合并", lambda r: r.merge_abort())
        elif status.rebasing:
            self.write("中止变基", lambda r: r.rebase_abort())
        else:
            QMessageBox.information(self, "GitDesk", "当前没有进行中的合并或变基。")

    def clipboard(self):
        return QApplication.clipboard()

    def closeEvent(self, event) -> None:
        if self.runner.busy and not os.environ.get("GITDESK_SMOKE_EXIT_MS"):
            answer = QMessageBox.question(
                self, "后台操作进行中",
                "Git 操作尚未结束。等待完成后退出可避免索引锁残留。\n"
                "是否等待并退出？")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self._closing = True
        self._save_settings()
        self.refresh_timer.stop()
        self.runner.shutdown()
        if self.runner.thread.isRunning():
            # 正在执行的 Git 不能被强杀；给用户短暂等待并安全退出线程。
            self.status("正在等待后台 Git 操作完成…")
            self.runner.thread.wait(10000)
        super().closeEvent(event)
