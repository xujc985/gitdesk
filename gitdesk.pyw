# -*- coding: utf-8 -*-
"""双击入口。pythonw 下的启动错误由 main.py 记录并提示。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import main, report_startup_error  # noqa: E402

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        report_startup_error()
        raise
