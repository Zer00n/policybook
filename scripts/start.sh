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

# 2.1 检查 OCR 所需的系统库
# rapidocr-onnxruntime 依赖完整版 opencv-python，它需要 libGL 等图形库。
# 服务器版 Linux 通常不预装，缺库时后端会在导入阶段直接崩溃，在这里提前拦下。
echo "检查 OCR 运行环境..."
if ! CV_ERR="$(cd backend && uv run python -c "import cv2" 2>&1)"; then
    echo "【错误】OCR 依赖的 OpenCV 无法加载："
    echo "$CV_ERR" | tail -3
    case "$CV_ERR" in
        *"cannot open shared object file"*|*libGL*|*libgthread*|*libglib*)
            echo ""
            echo "这是服务器版 Linux 常见的缺库问题，安装对应系统库后重试："
            echo "  Debian / Ubuntu :  sudo apt-get update && sudo apt-get install -y libgl1 libglib2.0-0"
            echo "  RHEL / CentOS   :  sudo yum install -y mesa-libGL glib2"
            ;;
    esac
    exit 1
fi

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
# 必须用健康检查结果决定后续输出：后端崩溃时不能再打印「启动成功」
echo "等待服务启动..."
BACKEND_READY=0
for i in {1..30}; do
    if curl -s http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        BACKEND_READY=1
        break
    fi
    # 后端进程已退出就不必再等
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        break
    fi
    sleep 0.5
done

if [ $BACKEND_READY -eq 0 ]; then
    echo ""
    echo "======================================================="
    echo "      后端服务未能就绪，启动失败                       "
    echo "======================================================="
    echo "  请查看上方后端输出的报错定位原因。常见情况："
    echo "    - 缺少 OCR 所需系统库（libGL.so.1、libglib 等）"
    echo "    - 端口 8000 已被占用"
    echo "    - .env 配置缺失或 APP_SECRET 未生成"
    echo "======================================================="
    exit 1
fi

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
