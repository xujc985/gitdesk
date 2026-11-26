#!/usr/bin/env sh
# 安装当前用户的 Linux 应用菜单入口，不修改系统目录。
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
APP_DIR=${XDG_DATA_HOME:-"$HOME/.local/share"}/applications
mkdir -p "$APP_DIR"
DESKTOP="$APP_DIR/gitdesk.desktop"
ESCAPED=$(printf '%s' "$HERE" | sed 's/\\/\\\\/g; s/"/\\"/g')
cat > "$DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Name=GitDesk
Comment=Lightweight native Git desktop client
Exec="$HERE/run.sh" %F
Icon=$ESCAPED/assets/gitdesk.png
Terminal=false
Categories=Development;RevisionControl;
Keywords=git;version control;qt;
StartupNotify=true
EOF
chmod +x "$HERE/run.sh"
printf 'GitDesk 已安装到应用菜单：%s\n' "$DESKTOP"
