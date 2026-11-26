#!/bin/sh
# macOS 便捷启动：./run-macos.command [仓库路径]
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$HERE/run.sh" "$@"
