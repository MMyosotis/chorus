#!/bin/bash
# 双击启动前端开发服务器
# macOS 会在 Terminal 中打开并运行

cd "$(dirname "$0")/frontend" || exit 1

if [ ! -d "node_modules" ]; then
  echo "首次运行，正在安装依赖..."
  npm install || { echo "npm install 失败"; read -p "按回车键退出..."; exit 1; }
fi

echo "启动前端开发服务器..."
echo "访问地址: http://localhost:5173"
echo "按 Ctrl+C 停止"
echo ""

npm run dev
