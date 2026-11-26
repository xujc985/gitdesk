# -*- coding: utf-8 -*-
"""Qt 通用控件：限量差异高亮、表单、空状态与小型 SVG 图标。"""
from __future__ import annotations

from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                               QFormLayout, QFrame, QLabel, QLineEdit,
                               QMessageBox, QPlainTextEdit, QVBoxLayout, QWidget)

from ui_qt import theme

MAX_PREVIEW = 1_200_000


class DiffHighlighter(QSyntaxHighlighter):
    """按行着色，不构造每行 QTextEdit/HTML，适合大文件预览。"""
    def __init__(self, document):
        super().__init__(document)
        self.formats = {}
        for name, fg, bg in (
            ("add", "#a8dca9", "#1e3429"), ("del", "#efa8a1", "#3b272b"),
            ("hunk", "#81bfff", "#223142"), ("meta", "#c6a3db", ""),
            ("header", "#9dc6f5", ""), ("ctx", theme.TEXT, ""),
        ):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(fg))
            if bg:
                fmt.setBackground(QColor(bg))
            self.formats[name] = fmt

    def highlightBlock(self, text: str) -> None:
        kind = "ctx"
        if text.startswith(("+++", "---")):
            kind = "meta"
        elif text.startswith("@@"):
            kind = "hunk"
        elif text.startswith(("diff ", "commit ", "index ", "Author", "Date",
                              "new file", "deleted file", "rename ")):
            kind = "header"
        elif text.startswith("+"):
            kind = "add"
        elif text.startswith("-"):
            kind = "del"
        self.setFormat(0, len(text), self.formats[kind])


class DiffView(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        from PySide6.QtGui import QFontDatabase
        self.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setMaximumBlockCount(50_000)  # 长期使用时文档块数量有上限
        self.setPlaceholderText("选择文件或提交以查看差异")
        self.highlighter = DiffHighlighter(self.document())

    def set_content(self, text: str) -> None:
        if len(text) > MAX_PREVIEW:
            text = text[:MAX_PREVIEW] + "\n\n… 预览过大，已截断；请用命令行查看完整差异。"
        self.setPlainText(text)
        self.moveCursor(self.textCursor().MoveOperation.Start)


def confirm(parent, title: str, message: str, danger: bool = False) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(message)
    box.setIcon(QMessageBox.Icon.Warning if danger else QMessageBox.Icon.Question)
    yes = box.addButton("确定", QMessageBox.ButtonRole.AcceptRole)
    box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    return box.clickedButton() is yes


def input_text(parent, title: str, label: str, initial: str = "") -> str | None:
    result = form(parent, title, [("value", label, initial)])
    return str(result["value"]).strip() if result else None


def form(parent, title: str, fields: Iterable[tuple], ok_text: str = "确定") -> dict | None:
    dialog = QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setMinimumWidth(470)
    layout = QVBoxLayout(dialog)
    content = QFormLayout()
    content.setSpacing(12)
    widgets = {}
    for item in fields:
        key, label, initial = item[:3]
        options = item[3] if len(item) > 3 else None
        if isinstance(initial, bool):
            widget = QCheckBox()
            widget.setChecked(initial)
        elif isinstance(options, (list, tuple)):
            widget = QComboBox()
            widget.setEditable(True)
            widget.addItems(options)
            widget.setCurrentText(initial)
        else:
            widget = QLineEdit(str(initial or ""))
        widgets[key] = widget
        content.addRow(label, widget)
    layout.addLayout(content)
    buttons = QDialogButtonBox()
    ok = buttons.addButton(ok_text, QDialogButtonBox.ButtonRole.AcceptRole)
    ok.setObjectName("Accent")
    buttons.addButton("取消", QDialogButtonBox.ButtonRole.RejectRole)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    result = {}
    for key, widget in widgets.items():
        if isinstance(widget, QCheckBox):
            result[key] = widget.isChecked()
        elif isinstance(widget, QComboBox):
            result[key] = widget.currentText().strip()
        else:
            result[key] = widget.text().strip()
    return result


def empty_state(title: str, subtitle: str = "") -> QFrame:
    frame = QFrame()
    layout = QVBoxLayout(frame)
    layout.addStretch()
    label = QLabel(title)
    label.setObjectName("Title")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setProperty("muted", True)
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        layout.addWidget(sub)
    layout.addStretch()
    return frame


def select_rows(widget) -> list[int]:
    return sorted({index.row() for index in widget.selectionModel().selectedIndexes()})
