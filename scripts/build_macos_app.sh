#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON:-python3}"
if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi

"$PYTHON_BIN" -m pip install ".[desktop]"

if [ -d web ]; then
  npm --prefix web install
  npm --prefix web run build
fi

"$PYTHON_BIN" -m PyInstaller --noconfirm packaging/macos/resume_screening_macos.spec

APP_PATH="$ROOT_DIR/dist/小A简历筛选.app"
ZIP_PATH="$ROOT_DIR/dist/小A简历筛选-mac.zip"
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

echo "已生成：$APP_PATH"
echo "可迁移压缩包：$ZIP_PATH"
