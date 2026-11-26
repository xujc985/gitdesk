# -*- coding: utf-8 -*-
"""逐块暂存对话框：选择 diff hunk，只更新 Git 暂存区。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QLabel, QListWidget,
                               QListWidgetItem, QPushButton, QVBoxLayout)

from diff_hunks import parse_hunks, patch_for_hunks
from ui_qt.widgets import DiffView, confirm


class HunkDialog(QDialog):
    def __init__(self, parent, app, repo, path: str, diff: str):
        super().__init__(parent)
        self.app, self.repo, self.path, self.diff = app, repo, path, diff
        self.hunks = parse_hunks(diff)
        self.setWindowTitle(f"逐块暂存 — {path}")
        self.resize(900, 650)
        layout = QVBoxLayout(self)
        label = QLabel("选择要加入暂存区的代码块。工作区内容不会改变。")
        label.setProperty("muted", True)
        layout.addWidget(label)
        self.list = QListWidget()
        for hunk in self.hunks:
            item = QListWidgetItem(f"{hunk.index + 1}. {hunk.header}")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, hunk)
            self.list.addItem(item)
        self.list.itemSelectionChanged.connect(self._preview)
        layout.addWidget(self.list, 1)
        self.preview = DiffView()
        layout.addWidget(self.preview, 2)
        buttons = QDialogButtonBox()
        apply = buttons.addButton("暂存选中代码块", QDialogButtonBox.ButtonRole.AcceptRole)
        apply.setObjectName("Accent")
        buttons.addButton("取消", QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _preview(self) -> None:
        item = self.list.currentItem()
        if item:
            self.preview.set_content(item.data(Qt.ItemDataRole.UserRole).patch)

    def selected_patch(self) -> str:
        indices = []
        for row in range(self.list.count()):
            item = self.list.item(row)
            if item.checkState() == Qt.CheckState.Checked:
                indices.append(item.data(Qt.ItemDataRole.UserRole).index)
        return patch_for_hunks(self.diff, indices)


def stage_hunks(parent, app, repo, path: str, diff: str) -> bool:
    if not parse_hunks(diff):
        return False
    dialog = HunkDialog(parent, app, repo, path, diff)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return False
    patch = dialog.selected_patch()
    app.write("逐块暂存", lambda r: r.apply_patch_cached(patch))
    return True
