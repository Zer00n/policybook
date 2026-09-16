#!/usr/bin/env bash
# scripts/dev.sh
# 启动 PolicyBook 本地开发服务（Linux / macOS / WSL）

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== 启动 PolicyBook 本地开发环境 ==="
cd "$ROOT_DIR"

if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "正在从 .env.example 生成 .env..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
fi

# 退出时杀死子进程
trap 'kill $(jobs -p) 2>/dev/null || true' EXIT

echo "正在拉起后端服务 (http://127.0.0.1:8000)..."
(cd "$ROOT_DIR/backend" && uv run uvicorn app.main:app --reload --port 8000) &

echo "正在拉起前端服务 (http://127.0.0.1:5173)..."
(cd "$ROOT_DIR/frontend" && pnpm dev) &

echo "前后端服务已启动！"
echo "前端地址: http://127.0.0.1:5173"
echo "后端地址: http://127.0.0.1:8000/api/docs"

wait
