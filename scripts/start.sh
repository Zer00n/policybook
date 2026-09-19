#!/usr/bin/env bash
# scripts/start.sh
# PolicyBook 保单簿 - Linux / macOS 一键启动脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

echo "======================================================="
echo "            PolicyBook 保单簿 · 一键启动               "
echo "======================================================="

# 1. 检查 uv
if ! command -v uv &> /dev/null; then
    echo "【错误】未检测到 uv 包管理器！请先安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# 2. 检查 .env 与数据目录
if [ ! -f ".env" ]; then
    echo "首次运行，自动初始化 .env 与基础目录..."
fi
(cd backend && uv run python -m app.scripts.init)

# 3. 检查前端
RUN_DEV=0
if command -v pnpm &> /dev/null; then
    DEPS_OK=1
    if [ ! -d "frontend/node_modules" ]; then
        echo "正在安装前端依赖 (pnpm install)..."
        # 安装失败不应直接终止启动：只要有已编译产物，仍可由后端单端口托管前端
        if ! (cd frontend && pnpm install); then
            DEPS_OK=0
            PNPM_VER="$(pnpm --version 2>/dev/null || echo 未知)"
            echo "【警告】前端依赖安装失败（当前 pnpm 版本：${PNPM_VER}）。"
        fi
    fi

    if [ $DEPS_OK -eq 1 ]; then
        RUN_DEV=1
    elif [ -f "frontend/dist/index.html" ]; then
        echo "  已检测到前端编译产物，改由后端提供静态服务，开发模式本次跳过。"
    else
        echo "  且未找到 frontend/dist 产物，无法提供前端页面。"
        echo "  请检查上面的 pnpm 报错后重试；也可先在能联网的机器上执行 pnpm build，"
        echo "  再把 frontend/dist 目录拷贝到本机，由后端单端口托管。"
        exit 1
    fi
elif [ -f "frontend/dist/index.html" ]; then
    echo "检测到前端已编译产物，将由后端提供静态服务。"
else
    echo "【错误】未检测到 pnpm 且未找到 frontend/dist 产物，请安装 Node.js 和 pnpm！"
    exit 1
fi

cleanup() {
    echo ""
    echo "正在停止 PolicyBook 服务..."
    kill $(jobs -p) 2>/dev/null || true
    wait 2>/dev/null || true
    echo "服务已停止。"
}
trap cleanup EXIT INT TERM

# 4. 启动后端
echo "正在启动后端服务 (http://127.0.0.1:8000)..."
(cd backend && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

# 5. 启动前端（若有 pnpm）
if [ $RUN_DEV -eq 1 ]; then
    echo "正在启动前端开发服务 (http://127.0.0.1:5173)..."
    (cd frontend && pnpm dev --host 0.0.0.0 --port 5173) &
    FRONTEND_PID=$!
    TARGET_URL="http://127.0.0.1:5173"
else
    TARGET_URL="http://127.0.0.1:8000"
fi

# 6. 等待服务就绪
echo "等待服务启动..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

echo ""
echo "======================================================="
echo "      ✓ PolicyBook 保单簿服务已成功运行！               "
echo "======================================================="
echo "  应用访问地址: $TARGET_URL"
echo "  后端接口文档: http://127.0.0.1:8000/api/docs"
echo "  按 Ctrl+C 退出并将停止所有服务"
echo "======================================================="

# 尝试在支持 xdg-open / open 的系统打开浏览器
if command -v xdg-open &> /dev/null; then
    xdg-open "$TARGET_URL" &>/dev/null || true
elif command -v open &> /dev/null; then
    open "$TARGET_URL" &>/dev/null || true
fi

wait
