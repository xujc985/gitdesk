#!/bin/sh
# GitDesk macOS .app 构建；在 macOS 上运行，非交叉编译。
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
PYTHON=${PYTHON:-python3}
"$PYTHON" -c 'import PySide6' >/dev/null 2>&1 || "$PYTHON" -m pip install -r requirements.txt
"$PYTHON" -c 'import sys; print("Python:", sys.version); import PySide6; print("Qt:", PySide6.__version__)'
"$PYTHON" -m PyInstaller --version >/dev/null 2>&1 || "$PYTHON" -m pip install 'pyinstaller>=6.10,<7'
"$PYTHON" -m PyInstaller --noconfirm --clean --distpath "$ROOT/dist" --workpath "$ROOT/build/pyinstaller" packaging/gitdesk.spec
export GITDESK_SMOKE_LOG="$ROOT/build/package-smoke.json"
mkdir -p "$ROOT/build"
"$PYTHON" packaging/smoke_test.py "$ROOT/dist/GitDesk.app/Contents/MacOS/GitDesk"

APP="$ROOT/dist/GitDesk.app"
VERSION=${GITDESK_VERSION:-1.0.0}
# 开发签名可让本机 Gatekeeper 识别；正式发布请提供 Developer ID 和 APPLE_ID。
if [ "${GITDESK_SIGN:-1}" = "1" ]; then
    codesign --deep --force --sign - "$APP"
fi
mkdir -p "$ROOT/release"
DMG="$ROOT/release/GitDesk-$VERSION-macos.dmg"
rm -f "$DMG"
hdiutil create -volname GitDesk -srcfolder "$APP" -ov -format UDZO "$DMG"
shasum -a 256 "$DMG" > "$DMG.sha256"
echo "macOS application: $APP"
echo "DMG: $DMG"
if [ -n "${APPLE_ID:-}" ] && [ -n "${APPLE_TEAM_ID:-}" ] && [ -n "${APPLE_APP_PASSWORD:-}" ]; then
    xcrun notarytool submit "$DMG" --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_PASSWORD" --wait
    xcrun stapler staple "$APP"
else
    echo "未配置 Apple 签名/公证凭据；当前仅生成本地开发包，不是正式分发签名包。"
fi
