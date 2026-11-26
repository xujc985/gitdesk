# -*- coding: utf-8 -*-
"""GitDesk Qt 原生桌面客户端启动入口（含启动错误诊断）。"""
from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LOG_FILE = os.path.join(os.path.expanduser("~"), ".gitdesk", "startup-error.log")

if getattr(sys, "frozen", False) and sys.platform == "win32":
    # 打包后的普通用户目录优先使用 %LOCALAPPDATA%，避免只读安装位置。
    LOG_FILE = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
                            "GitDesk", "startup-error.log")


def report_startup_error() -> None:
    """pythonw 没有控制台，启动失败也要留下日志并给出可见提示。"""
    text = traceback.format_exc()
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(f"\n[{datetime.now().isoformat()}]\n{text}")
    except OSError:
        pass
    try:
        if sys.platform == "win32":
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "GitDesk 启动失败。请查看日志：\n" + LOG_FILE + "\n\n" + text[-1800:],
                "GitDesk 启动错误", 0x10)
        else:
            print(text, file=sys.stderr)
    except Exception:
        pass


try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    print("GitDesk 需要 PySide6。请先运行：python -m pip install -r requirements.txt",
          file=sys.stderr)
    report_startup_error()
    raise SystemExit(1)

from ui_qt import theme
from ui_qt.main import MainWindow
from ui_qt.platform import app_icon, prepare_environment


def main() -> int:
    # 高 DPI 由 Qt 自动处理，不需要 WebView 或额外原生库。
    prepare_environment()
    app = QApplication(sys.argv)
    app.setApplicationName("GitDesk")
    app.setOrganizationName("GitDesk")
    app.setWindowIcon(app_icon())
    theme.apply(app)
    window = MainWindow(sys.argv[1] if len(sys.argv) > 1 else "")
    window.show()
    # 打包/开发冒烟测试：只验证真实启动与数据，不创建/修改提交。
    if os.environ.get("GITDESK_SMOKE_EXIT_MS"):
        print("SMOKE: enabled", flush=True)
        from PySide6.QtCore import QTimer

        def smoke_report() -> None:
            import json
            import PySide6
            log = os.environ.get("GITDESK_SMOKE_LOG")
            if log:
                print(f"SMOKE: repo={window.repo.path if window.repo else None} log={log}", flush=True)
            if log and window.repo:
                log_page = window.pages[1]
                if not log_page.commits:
                    # 后台历史尚未加载完成，最多再等 10 秒；不提前生成失败报告。
                    QTimer.singleShot(250, smoke_report)
                    return
                payload = {
                    "status": "ok", "repository": window.repo.path,
                    "history": len(log_page.commits),
                    "icon": not window.windowIcon().isNull(),
                    "qt": PySide6.__version__,
                    "platform": sys.platform,
                }
                try:
                    with open(log, "w", encoding="utf-8") as handle:
                        json.dump(payload, handle, ensure_ascii=False)
                except OSError as exc:
                    print(f"SMOKE: cannot write log {log}: {exc}", file=sys.stderr)
            window._closing = True  # 验证模式不弹后台任务确认框
            window.close()
            app.quit()
            print("SMOKE: exit", flush=True)
        QTimer.singleShot(int(os.environ["GITDESK_SMOKE_EXIT_MS"]), smoke_report)
        # 打包测试模式下不等待可能进行中的后台 Git：验证完成后直接退出
        # QApplication，避免窗口 closeEvent 与用户交互/队列关闭互相等待。
        def force_smoke_exit() -> None:
            smoke_report()
            os._exit(0)
        QTimer.singleShot(int(os.environ["GITDESK_SMOKE_EXIT_MS"]) + 10000,
                          force_smoke_exit)
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        report_startup_error()
        raise
