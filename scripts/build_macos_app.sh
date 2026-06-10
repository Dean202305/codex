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
PACKAGE_DIR="$(mktemp -d /private/tmp/resume-screening-app.XXXXXX)"
PACKAGE_APP_PATH="$PACKAGE_DIR/小A简历筛选.app"
trap 'rm -rf "$PACKAGE_DIR"' EXIT

clean_app_xattrs() {
  local target="$1"
  if command -v chflags >/dev/null 2>&1; then
    chflags -R nohidden "$target" 2>/dev/null || true
  fi
  if command -v xattr >/dev/null 2>&1; then
    xattr -cr "$target" || true
    xattr -cr -s "$target" || true
    find "$target" -exec xattr -c {} \; 2>/dev/null || true
    find "$target" -type l -exec xattr -c -s {} \; 2>/dev/null || true
    for attr in com.apple.FinderInfo com.apple.ResourceFork "com.apple.fileprovider.fpfs#P" com.apple.provenance; do
      find "$target" -xattrname "$attr" -exec xattr -d "$attr" {} \; 2>/dev/null || true
      find "$target" -xattrname "$attr" -exec xattr -d -s "$attr" {} \; 2>/dev/null || true
      find "$target" -exec xattr -d "$attr" {} \; 2>/dev/null || true
      find "$target" -type l -exec xattr -d -s "$attr" {} \; 2>/dev/null || true
      xattr -d "$attr" "$target" 2>/dev/null || true
      xattr -d -s "$attr" "$target" 2>/dev/null || true
      xattr -d "$attr" "$target/Contents/Frameworks/Python.framework" 2>/dev/null || true
      xattr -d -s "$attr" "$target/Contents/Frameworks/Python.framework" 2>/dev/null || true
      xattr -d "$attr" "$target/Contents/Resources/Python.framework" 2>/dev/null || true
      xattr -d -s "$attr" "$target/Contents/Resources/Python.framework" 2>/dev/null || true
    done
  fi
}

clean_app_xattrs "$APP_PATH"
ditto --norsrc "$APP_PATH" "$PACKAGE_APP_PATH"
clean_app_xattrs "$PACKAGE_APP_PATH"
if command -v codesign >/dev/null 2>&1; then
  codesign --force --deep --sign - "$PACKAGE_APP_PATH"
  clean_app_xattrs "$PACKAGE_APP_PATH"
  codesign --verify --deep --strict --verbose=2 "$PACKAGE_APP_PATH"
fi

(cd "$PACKAGE_DIR" && ditto -c -k --keepParent --norsrc "小A简历筛选.app" "$ZIP_PATH")

if command -v hdiutil >/dev/null 2>&1; then
  ln -s /Applications "$PACKAGE_DIR/Applications"
  hdiutil create -volname "小A简历筛选" -srcfolder "$PACKAGE_DIR" -ov -format UDZO "$DMG_PATH"
fi

echo "已生成：$APP_PATH"
echo "可迁移压缩包：$ZIP_PATH"
echo "本地安装包：$DMG_PATH"
