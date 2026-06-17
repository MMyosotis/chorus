#!/bin/bash
# 同时启动后端和前端开发服务器

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "正在停止服务..."
    [ -n "$BACKEND_PID" ] && kill "$BACKEND_PID" 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill "$FRONTEND_PID" 2>/dev/null
    wait 2>/dev/null
    echo "已停止"
    exit 0
}
trap cleanup SIGINT SIGTERM

# --- 后端 ---
cd "$PROJECT_ROOT" || exit 1

if [ ! -d ".venv" ]; then
    echo "后端：首次运行，正在安装依赖..."
    uv sync || { echo "uv sync 失败"; exit 1; }
fi

echo "启动后端服务... http://localhost:8000"
.venv/bin/uvicorn kitty.app:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# --- 前端 ---
cd "$PROJECT_ROOT/frontend" || exit 1

if [ ! -d "node_modules" ]; then
    echo "前端：首次运行，正在安装依赖..."
    npm install || { echo "npm install 失败"; kill "$BACKEND_PID"; exit 1; }
fi

echo "启动前端服务... http://localhost:5173"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "===== Little Kitty 已启动 ====="
echo "后端: http://localhost:8000"
echo "前端: http://localhost:5173"
echo "按 Ctrl+C 同时停止两个服务"
echo "================================"
echo ""

wait
