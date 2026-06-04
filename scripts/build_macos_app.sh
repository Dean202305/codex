#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

ARCH="$(uname -m)"
case "$ARCH" in
  arm64|aarch64)
    RUNTIME_KEY="macos-arm64"
    ;;
  x86_64|amd64)
    RUNTIME_KEY="macos-x64"
    ;;
  *)
    echo "不支持的 macOS 架构：$ARCH" >&2
    exit 1
    ;;
esac

RUNTIME_PATH="$ROOT_DIR/packaging/runtime/$RUNTIME_KEY/llama-server"
if [ ! -f "$RUNTIME_PATH" ] && [ "${ALLOW_MISSING_LOCAL_RUNTIME:-}" != "1" ]; then
  echo "缺少本地模型运行器：$RUNTIME_PATH" >&2
  echo "请按 packaging/runtime/README.md 放置 llama-server，或仅做开发验证时设置 ALLOW_MISSING_LOCAL_RUNTIME=1。" >&2
  exit 1
fi

"$PYTHON_BIN" -m pip install ".[desktop]"

if [ -d web ]; then
  npm --prefix web install
  npm --prefix web run build
fi

"$PYTHON_BIN" -m PyInstaller --noconfirm packaging/macos/resume_screening_macos.spec

APP_PATH="$ROOT_DIR/dist/小A简历筛选.app"
RUNTIME_SOURCE="$ROOT_DIR/packaging/runtime"
RUNTIME_DEST="$APP_PATH/Contents/Resources/packaging/runtime"
if [ -d "$RUNTIME_SOURCE" ]; then
  mkdir -p "$(dirname "$RUNTIME_DEST")"
  rm -rf "$RUNTIME_DEST"
  ditto --norsrc "$RUNTIME_SOURCE" "$RUNTIME_DEST"
fi

BUNDLED_RUNTIME_PATH="$RUNTIME_DEST/$RUNTIME_KEY/llama-server"
if [ ! -f "$BUNDLED_RUNTIME_PATH" ] && [ "${ALLOW_MISSING_LOCAL_RUNTIME:-}" != "1" ]; then
  echo "macOS 包缺少本地模型运行器：$BUNDLED_RUNTIME_PATH" >&2
  exit 1
fi
if [ -f "$BUNDLED_RUNTIME_PATH" ]; then
  chmod +x "$BUNDLED_RUNTIME_PATH"
fi

ZIP_PATH="$ROOT_DIR/dist/小A简历筛选-mac.zip"
DMG_PATH="$ROOT_DIR/dist/小A简历筛选-mac.dmg"
SIGNED_DIR="$(mktemp -d /private/tmp/resume-screening-app.XXXXXX)"
SIGNED_APP_PATH="$SIGNED_DIR/小A简历筛选.app"
trap 'rm -rf "$SIGNED_DIR"' EXIT

clean_app_xattrs() {
  local target="$1"
  if command -v xattr >/dev/null 2>&1; then
    xattr -cr "$target" || true
    find "$target" -name Python.framework -exec xattr -s -d com.apple.FinderInfo {} \; 2>/dev/null || true
    find "$target" -name Python.framework -exec xattr -d com.apple.FinderInfo {} \; 2>/dev/null || true
    xattr -d com.apple.FinderInfo "$target" 2>/dev/null || true
  fi
}

ditto --norsrc "$APP_PATH" "$SIGNED_APP_PATH"
clean_app_xattrs "$SIGNED_APP_PATH"

if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$SIGNED_APP_PATH"
  clean_app_xattrs "$SIGNED_APP_PATH"
  codesign --verify --deep --strict --verbose=2 "$SIGNED_APP_PATH"
fi

rm -rf "$APP_PATH"
ditto --norsrc "$SIGNED_APP_PATH" "$APP_PATH"
(cd "$SIGNED_DIR" && ditto -c -k --keepParent --norsrc "小A简历筛选.app" "$ZIP_PATH")

if command -v hdiutil >/dev/null 2>&1; then
  ln -s /Applications "$SIGNED_DIR/Applications"
  hdiutil create -volname "小A简历筛选" -srcfolder "$SIGNED_DIR" -ov -format UDZO "$DMG_PATH"
fi

echo "已生成：$APP_PATH"
echo "可迁移压缩包：$ZIP_PATH"
echo "本地安装包：$DMG_PATH"
