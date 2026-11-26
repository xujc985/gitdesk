#!/usr/bin/env sh
# GitDesk Qt 跨平台启动器：Linux / macOS
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON=${PYTHON:-python3}
if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "GitDesk: 未找到 Python 3，请先安装 Python 3.10+。" >&2
    exit 1
fi
if ! "$PYTHON" -c 'import PySide6' >/dev/null 2>&1; then
    echo "GitDesk: 正在安装 Qt Widgets 依赖…"
    "$PYTHON" -m pip install -r "$HERE/requirements.txt"
fi
exec "$PYTHON" "$HERE/main.py" "$@"
