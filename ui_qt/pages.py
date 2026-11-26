# -*- coding: utf-8 -*-
"""Qt 分支、贮藏和标签页。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QLabel, QMenu,
                               QMessageBox, QPushButton, QSplitter,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ui_qt.widgets import DiffView, confirm, form, input_text


class BranchesPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app, self.repo = app, None
        self._generation = 0
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        buttons = QHBoxLayout()
        for text, fn in (("＋ 新建分支", self._create), ("刷新", self.refresh)):
            button = QPushButton(text)
            button.clicked.connect(fn)
            buttons.addWidget(button)
        buttons.addStretch()
        left_layout.addLayout(buttons)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["分支", "追踪", "最后提交"])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 160)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.itemDoubleClicked.connect(lambda item, _col: self._checkout(item))
        left_layout.addWidget(self.tree, 1)
        splitter.addWidget(left)
        info = QWidget()
        info_layout = QVBoxLayout(info)
        title = QLabel("分支工作流")
        title.setStyleSheet("font-size:18px;font-weight:600;")
        info_layout.addWidget(title)
        self.info = QLabel("双击分支检出；右键可合并、变基、重命名或删除。")
        self.info.setWordWrap(True)
        self.info.setProperty("muted", True)
        info_layout.addWidget(self.info)
        for text, fn in (("合并到当前分支…", self._merge),
                         ("变基当前分支…", self._rebase),
                         ("继续变基", self.app.continue_rebase),
                         ("中止合并 / 变基", self.app.abort_operation)):
            button = QPushButton(text)
            button.clicked.connect(fn)
            info_layout.addWidget(button)
        info_layout.addStretch()
        splitter.addWidget(info)
        splitter.setSizes([720, 300])

    def set_repo(self, repo):
        self.repo = repo
        self.tree.clear()
        if repo:
            self.refresh()

    def refresh(self):
        if not self.repo:
            return
        repo = self.repo
        self._generation += 1
        generation = self._generation

        def ok(result):
            if generation != self._generation or repo is not self.repo:
                return
            local, remote = result
            self.tree.clear()
            for title, branches in (("本地分支", local), ("远程分支", remote)):
                group = QTreeWidgetItem([title, "", ""])
                self.tree.addTopLevelItem(group)
                for branch in branches:
                    track = branch.upstream
                    if branch.ahead or branch.behind:
                        track += f"  ↑{branch.ahead} ↓{branch.behind}"
                    name = ("✓ " if branch.current else "") + branch.name
                    item = QTreeWidgetItem([name, track, branch.last_subject])
                    item.setData(0, Qt.ItemDataRole.UserRole, branch)
                    item.setToolTip(2, f"{branch.last_subject}\n{branch.last_date}")
                    group.addChild(item)
                group.setExpanded(bool(branches))
        self.app.run("读取分支", repo.branches, ok, coalesce=True)

    def _current(self):
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def _checkout(self, item=None):
        branch = item.data(0, Qt.ItemDataRole.UserRole) if item else self._current()
        if branch and not branch.current:
            if branch.remote:
                self.app.write("检出远程分支", lambda r: r.checkout_remote(branch.name))
            else:
                self.app.write("检出分支", lambda r: r.checkout(branch.name))

    def _create(self):
        result = form(self, "新建分支", [("name", "名称", ""), ("start", "起点（留空为当前）", ""),
                                      ("checkout", "立即检出", True)])
        if result and result["name"]:
            self.app.write("新建分支", lambda r: r.create_branch(result["name"], result["start"] or None, result["checkout"]))

    def _menu(self, point):
        branch = self._current()
        if not branch:
            return
        menu = QMenu(self)
        menu.addAction("检出", lambda: self._checkout())
        menu.addAction("合并到当前分支", lambda: self._merge(branch))
        menu.addAction("变基当前分支到此", lambda: self.app.write("变基", lambda r: r.rebase(branch.name)))
        if not branch.remote:
            menu.addAction("重命名…", lambda: self._rename(branch))
            menu.addAction("删除分支…", lambda: self._delete(branch))
        else:
            remote, _, name = branch.name.partition("/")
            menu.addAction("删除远程分支…", lambda: self._delete_remote(name, remote))
        menu.exec(self.tree.viewport().mapToGlobal(point))

    def _merge(self, branch=None):
        branch = branch or self._current()
        if branch:
            result = form(self, "合并分支", [("no_ff", "禁止快进", False), ("squash", "压缩提交", False)])
            if result is not None:
                self.app.write("合并分支", lambda r: r.merge(branch.name, no_ff=result["no_ff"], squash=result["squash"]))

    def _rebase(self):
        branch = self._current()
        if branch:
            self.app.write("变基", lambda r: r.rebase(branch.name))

    def _rename(self, branch):
        name = input_text(self, "重命名分支", "新名称", branch.name)
        if name:
            self.app.write("重命名分支", lambda r: r.rename_branch(branch.name, name))

    def _delete(self, branch):
        if confirm(self, "删除分支", f"删除 {branch.name}？未合并的提交可能丢失。", True):
            self.app.write("删除分支", lambda r: r.delete_branch(branch.name))

    def _delete_remote(self, name, remote):
        if confirm(self, "删除远程分支", f"确定删除 {remote}/{name}？", True):
            self.app.write("删除远程分支", lambda r: r.delete_branch(name, remote=True, remote_name=remote))


class StashPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app, self.repo = app, None
        self._generation = 0
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        for text, fn in (("贮藏更改…", self._push), ("刷新", self.refresh)):
            button = QPushButton(text)
            button.clicked.connect(fn)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["贮藏", "哈希"])
        self.tree.setColumnWidth(0, 400)
        self.tree.itemSelectionChanged.connect(self._select)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        splitter.addWidget(self.tree)
        self.diff = DiffView()
        splitter.addWidget(self.diff)
        splitter.setSizes([420, 850])
        layout.addWidget(splitter, 1)

    def set_repo(self, repo):
        self.repo = repo
        self.tree.clear()
        self.diff.clear()
        if repo:
            self.refresh()

    def refresh(self):
        if self.repo:
            repo = self.repo
            self._generation += 1
            generation = self._generation

            def ok(stashes):
                if generation != self._generation or repo is not self.repo:
                    return
                self.tree.clear()
                for stash in stashes:
                    item = QTreeWidgetItem([stash.message, stash.sha[:8]])
                    item.setData(0, Qt.ItemDataRole.UserRole, stash)
                    self.tree.addTopLevelItem(item)
            self.app.run("读取贮藏", repo.stashes, ok, coalesce=True)

    def _current(self):
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def _select(self):
        stash = self._current()
        if stash and self.repo:
            self.app.run("预览贮藏", lambda: self.repo.stash_show(stash.index, sha=stash.sha), self.diff.set_content)

    def _push(self):
        result = form(self, "贮藏更改", [("message", "说明", ""),
                                      ("untracked", "包含未跟踪文件", False),
                                      ("keep_index", "保留已暂存内容", False)])
        if result is not None:
            self.app.write("贮藏更改", lambda r: r.stash_push(result["message"], result["untracked"], result["keep_index"]))

    def _menu(self, point):
        stash = self._current()
        if not stash:
            return
        menu = QMenu(self)
        menu.addAction("应用 (Apply)", lambda: self.app.write("应用贮藏", lambda r: r.stash_apply(stash.index, sha=stash.sha)))
        menu.addAction("弹出 (Pop)", lambda: self.app.write("弹出贮藏", lambda r: r.stash_apply(stash.index, pop=True, sha=stash.sha)))
        menu.addAction("删除 (Drop)", lambda: self.app.write("删除贮藏", lambda r: r.stash_drop(stash.index, sha=stash.sha)))
        menu.exec(self.tree.viewport().mapToGlobal(point))


class TagsPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app, self.repo = app, None
        self._generation = 0
        layout = QVBoxLayout(self)
        buttons = QHBoxLayout()
        for text, fn in (("＋ 新建标签", self._create), ("刷新", self.refresh)):
            button = QPushButton(text)
            button.clicked.connect(fn)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["标签", "提交", "类型", "说明"])
        self.tree.setColumnWidth(0, 170)
        self.tree.setColumnWidth(1, 100)
        self.tree.setColumnWidth(2, 80)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu)
        layout.addWidget(self.tree, 1)

    def set_repo(self, repo):
        self.repo = repo
        self.tree.clear()
        if repo:
            self.refresh()

    def refresh(self):
        if self.repo:
            repo = self.repo
            self._generation += 1
            generation = self._generation

            def ok(tags):
                if generation != self._generation or repo is not self.repo:
                    return
                self.tree.clear()
                for tag in tags:
                    item = QTreeWidgetItem([tag.name, tag.sha, "附注" if tag.annotated else "轻量", tag.subject])
                    item.setData(0, Qt.ItemDataRole.UserRole, tag)
                    self.tree.addTopLevelItem(item)
            self.app.run("读取标签", repo.tags, ok, coalesce=True)

    def _current(self):
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def _create(self):
        result = form(self, "新建标签", [("name", "标签名", ""), ("target", "目标提交（空为 HEAD）", ""),
                                      ("message", "说明（空为轻量标签）", "")])
        if result and result["name"]:
            self.app.write("创建标签", lambda r: r.create_tag(result["name"], result["message"] or None, result["target"] or None))

    def _menu(self, point):
        tag = self._current()
        if not tag:
            return
        menu = QMenu(self)
        menu.addAction("检出", lambda: self.app.write("检出标签", lambda r: r.checkout(tag.name)))
        menu.addAction("推送到远程…", lambda: self._push(tag))
        menu.addAction("删除标签…", lambda: self._delete(tag))
        menu.exec(self.tree.viewport().mapToGlobal(point))

    def _push(self, tag):
        remotes = self.repo.remotes() if self.repo else []
        result = form(self, "推送标签", [("remote", "远程", "origin",
                                        [remote.name for remote in remotes])])
        if result and result["remote"]:
            self.app.write("推送标签", lambda r: r.push_tag(tag.name, result["remote"]))

    def _delete(self, tag):
        if confirm(self, "删除标签", f"确定删除标签 {tag.name}？远程标签不受影响。", True):
            self.app.write("删除标签", lambda r: r.delete_tag(tag.name))
