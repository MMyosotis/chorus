#!/bin/bash
# 双击启动后端服务

cd "$(dirname "$0")" || exit 1

if [ ! -d ".venv" ]; then
  echo "首次运行，正在安装依赖..."
  uv sync || { echo "uv sync 失败"; read -p "按回车键退出..."; exit 1; }
fi

echo "启动后端服务..."
echo "访问地址: http://localhost:8000"
echo "按 Ctrl+C 停止"
echo ""

.venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
