# -*- coding: utf-8 -*-
"""Qt 变更页：工作区分组、暂存、回滚、提交与差异。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QHBoxLayout, QLabel, QMessageBox,
                               QPushButton, QSplitter, QTextEdit, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from ui_qt.widgets import DiffView, confirm


class ChangesPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.repo = None
        self.status = None
        self._generation = 0
        self._diff_generation = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        left = QWidget()
        form = QVBoxLayout(left)
        form.setContentsMargins(14, 12, 8, 12)
        title = QLabel("本地更改")
        title.setStyleSheet("font-weight:600;")
        form.addWidget(title)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["文件", "状态"])
        self.tree.setColumnWidth(0, 390)
        self.tree.setRootIsDecorated(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemSelectionChanged.connect(self._select)
        form.addWidget(self.tree, 1)
        message_title = QLabel("提交信息")
        message_title.setProperty("muted", True)
        form.addWidget(message_title)
        self.message = QTextEdit()
        self.message.setPlaceholderText("输入本次提交的说明…   Ctrl+Enter 提交")
        self.message.setMaximumHeight(92)
        self.message.installEventFilter(self)
        form.addWidget(self.message)
        row = QHBoxLayout()
        self.amend = QCheckBox("修改上一次提交")
        row.addWidget(self.amend)
        row.addStretch()
        self.commit_button = QPushButton("提交")
        self.commit_button.setObjectName("Accent")
        self.commit_button.clicked.connect(self.commit)
        row.addWidget(self.commit_button)
        form.addLayout(row)
        splitter.addWidget(left)
        right = QWidget()
        preview = QVBoxLayout(right)
        preview.setContentsMargins(8, 12, 14, 12)
        diff_bar = QHBoxLayout()
        self.diff_title = QLabel("差异预览")
        self.diff_title.setProperty("muted", True)
        diff_bar.addWidget(self.diff_title, 1)
        self.side_by_side = QCheckBox("并排")
        self.side_by_side.setToolTip("切换统一 diff 与左右并排差异")
        self.side_by_side.toggled.connect(self._toggle_diff_mode)
        diff_bar.addWidget(self.side_by_side)
        preview.addLayout(diff_bar)
        self.diff = DiffView()
        preview.addWidget(self.diff, 1)
        self.conflict_actions = QHBoxLayout()
        self.conflict_label = QLabel("冲突文件：选择保留版本，或手动编辑后暂存")
        self.conflict_label.setProperty("muted", True)
        self.conflict_actions.addWidget(self.conflict_label, 1)
        self.ours_button = QPushButton("保留我方")
        self.ours_button.clicked.connect(lambda: self._resolve("ours"))
        self.theirs_button = QPushButton("保留对方")
        self.theirs_button.clicked.connect(lambda: self._resolve("theirs"))
        self.conflict_actions.addWidget(self.ours_button)
        self.conflict_actions.addWidget(self.theirs_button)
        preview.addLayout(self.conflict_actions)
        self.conflict_label.hide()
        self.ours_button.hide()
        self.theirs_button.hide()
        self._current_file = None
        splitter.addWidget(right)
        splitter.setSizes([450, 900])

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent
        if (watched is self.message and event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.commit()
            return True
        return super().eventFilter(watched, event)

    def set_repo(self, repo) -> None:
        self.repo = repo
        self._generation += 1
        self.tree.clear()
        self.diff.clear()
        self.status = None
        if repo:
            self.refresh()

    def refresh(self) -> None:
        if not self.repo:
            return
        repo = self.repo
        self._generation += 1
        generation = self._generation

        def ok(status) -> None:
            if generation == self._generation and repo is self.repo:
                self.status = status
                self._fill(status)
        self.app.run("读取变更", repo.status, ok, coalesce=True)

    def _fill(self, status) -> None:
        self.tree.clear()
        groups = (("冲突", status.conflicted), ("已暂存", status.staged),
                  ("未暂存的更改", status.unstaged), ("未跟踪", status.untracked))
        for title, files in groups:
            if not files:
                continue
            group = QTreeWidgetItem([f"{title}  ({len(files)})", ""])
            group.setFirstColumnSpanned(True)
            group.setForeground(0, Qt.GlobalColor.lightGray)
            self.tree.addTopLevelItem(group)
            for file in files:
                name = file.path + (f"  ←  {file.orig_path}" if file.orig_path else "")
                item = QTreeWidgetItem([name, file.label()])
                item.setData(0, Qt.ItemDataRole.UserRole, file)
                group.addChild(item)
        self.tree.expandAll()

    def _files(self):
        return [item.data(0, Qt.ItemDataRole.UserRole)
                for item in self.tree.selectedItems()
                if item.data(0, Qt.ItemDataRole.UserRole) is not None]

    def _select(self) -> None:
        files = self._files()
        if not files or not self.repo:
            return
        file = files[0]
        self._current_file = file
        repo = self.repo
        self._current_file = file
        conflict = file.conflicted
        self.conflict_label.setVisible(conflict)
        self.ours_button.setVisible(conflict)
        self.theirs_button.setVisible(conflict)
        self._diff_generation += 1
        generation = self._diff_generation
        self.diff_title.setText(file.path)
        if self.side_by_side.isChecked() and not file.untracked:
            self._load_side_diff(file, repo, generation)
            return

        def work():
            if file.untracked:
                import os
                with open(os.path.join(repo.path, file.path), encoding="utf-8",
                          errors="replace") as handle:
                    content = handle.read(100_000)
                return "新文件（未跟踪）\n\n" + "\n".join("+" + line for line in content.splitlines())
            return repo.diff(file.path, staged=file.staged and not file.unstaged,
                             worktree=file.staged and file.unstaged)

        def ok(text):
            if generation == self._diff_generation and repo is self.repo:
                self.diff.set_content(text)
        self.app.run("查看差异", work, ok, coalesce=True)

    def _menu(self, point) -> None:
        files = self._files()
        if not files:
            return
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        paths = [file.path for file in files]
        if any(file.unstaged or file.untracked for file in files):
            menu.addAction("暂存", lambda: self._write("暂存", lambda r: r.stage(paths)))
        if len(files) == 1 and not files[0].untracked and not files[0].conflicted:
            menu.addAction("逐块暂存…", self._stage_hunks)
        if any(file.staged for file in files):
            menu.addAction("取消暂存", lambda: self._write("取消暂存", lambda r: r.unstage(paths)))
        menu.addSeparator()
        if any(file.unstaged and not file.untracked for file in files):
            menu.addAction("回滚更改…", lambda: self._discard(paths, False))
        if any(file.conflicted for file in files):
            menu.addAction("查看我方 / 对方", lambda: self._show_conflict_sides())
            menu.addAction("保留我方并标记解决", lambda: self._resolve("ours"))
            menu.addAction("保留对方并标记解决", lambda: self._resolve("theirs"))
        if any(file.untracked for file in files):
            menu.addAction("删除文件…", lambda: self._discard(paths, True))
        menu.exec(self.tree.viewport().mapToGlobal(point))

    def _stage_hunks(self) -> None:
        file = self._current_file
        if not file or not self.repo:
            return
        repo = self.repo

        def work():
            return repo.diff(file.path, staged=file.staged and not file.unstaged,
                             worktree=file.staged and file.unstaged)

        def ok(diff):
            from ui_qt.hunks import stage_hunks
            if not stage_hunks(self, self.app, repo, file.path, diff):
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(self, "逐块暂存", "该文件没有可逐块选择的差异。")
        self.app.run("读取差异块", work, ok)

    def _toggle_diff_mode(self, _checked=False) -> None:
        self._select()

    def _load_side_diff(self, file, repo, generation) -> None:
        """并排展示基准/修改后内容；冲突时展示我方/对方。"""
        import os

        def work():
            if file.conflicted:
                left = repo.conflict_file(file.path, "ours")
                right = repo.conflict_file(file.path, "theirs")
                return left, right, "我方 (当前分支)", "对方 (合并分支)"
            base = repo.show_file("HEAD", file.path)
            with open(os.path.join(repo.path, file.path), encoding="utf-8",
                      errors="replace") as handle:
                current = handle.read()
            return base, current, "HEAD", "工作区"

        def ok(result):
            if generation != self._diff_generation or repo is not self.repo:
                return
            left, right, left_title, right_title = result
            from ui_qt.diff_split import show_side_by_side
            show_side_by_side(self, file.path, left, right, left_title, right_title)
        self.app.run("并排差异", work, ok, coalesce=True)

    def _show_conflict_sides(self) -> None:
        if self._current_file and self._current_file.conflicted:
            self._load_side_diff(self._current_file, self.repo,
                                 self._diff_generation)

    def _resolve(self, side: str) -> None:
        file = self._current_file
        if not file or not file.conflicted:
            return
        title = "保留我方" if side == "ours" else "保留对方"
        if confirm(self, title, f"将使用{title}版本覆盖 {file.path}，并标记冲突已解决？"):
            self.app.write("解决冲突", lambda repo: repo.resolve_conflict(file.path, side))

    def _write(self, name, fn) -> None:
        self.app.write(name, fn)

    def _discard(self, paths, untracked) -> None:
        if confirm(self, "确认回滚", f"将丢弃 {len(paths)} 个文件的更改，不可恢复。", True):
            self._write("回滚更改", lambda r: r.discard(paths, untracked=untracked))

    def commit(self) -> None:
        if not self.repo:
            return
        message = self.message.toPlainText().strip()
        if not message and not self.amend.isChecked():
            QMessageBox.information(self, "提交", "请输入提交信息。")
            return
        if self.status and not self.status.staged and not self.amend.isChecked():
            if not self.status.unstaged and not self.status.untracked:
                QMessageBox.information(self, "提交", "没有可提交的更改。")
                return
            if not confirm(self, "提交全部更改", "没有已暂存更改。是否暂存全部并提交？"):
                self.commit_button.setEnabled(True)
                return

            def work(repo):
                repo.stage_all()
                return repo.commit(message, self.amend.isChecked())
        else:
            work = lambda repo: repo.commit(message, self.amend.isChecked())

        repo = self.repo
        if repo is None:
            return
        self.commit_button.setEnabled(False)

        def ok(_result):
            if repo is self.repo:
                self.message.clear()
                self.amend.setChecked(False)
                self.app.status("提交完成")
                self.app.refresh_all()
            self.commit_button.setEnabled(True)

        def failed(exc):
            self.commit_button.setEnabled(True)
            self.app.error(exc)
        self.app.run("提交", lambda: work(repo), ok, on_err=failed, write=True)
