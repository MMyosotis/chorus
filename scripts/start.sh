#!/bin/bash
# 同时启动后端和前端开发服务器
# 后端：uvicorn (含 supervisor SSE + subagent 后台线程 + scheduler 守护线程)
# 前端：vite dev (三栏布局，代理 /api → :8000)

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

cd "$PROJECT_ROOT" || exit 1

# --- 环境变量检查（多智能体需对话/生图/搜索多组 key）---
if [ ! -f ".env" ]; then
    echo "警告：未找到 .env，将以下变量填入 .env 后再启动（缺 key 会在对话/生图时报错）："
    echo "  DEEPSEEK_API_KEY / MINIMAX_API_KEY（对话模型，按 CHAT_MODELS 用到哪个配哪个）"
    echo "  ARK_IMAGE_API_KEY（生图）"
    echo "  BAIDU_SEARCH_API_KEY / BAIDU_SEARCH_BASE_URL（联网搜索，可选）"
    echo ""
fi

# --- 后端 ---
if [ ! -d ".venv" ]; then
    echo "后端：首次运行，正在安装依赖..."
    uv sync || { echo "uv sync 失败"; exit 1; }
fi

echo "启动后端服务... http://localhost:8000"
.venv/bin/uvicorn chorus.app:app --host 127.0.0.1 --port 8000 --reload &
BACKEND_PID=$!

# --- 前端 ---
cd "$PROJECT_ROOT/web" || exit 1

if [ ! -d "node_modules" ]; then
    echo "前端：首次运行，正在安装依赖..."
    npm install || { echo "npm install 失败"; kill "$BACKEND_PID"; exit 1; }
fi

echo "启动前端服务... http://localhost:5173"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "===== Chorus 已启动 ====="
echo "后端: http://localhost:8000  (API + SSE + scheduler)"
echo "前端: http://localhost:5173  (三栏：会话 / 对话+创作 / 角色栏)"
echo "按 Ctrl+C 同时停止两个服务"
echo "================================"
echo ""

wait
