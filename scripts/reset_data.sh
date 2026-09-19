#!/usr/bin/env bash
# scripts/reset_data.sh
# PolicyBook 保单簿 - 清空测试数据脚本 (Linux / macOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "======================================================="
echo "         PolicyBook 保单簿 · 重置平台测试数据           "
echo "======================================================="

(cd backend && uv run python "$ROOT_DIR/scripts/reset_data.py")

echo ""
echo "数据清空完毕，平台已回归纯净初始化状态。"
