# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Little Kitty — 带上下文记忆的 AI 对话助手。前后端分离架构，后端 FastAPI + OpenAI SDK 提供 SSE 流式对话，前端 Vue 3 + Vite 提供聊天界面。

## Commands

### 后端
```bash
uv sync                                          # 安装依赖
.venv/bin/uvicorn backend.app:app --reload --port 8000   # 启动开发服务器
```

### 前端
```bash
cd frontend && npm install && npm run dev         # 安装依赖并启动开发服务器
cd frontend && npm run build                      # 构建生产版本
```

### 环境变量
在 `.env` 中配置（必须）：
- `OPENAI_API_KEY` — API 密钥
- `OPENAI_BASE_URL` — API 基地址（默认 `https://api.openai.com/v1`）
- `MODEL_ID` — 模型名称（默认 `gpt-4o`）

## Architecture

### 后端 (backend/)

| 模块 | 职责 |
|------|------|
| `config.py` | 从 `.env` 读取配置（API_KEY, BASE_URL, MODEL_ID, SYSTEM_PROMPT, MAX_TOKENS） |
| `chat.py` | 对话核心：OpenAI 客户端、全局 `_history` 列表管理单会话上下文、`chat_stream()` 同步生成器逐 token yield |
| `routes/chat.py` | HTTP 路由层，三个端点：`POST /api/chat`（SSE 流式）、`GET /api/chat/history`、`POST /api/chat/reset` |
| `app.py` | FastAPI 应用工厂，CORS 配置（允许 localhost:5173），注册路由 |

关键设计：路由函数用同步 `def`（非 `async def`），FastAPI 自动线程池执行；流结束后才将完整 assistant 回复写入历史；异常时回滚 user 消息。

### 前端 (frontend/src/)

```
App.vue（状态中心：messages, streaming + fetchHistory/sendMessage/newChat）
├── ChatWindow.vue（消息列表 + 自动滚动）
│   └── MessageBubble.vue（单条气泡，根据 role 左右对齐）
└── InputBar.vue（输入框 + 发送按钮）
```

SSE 解析用 `fetch` + `ReadableStream`（不用 EventSource，因为需要 POST）。Vite 开发代理 `/api` → `http://localhost:8000`。

### 数据流

1. 前端 POST `/api/chat` → 后端调用 OpenAI 流式 API
2. 后端逐 token 生成 SSE 事件（`type: token/done/error`）
3. 前端 `ReadableStream` 解析 SSE，Vue 响应式驱动打字机效果

## No Tests

项目当前没有测试框架和测试文件。
