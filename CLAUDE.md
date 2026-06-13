# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Little Kitty — 带上下文记忆的 AI 对话助手，支持 tool calling 和动态 skill 加载。前后端分离架构：后端 FastAPI + OpenAI SDK 提供 SSE 流式对话（含 agent loop），前端 Vue 3 + Vite 提供聊天界面。

## Commands

### 后端
```bash
uv sync                                                # 安装依赖
.venv/bin/uvicorn backend.app:app --reload --port 8000 # 启动开发服务器
./启动后端.sh                                          # 等价快捷脚本

# 不走 HTTP 的本地调试 CLI（直接调用 chat_stream，方便观察 SSE 事件）
.venv/bin/python -m backend.tests.test_cli
```

### 前端
```bash
cd frontend && npm install && npm run dev   # 安装依赖并启动开发服务器
cd frontend && npm run build                # 构建生产版本
./启动前端.sh                                # 等价快捷脚本
```

### 环境变量
在 `.env` 中配置：
- `OPENAI_API_KEY` — API 密钥（必须）
- `OPENAI_BASE_URL` — API 基地址（默认 `https://api.openai.com/v1`）
- `MODEL_ID` — 模型名称（默认 `gpt-4o`）
- `MAX_TOOL_ITERATIONS` — agent loop 最大迭代次数（默认 `10`）

## Architecture

### 后端 (backend/)

| 模块 | 职责 |
|------|------|
| `config.py` | 从 `.env` 读取配置（API_KEY, BASE_URL, MODEL_ID, SYSTEM_PROMPT, MAX_TOKENS, MAX_TOOL_ITERATIONS, SKILLS_DIR） |
| `chat.py` | 对话核心：OpenAI 客户端、全局 `_history` 列表、`_assistant_messages` 元数据、`chat_stream()` 同步生成器实现 agent loop |
| `routes/chat.py` | HTTP 路由：`POST /api/chat`（SSE 流式）、`GET /api/chat/history`、`POST /api/chat/reset` |
| `app.py` | FastAPI 应用工厂，CORS + 初始化 SkillLoader + 注册路由 |
| `tools/base.py` | 工具注册框架：`@tool` 装饰器、`ToolDef`（含可选 `display` 回调）、`_REGISTRY`、`dispatch_tool()`/`get_tool_schemas()`/`format_tool_display()`/`safe_path()` |
| `tools/builtin/` | 内置工具：bash, read_file, write_file, edit_file, glob_search, load_skill |
| `skills/loader.py` | SkillLoader：扫描 `skills_data/*.md`，解析 frontmatter，生成 skill 摘要注入 system prompt |
| `skills/__init__.py` | SkillLoader 单例管理（`init_skill_loader` / `get_skill_loader`） |
| `tests/test_cli.py` | 终端测试 CLI（直接调用 `chat_stream`，不经过 HTTP），用于快速验证 agent loop |

### Agent Loop (chat.py)

`chat_stream()` 实现多轮工具调用循环：
1. 每次迭代调用 OpenAI 流式 API（附带 tool schemas）
2. `_accumulate_stream()` 消费流，yield token / reasoning / reasoning_done 事件，累积 tool_calls
3. 纯文本回复（`finish_reason != "tool_calls"`）→ 写入历史，yield done，结束
4. 工具调用 → 写入 assistant 消息，逐个执行工具，yield tool_call/tool_result 事件，把 tool 输出 append 到 `_history`，继续下一轮迭代
5. 达到 `MAX_TOOL_ITERATIONS` 时 yield `done` + `reason="max_iterations_reached"` 强制结束

关键设计：
- 路由函数用同步 `def`（非 `async def`），FastAPI 自动线程池执行；流结束后才将完整 assistant 回复写入历史；异常时回滚本次新增的 history 行和对应的 message 元数据。
- **每个 OpenAI 轮次 = 一条 assistant 历史消息 = 一个前端气泡**。每轮开始前生成新的 `message_id`，并通过 `message_start` 事件通知前端创建气泡；该轮的 `thinking` / `tools` 元数据汇总到 `_assistant_messages[message_id]`，并通过 `_meta_message_id` 字段挂在历史里的 assistant 消息上。
- 发给 OpenAI 前由 `_sanitize_for_openai()` 剥离所有 `_meta_*` 字段。
- `_accumulate_stream` 在收到 `delta.reasoning_content` 时进入"思考中"状态，遇到 `delta.content` / `delta.tool_calls` 时 close 当前思考段并 yield `reasoning_done`（含 `duration_ms`）；流结束兜底也会 close。
- `get_history()` 输出给前端时，每条 assistant 消息附带自己那一轮的 `thinking` / `tools` 元数据，用于刷新页面后恢复气泡内的折叠面板（不会再出现多条气泡共享同一份元数据的问题）。

### Skill 系统

- `backend/skills_data/` 下放 markdown 文件，支持 frontmatter（name, description, tags）
- SkillLoader 启动时扫描并缓存，`format_skill_hints()` 生成摘要追加到 system prompt
- 模型通过 `load_skill` 工具按需加载完整 skill 内容
- `_ensure_system_prompt()` 每次对话开始时刷新 system prompt（含最新 skill 摘要）

### Tool 安全与展示

- `safe_path()` 在 `tools/base.py` 中确保文件操作路径不逃逸工作目录（`WORKDIR = Path.cwd()`）。
- 每个工具可在 `@tool(... display=...)` 中提供回调，返回单行人类可读描述（前端用于展示工具调用 chip）。`format_tool_display()` 负责剥换行、限长（200 字符），并在出错时回退到工具名。

### 前端 (frontend/src/)

```
App.vue（状态中心：messages, streaming + fetchHistory/sendMessage/newChat）
├── ChatWindow.vue（消息列表 + 自动滚动）
│   └── MessageBubble.vue（单条气泡，user 右对齐；assistant 含 thinking / tools 折叠面板 + 主文本）
└── InputBar.vue（输入框 + 发送按钮）
```

assistant 消息在前端被规范化为 `{ role, content, thinking: { state, items, expanded }, tools: { state, items, expanded } }`：
- `thinking.items[i] = { text, duration_ms }`，`reasoning` token 持续追加到当前段，收到 `reasoning_done` 时写入 `duration_ms` 并标记完成。
- `tools.items[i] = { id, name, arguments, duration_ms, content, display }`，`tool_result` 通过 `id` 匹配回 `tool_call` 并填充结果。
- 流式期间 `App.vue` 收到 `message_start` 事件时：先把上一轮的 running 状态收尾；若当前气泡还没产出 `content` 则**复用**它（让本轮的 thinking / tools 继续累积进同一气泡），否则才 push 新气泡。这避免了"只有思考 / 工具调用、没有正文"的空壳气泡——它们会被合并到下一个有正文的气泡。
- 页面刷新时 `fetchHistory()` 会先调用 `mergeAssistantHistory()`：把连续的"无 content 的 assistant 轮次"thinking / tools 累积到下一条有 content 的 assistant 消息上，再调用 `normalizeAssistant()` 包装成前端结构；尾部若仍有未合并的中间轮（如 `max_iterations_reached`），保留为独立气泡以免信息丢失。

SSE 解析用 `fetch` + `ReadableStream`（不用 EventSource，因为需要 POST）。Vite 开发代理 `/api` → `http://localhost:8000`。

### SSE 事件类型

| type | 说明 |
|------|------|
| `message_start` | 新一轮 assistant 消息开始（含 `id`），前端据此创建新气泡 |
| `reasoning` | 思考阶段 token 片段（`delta.reasoning_content`），归属到当前气泡 |
| `reasoning_done` | 当前思考段结束（含 `duration_ms`） |
| `token` | 流式正文文本片段，归属到当前气泡 |
| `tool_call` | 模型请求调用工具（`id`, `name`, `arguments`, `display`） |
| `tool_result` | 工具执行结果（`tool_call_id`, `name`, `content`, `duration_ms`） |
| `done` | 对话回合结束（`reason` 仅在达到 `max_iterations` 时存在） |
| `error` | 异常信息（同时回滚本次新增的历史行与消息元数据） |

### 数据流

1. 前端 POST `/api/chat` → 后端 `chat_stream()` agent loop
2. 每轮：OpenAI 流式 API → 逐 token yield SSE → 前端 ReadableStream 解析 → Vue 响应式驱动打字机效果
3. 工具调用时：yield tool_call → 执行工具 → yield tool_result → 继续下一轮 OpenAI 调用

## No Tests

项目当前没有正式测试框架和单元测试。`backend/tests/test_cli.py` 是手动调试用的交互 CLI，不是自动化测试。
