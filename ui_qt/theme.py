# -*- coding: utf-8 -*-
"""现代 IntelliJ 风格 Qt 主题；不加载图片或 Web 资源。"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ui_qt.platform import platform_font_families

BG = "#1e2023"
EDITOR = "#191b1e"
PANEL = "#282b30"
RAISED = "#32363d"
HOVER = "#3a414c"
TEXT = "#bdc4cf"
BRIGHT = "#e3e7ee"
MUTED = "#89929f"
ACCENT = "#67a5f8"
SELECT = "#315d8d"
BORDER = "#3a3f47"
GREEN = "#83c68c"
YELLOW = "#d8b66a"
PURPLE = "#c79bdc"
FONT, MONO = platform_font_families()


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    for role, color in (
        (QPalette.ColorRole.Window, BG), (QPalette.ColorRole.Base, EDITOR),
        (QPalette.ColorRole.AlternateBase, PANEL), (QPalette.ColorRole.Button, PANEL),
        (QPalette.ColorRole.Text, TEXT), (QPalette.ColorRole.ButtonText, TEXT),
        (QPalette.ColorRole.WindowText, BRIGHT), (QPalette.ColorRole.Highlight, SELECT),
        (QPalette.ColorRole.HighlightedText, "#ffffff"), (QPalette.ColorRole.ToolTipBase, PANEL),
        (QPalette.ColorRole.ToolTipText, BRIGHT),
    ):
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#626a76"))
    app.setPalette(palette)
    app.setStyleSheet(f"""
        * {{ font-family: '{FONT}', sans-serif; font-size: 13px; }}
        QMainWindow, QDialog {{ background: {BG}; }}
        QMenuBar {{ background: {PANEL}; padding: 2px 6px; }}
        QMenuBar::item {{ padding: 6px 10px; border-radius: 4px; }}
        QMenuBar::item:selected, QMenu::item:selected {{ background: {SELECT}; color: white; }}
        QMenu {{ background: {PANEL}; color: {BRIGHT}; border: 1px solid {BORDER}; padding: 5px; }}
        QMenu::item {{ padding: 7px 28px 7px 12px; border-radius: 4px; }}
        QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 9px; }}
        #Toolbar, #StatusBar {{ background: {PANEL}; border: none; }}
        #Toolbar QLabel {{ color: {MUTED}; padding-right: 6px; }}
        QToolButton, QPushButton {{ background: {RAISED}; color: {TEXT};
            border: none; border-radius: 5px; padding: 6px 11px; }}
        QToolButton:hover, QPushButton:hover {{ background: {HOVER}; color: {BRIGHT}; }}
        QToolButton:pressed, QPushButton:pressed {{ background: {SELECT}; color: white; }}
        QPushButton#Accent {{ background: {ACCENT}; color: #111820; font-weight: 600; padding: 7px 16px; }}
        QPushButton#Accent:hover {{ background: #84b8fa; }}
        QPushButton#Danger {{ background: #653f43; color: #f5bbb7; }}
        QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {{ background: {EDITOR};
            color: {TEXT}; border: 1px solid {BORDER}; border-radius: 5px; padding: 5px;
            selection-background-color: {SELECT}; }}
        QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
        QComboBox::drop-down {{ border: none; width: 22px; }}
        QComboBox QAbstractItemView {{ background: {PANEL}; color: {TEXT};
            selection-background-color: {SELECT}; padding: 5px; }}
        QTreeView, QListView, QTableView {{ background: {EDITOR}; color: {TEXT};
            border: none; outline: none; alternate-background-color: #1d2024;
            selection-background-color: {SELECT}; selection-color: white; }}
        QTreeView::item, QListView::item {{ padding: 4px 5px; border: none; }}
        QTreeView::item:hover, QListView::item:hover {{ background: #282e36; }}
        QHeaderView::section {{ background: {PANEL}; color: {MUTED}; padding: 7px 8px;
            border: none; border-bottom: 1px solid {BORDER}; }}
        QTabWidget::pane {{ border: none; }}
        QTabBar::tab {{ background: {BG}; color: {MUTED}; padding: 9px 18px; border: none; }}
        QTabBar::tab:selected {{ background: {PANEL}; color: {BRIGHT}; border-bottom: 2px solid {ACCENT}; }}
        QTabBar::tab:hover:!selected {{ background: #292d32; color: {TEXT}; }}
        QSplitter::handle {{ background: {BORDER}; width: 2px; height: 2px; }}
        QSplitter::handle:hover {{ background: {ACCENT}; }}
        QScrollBar:vertical {{ background: transparent; width: 9px; margin: 0; }}
        QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 0; }}
        QScrollBar::handle {{ background: #48515d; border-radius: 4px; min-height: 30px; min-width: 30px; }}
        QScrollBar::handle:hover {{ background: #62758d; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QLabel#Title {{ font-size: 24px; font-weight: 600; color: {BRIGHT}; }}
        QLabel#Subtitle, QLabel[muted="true"] {{ color: {MUTED}; }}
        QLabel#Badge {{ color: {ACCENT}; background: {RAISED}; padding: 3px 7px; border-radius: 4px; }}
        QStatusBar {{ background: {PANEL}; color: {MUTED}; }}
        QStatusBar::item {{ border: none; }}
        QToolTip {{ background: {PANEL}; color: {BRIGHT}; border: 1px solid {BORDER}; padding: 5px; }}
        QProgressBar {{ background: {EDITOR}; border: none; height: 4px; text-align: center; }}
        QProgressBar::chunk {{ background: {ACCENT}; }}
    """)
