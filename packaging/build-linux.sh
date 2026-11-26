#!/usr/bin/env sh
# GitDesk Linux 独立应用构建：onedir + AppDir + tar.gz。
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
PYTHON=${PYTHON:-python3}
"$PYTHON" -c 'import PySide6' >/dev/null 2>&1 || "$PYTHON" -m pip install -r requirements.txt
"$PYTHON" -m PyInstaller --version >/dev/null 2>&1 || "$PYTHON" -m pip install 'pyinstaller>=6.10,<7'
VERSION=${GITDESK_VERSION:-1.0.0}
# Linux CI/无显示服务器也执行真实 Qt 启动验证。
if [ -z "${DISPLAY:-}" ]; then export QT_QPA_PLATFORM=offscreen; fi
export GITDESK_SMOKE_LOG="$ROOT/build/package-smoke.json"
mkdir -p "$ROOT/build"
"$PYTHON" -m PyInstaller --noconfirm --clean --distpath "$ROOT/dist" --workpath "$ROOT/build/pyinstaller" packaging/gitdesk.spec
"$PYTHON" packaging/smoke_test.py "$ROOT/dist/GitDesk/GitDesk"
APPDIR="$ROOT/dist/GitDesk.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/icons/hicolor/256x256/apps" "$APPDIR/usr/share/applications"
cp -R "$ROOT/dist/GitDesk/." "$APPDIR/usr/bin/"
cp "$ROOT/assets/gitdesk.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/gitdesk.png"
cat > "$APPDIR/usr/share/applications/gitdesk.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=GitDesk
Comment=Lightweight native Git desktop client
Exec=GitDesk %F
Icon=gitdesk
Terminal=false
Categories=Development;RevisionControl;
EOF
cp "$APPDIR/usr/share/applications/gitdesk.desktop" "$APPDIR/gitdesk.desktop"
cp "$ROOT/assets/gitdesk.png" "$APPDIR/gitdesk.png"
cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env sh
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$HERE/usr/bin/GitDesk" "$@"
EOF
chmod +x "$APPDIR/AppRun" "$APPDIR/usr/bin/GitDesk"
mkdir -p "$ROOT/release"
ARCHIVE="$ROOT/release/GitDesk-$VERSION-linux-x64.tar.gz"
tar -C "$ROOT/dist" -czf "$ARCHIVE" "$(basename "$APPDIR")"
(cd "$ROOT/release" && sha256sum "$(basename "$ARCHIVE")" > "$(basename "$ARCHIVE").sha256")
echo "Linux AppDir package: $ARCHIVE"
# 额外生成单文件可执行 AppImage（需 Linux/AppImage 兼容环境）。
if command -v appimagetool >/dev/null 2>&1; then
    appimagetool "$APPDIR" "$ROOT/release/GitDesk-$VERSION-linux-x64.AppImage"
    chmod +x "$ROOT/release/GitDesk-$VERSION-linux-x64.AppImage"
    (cd "$ROOT/release" && sha256sum "GitDesk-$VERSION-linux-x64.AppImage" > "GitDesk-$VERSION-linux-x64.AppImage.sha256")
else
    echo "安装 appimagetool 后可生成 AppImage："
    echo "  https://github.com/AppImage/appimagetool/releases"
fi
