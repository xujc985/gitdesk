# -*- coding: utf-8 -*-
"""Qt 并排差异：同步滚动、左右标题、轻量差异高亮。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPlainTextEdit,
                               QSplitter, QVBoxLayout, QWidget)

from ui_qt.widgets import DiffHighlighter
from ui_qt import theme


class SideText(QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMaximumBlockCount(50_000)
        self.highlighter = DiffHighlighter(self.document())
        self.setStyleSheet(f"background:{theme.EDITOR};border:none;")


def show_side_by_side(parent, path: str, left: str, right: str,
                      left_title: str, right_title: str) -> QDialog:
    dialog = QDialog(parent)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    dialog.setWindowTitle(f"并排差异 — {path}")
    dialog.resize(1180, 720)
    if hasattr(parent, "_side_diff_dialog") and parent._side_diff_dialog is not None:
        parent._side_diff_dialog.close()
    parent._side_diff_dialog = dialog
    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(10, 10, 10, 10)
    split = QSplitter(Qt.Orientation.Horizontal)
    left_view, right_view = SideText(), SideText()
    for title, content, widget in ((left_title, left, left_view),
                                   (right_title, right, right_view)):
        panel = QVBoxLayout()
        label = QLabel(title)
        label.setProperty("muted", True)
        panel.addWidget(label)
        widget.setPlainText(content)
        panel.addWidget(widget, 1)
        container = QWidget()
        container.setLayout(panel)
        split.addWidget(container)
    split.setSizes([580, 580])
    layout.addWidget(split, 1)
    scrolling = {"locked": False}

    def sync(source):
        if scrolling["locked"]:
            return
        scrolling["locked"] = True
        target = right_view if source is left_view else left_view
        target.verticalScrollBar().setValue(source.verticalScrollBar().value())
        target.horizontalScrollBar().setValue(source.horizontalScrollBar().value())
        scrolling["locked"] = False
    left_view.verticalScrollBar().valueChanged.connect(lambda _value: sync(left_view))
    right_view.verticalScrollBar().valueChanged.connect(lambda _value: sync(right_view))
    left_view.horizontalScrollBar().valueChanged.connect(lambda _value: sync(left_view))
    right_view.horizontalScrollBar().valueChanged.connect(lambda _value: sync(right_view))
    dialog.show()
    # 只保留一个并排窗口；WA_DeleteOnClose 释放 Qt 文档与高亮资源。
    parent._side_diff_dialog = dialog
    dialog.finished.connect(lambda _code: setattr(parent, "_side_diff_dialog", None))
    return dialog
