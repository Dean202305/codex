#!/bin/zsh
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source ".venv/bin/activate"
python -m pip install .

if [ ! -f "config.yaml" ]; then
  cp "config.example.yaml" "config.yaml"
fi

if [ ! -f "src/resume_screening/web/static/index.html" ]; then
  if command -v npm >/dev/null 2>&1; then
    (cd web && npm install && npm run build)
  else
    echo "没有找到 npm，无法构建 React 页面。请先安装 Node.js，或联系 Codex 帮你构建一次。"
    exit 1
  fi
fi

open "http://127.0.0.1:8765"
resume-screening web --config config.yaml --host 127.0.0.1 --port 8765
