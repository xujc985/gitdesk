# -*- coding: utf-8 -*-
"""Qt 彩色提交图：QGraphics 仅保留可见提交与连线，长历史内存有界。"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView

from graph_layout import PALETTE
from ui_qt import theme


class HistoryGraph(QGraphicsView):
    commit_selected = Signal(int)
    LANE, ROW = 24, 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = []
        self.selected = -1
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setBackgroundBrush(QColor(theme.EDITOR))
        self.setMinimumWidth(58)
        self.setMaximumWidth(240)

    def set_rows(self, rows, lanes: int) -> None:
        self.rows = rows
        width = max(58, lanes * self.LANE + 16)
        self.setFixedWidth(min(240, width))
        self.scene().setSceneRect(0, 0, width, len(rows) * self.ROW + 20)
        self.rebuild()

    def set_selected(self, row: int) -> None:
        self.selected = row
        self.rebuild()

    def rebuild(self) -> None:
        self.scene().clear()
        if not self.rows:
            return
        rect = self.viewport().rect()
        top_left = self.mapToScene(rect.topLeft())
        bottom_left = self.mapToScene(rect.bottomLeft())
        first = max(0, int(top_left.y() // self.ROW) - 3)
        last = min(len(self.rows), int(bottom_left.y() // self.ROW) + 4)
        for index in range(first, last):
            row = self.rows[index]
            y = index * self.ROW + self.ROW / 2
            for edge in row.edges:
                x1, x2 = 14 + edge.from_col * self.LANE, 14 + edge.to_col * self.LANE
                target_row = edge.to_row if edge.to_row >= 0 else len(self.rows)
                # 父子提交跨出当前视口时，仅绘制可见区段，不构造
                # 跨越数百/数千行的曲线，避免旧线弯折或看似消失。
                if target_row > index + 1:
                    if index > last or target_row < first:
                        continue
                    y_start = y
                    # 父提交在可视区域外时，线继续延伸出视口，而不是消失。
                    y_end = min(target_row, last) * self.ROW + self.ROW / 2
                else:
                    y_start = y
                    y_end = target_row * self.ROW + self.ROW / 2
                color = QColor(PALETTE[edge.color_index % len(PALETTE)])
                pen = QPen(color, 1.8)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                path = QPainterPath()
                path.moveTo(x1, y_start)
                if x1 == x2:
                    path.lineTo(x1, y_end)
                else:
                    bend = min(12, abs(y_end - y_start) / 3)
                    path.lineTo(x1, y_start + bend)
                    path.cubicTo(x1, y_end - bend, x2, y_start + bend, x2, y_end)
                self.scene().addPath(path, pen)
        for index in range(first, last):
            row = self.rows[index]
            x, y = 14 + row.column * self.LANE, index * self.ROW + self.ROW / 2
            color = QColor(PALETTE[row.color_index % len(PALETTE)])
            if index == self.selected:
                self.scene().addEllipse(QRectF(x - 8, y - 8, 16, 16),
                                        QPen(QColor(theme.BRIGHT), 1), Qt.BrushStyle.NoBrush)
            self.scene().addEllipse(QRectF(x - 4, y - 4, 8, 8),
                                    QPen(QColor(theme.EDITOR), 1), color)
            if row.head:
                self.scene().addEllipse(QRectF(x - 7, y - 7, 14, 14),
                                        QPen(color, 1.8), Qt.BrushStyle.NoBrush)

    def scroll_to_row(self, row: int) -> None:
        """让指定提交行位于视口顶部，与提交表格逐行对齐。"""
        self.verticalScrollBar().setValue(max(0, row * self.ROW))
        self.rebuild()

    def mousePressEvent(self, event) -> None:
        row = int(self.mapToScene(event.position().toPoint()).y() // self.ROW)
        if 0 <= row < len(self.rows):
            self.commit_selected.emit(row)
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.rebuild()
