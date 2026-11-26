# -*- coding: utf-8 -*-
"""Qt 历史页：真实彩色分支拓扑 + 虚拟化提交表格。"""
from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMenu, QPushButton, QSplitter,
                               QTabWidget, QTableView, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from graph_layout import layout_commits
from ui_qt import theme
from ui_qt.history_graph import HistoryGraph
from ui_qt.widgets import DiffView, confirm, form, input_text


class CommitModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.commits = []

    def set_commits(self, commits) -> None:
        self.beginResetModel()
        self.commits = commits
        self.endResetModel()

    def rowCount(self, _parent=QModelIndex()) -> int:
        return len(self.commits)

    def columnCount(self, _parent=QModelIndex()) -> int:
        return 3

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        commit = self.commits[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            if index.column() == 0:
                return commit.subject
            if index.column() == 1:
                return commit.author
            return commit.date
        if role == Qt.ItemDataRole.UserRole:
            return commit
        if role == Qt.ItemDataRole.ForegroundRole:
            if commit.is_head:
                return QColor(theme.BRIGHT)
            if index.column() == 2:
                return QColor(theme.MUTED)
        if role == Qt.ItemDataRole.ToolTipRole and index.column() == 0:
            return f"{commit.subject}\n{commit.refs or commit.short}"
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ("提交信息", "作者", "日期")[section]
        return None


class RefBar(QWidget):
    """真正的分支/标签徽标行，与提交文本分离，避免长引用挤压主题。"""
    def __init__(self):
        super().__init__()
        self.setFixedHeight(32)
        self.refs = []

    def set_refs(self, refs: str) -> None:
        self.refs = [r.strip() for r in refs.split(",") if r.strip()]
        self.update()

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QPainter
        painter = QPainter(self)
        x = 8
        for ref in self.refs:
            text = ref
            color = theme.GREEN
            if ref.startswith("tag: "):
                text, color = "◆ " + ref[5:], theme.YELLOW
            elif "/" in ref and not ref.startswith("HEAD"):
                color = theme.ACCENT
            text = "⑂ " + text if not ref.startswith("tag:") else text
            width = painter.fontMetrics().horizontalAdvance(text) + 14
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(theme.RAISED))
            painter.drawRoundedRect(x, 3, width, 24, 4, 4)
            painter.setPen(QColor(color))
            painter.drawText(x + 7, 20, text)
            x += width + 6


class LogPage(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app, self.repo = app, None
        self._generation = self._detail_generation = 0
        self.commits = []
        self.history_limit = 200
        self._graph_scroll_lock = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self.splitter)
        main = QWidget()
        top = QVBoxLayout(main)
        top.setContentsMargins(14, 10, 14, 8)
        filters = QHBoxLayout()
        self.branch = QComboBox()
        self.branch.addItem("全部分支")
        self.branch.setMinimumWidth(160)
        self.branch.currentTextChanged.connect(lambda _text: self.refresh())
        filters.addWidget(self.branch)
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索提交信息…")
        self.search.setClearButtonEnabled(True)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(350)
        self.search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda _text: self.search_timer.start())
        filters.addWidget(self.search, 1)
        reload = QPushButton("加载更早")
        reload.setToolTip("每次追加 200 条，保持长历史内存有界")
        reload.clicked.connect(self.load_more)
        filters.addWidget(reload)
        top.addLayout(filters)
        body = QHBoxLayout()
        self.graph = HistoryGraph()
        body.addWidget(self.graph)
        right = QVBoxLayout()
        self.refs = RefBar()
        right.addWidget(self.refs)
        self.model = CommitModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 155)
        self.table.setAlternatingRowColors(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._menu)
        self.table.selectionModel().currentRowChanged.connect(self._select)
        right.addWidget(self.table, 1)
        body.addLayout(right, 1)
        top.addLayout(body, 1)
        self.splitter.addWidget(main)
        self.tabs = QTabWidget()
        self.detail = DiffView()
        self.tabs.addTab(self.detail, "提交详情")
        files = QWidget()
        files_layout = QVBoxLayout(files)
        files_layout.setContentsMargins(0, 0, 0, 0)
        file_split = QSplitter(Qt.Orientation.Horizontal)
        self.files = QTreeWidget()
        self.files.setHeaderLabels(["文件", "状态"])
        self.files.setColumnWidth(0, 400)
        self.files.itemDoubleClicked.connect(self._file_diff)
        file_split.addWidget(self.files)
        self.file_diff = DiffView()
        file_split.addWidget(self.file_diff)
        file_split.setSizes([430, 800])
        files_layout.addWidget(file_split)
        self.tabs.addTab(files, "变更文件")
        self.splitter.addWidget(self.tabs)
        self.splitter.setSizes([470, 300])
        self.graph.commit_selected.connect(self._select_graph)
        self.table.verticalScrollBar().valueChanged.connect(self._sync_graph)
        self.graph.verticalScrollBar().valueChanged.connect(self._graph_scroll)

    def set_repo(self, repo) -> None:
        self.repo = repo
        self._generation += 1
        self.model.set_commits([])
        self.graph.set_rows([], 1)
        self.detail.clear()
        self.files.clear()
        if repo:
            self.refresh()

    def refresh(self) -> None:
        if not self.repo:
            return
        repo = self.repo
        self._generation += 1
        generation = self._generation
        branch = self.branch.currentText()
        search = self.search.text().strip() or None
        limit = self.history_limit

        def work():
            from git_backend import run_git
            commits = repo.log(limit=limit, all_refs=branch in ("全部分支", ""),
                               branch=None if branch in ("全部分支", "") else branch,
                               grep=search)
            branches, _ = repo.branches()
            _, head, _ = run_git(["rev-parse", "HEAD"], repo.path)
            return commits, branches, head.strip()

        def ok(result):
            if generation != self._generation or repo is not self.repo:
                return
            commits, branches, head = result
            previous_sha = self._current().sha if self._current() else ""
            self.commits = commits
            for commit in commits:
                commit.is_head = commit.sha == head
            self.model.set_commits(commits)
            rows, lanes = layout_commits(commits)
            self.graph.set_rows(rows, lanes)
            current = self.branch.currentText()

            self.branch.blockSignals(True)
            self.branch.clear()
            self.branch.addItem("全部分支")
            self.branch.addItems([b.name for b in branches])
            self.branch.setCurrentText(current)
            self.branch.blockSignals(False)
            if commits:
                selected = next((i for i, commit in enumerate(commits)
                                 if commit.sha == previous_sha), 0)
                self.table.selectRow(selected)
            else:
                self.detail.set_content("当前筛选条件下没有提交。")
        self.app.run("读取历史", work, ok, coalesce=True)

    def load_more(self) -> None:
        self.history_limit += 200
        self.refresh()

    def _current(self):
        row = self.table.currentIndex().row()
        return self.commits[row] if 0 <= row < len(self.commits) else None

    def _select_graph(self, row: int) -> None:
        self.table.selectRow(row)
        self.graph.set_selected(row)

    def _sync_graph(self) -> None:
        if self._graph_scroll_lock:
            return
        self._graph_scroll_lock = True
        bar = self.table.verticalScrollBar()
        row_height = self.table.rowHeight(0) if self.model.rowCount() else 32
        self.graph.scroll_to_row(round(bar.value() / max(1, row_height)))
        self._graph_scroll_lock = False

    def _graph_scroll(self, value: int) -> None:
        if self._graph_scroll_lock:
            return
        self._graph_scroll_lock = True
        row = round(value / self.graph.ROW)
        if row >= 0:
            self.table.verticalScrollBar().setValue(row * self.table.rowHeight(0))
        self._graph_scroll_lock = False

    def _select(self, current, _previous=None) -> None:
        commit = self._current()
        if not commit or not self.repo:
            return
        self.graph.set_selected(current.row())
        self.refs.set_refs(commit.refs)
        repo = self.repo
        self._detail_generation += 1
        generation = self._detail_generation

        def work():
            return repo.commit_detail(commit.sha), repo.commit_files(commit.sha)

        def ok(result):
            if generation != self._detail_generation or repo is not self.repo:
                return
            detail, files = result
            self.detail.set_content(detail)
            self.files.clear()
            for file in files:
                item = QTreeWidgetItem([file.path, file.label()])
                item.setData(0, Qt.ItemDataRole.UserRole, file.path)
                self.files.addTopLevelItem(item)
        self.app.run("提交详情", work, ok, coalesce=True)

    def _file_diff(self, item, _column=0) -> None:
        commit = self._current()
        if not commit or not self.repo:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        repo = self.repo
        self.app.run("文件差异", lambda: repo.diff_commit(commit.sha, path),
                     self.file_diff.set_content)

    def _menu(self, point) -> None:
        commit = self._current()
        if not commit:
            return
        menu = QMenu(self)
        menu.addAction("在此提交新建分支…", lambda: self._branch(commit))
        menu.addAction("检出该提交", lambda: self.app.write("检出提交", lambda r: r.checkout(commit.sha)))
        menu.addAction("为此提交打标签…", lambda: self._tag(commit))
        menu.addSeparator()
        menu.addAction("Cherry-pick 到当前分支", lambda: self.app.write("Cherry-pick", lambda r: r.cherry_pick(commit.sha)))
        menu.addAction("还原此提交 (Revert)", lambda: self.app.write("Revert", lambda r: r.revert(commit.sha)))
        menu.addAction("重置当前分支到此提交…", lambda: self._reset(commit))
        menu.addSeparator()
        menu.addAction("复制提交哈希", lambda: self.app.clipboard().setText(commit.sha))
        menu.exec(self.table.viewport().mapToGlobal(point))

    def _branch(self, commit) -> None:
        name = input_text(self, "新建分支", "分支名")
        if name:
            self.app.write("新建分支", lambda r: r.create_branch(name, commit.sha))

    def _tag(self, commit) -> None:
        result = form(self, "新建标签", [("name", "标签名", ""), ("message", "说明", "")])
        if result and result["name"]:
            self.app.write("创建标签", lambda r: r.create_tag(result["name"], result["message"] or None, commit.sha))

    def _reset(self, commit) -> None:
        result = form(self, "重置分支", [("mode", "模式", "mixed", ["soft", "mixed", "hard"])])
        if result and (result["mode"] != "hard" or confirm(self, "硬重置", "硬重置将丢弃未提交更改，不可恢复！", True)):
            self.app.write("重置", lambda r: r.reset(result["mode"], commit.sha))
