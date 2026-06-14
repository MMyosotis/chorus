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
- `CONV_TTL_DAYS` — 会话过期天数，超过自动清理（默认 `30`）
- `CONV_MAX_BYTES` — 单个会话 JSON 最大字节数，超过删除（默认 `1048576`）
- `CONV_MAX_COUNT` — 会话总数上限，超过删除最旧（默认 `100`）
- `ARK_IMAGE_API_KEY` — 火山方舟图像生成 API 密钥（`generate_image` 工具使用，与对话密钥解耦）
- `ARK_IMAGE_BASE_URL` — 火山方舟图像 API 基地址（默认 `https://ark.cn-beijing.volces.com/api/v3`）
- `ARK_IMAGE_MODEL_SEEDREAM_4` — seedream-4 逻辑名映射的真实模型 ID（默认 `doubao-seedream-4-0-250828`）
- `ARK_IMAGE_MODEL_SEEDREAM_5_LITE` — seedream-5-lite 逻辑名映射的真实模型 ID（默认 `doubao-seedream-5-0-litenew`）
- `IMAGE_TEST_FAKE_URL` — 图像测试模式下的固定返回 URL（默认是一张已知可用的橘猫图，可覆盖换图）。测试开关本身只在控制台「设置」中切换，默认关闭，进程级状态、重启回到关

## Architecture

### 后端 (backend/)

| 模块 | 职责 |
|------|------|
| `config.py` | 从 `.env` 读取配置（API_KEY, BASE_URL, MODEL_ID, SYSTEM_PROMPT, MAX_TOKENS, MAX_TOOL_ITERATIONS, SKILLS_DIR, CONVERSATIONS_DIR, CONV_TTL_DAYS / CONV_MAX_BYTES / CONV_MAX_COUNT） |
| `chat.py` | 对话核心：OpenAI 客户端、`chat_stream(message, conversation_id)` 同步生成器实现 agent loop；通过 `init_chat_store()` 注入 `ConversationStore` 操作具体会话的 `history`/`assistant_messages`；包含 `_maybe_generate_title` 首轮标题生成 |
| `conversations/store.py` | `ConversationStore`：按 id 隔离的会话持久化（`backend/data/conversations/{id}.json`），原子写、双层锁（全局 + 会话级）、节流清理（TTL/单文件大小/总量）|
| `settings/store.py` | `SettingsStore`：通用 KV 配置持久化（`backend/data/settings.db`），独立于会话数据；启动时回灌到 `config.py` 内存（如 `image_test_mode`） |
| `routes/chat.py` | HTTP 路由：`/api/conversations`（list/create）、`/api/conversations/{id}`（delete/rename）、`/api/conversations/{id}/messages`（GET）、`/api/conversations/{id}/chat`（SSE 流式，409 防同会话并发） |
| `routes/debug.py` | 调试 endpoint：`/api/debug/test-mode`（GET/PATCH），PATCH 同时改 config 内存与 settings 持久化 |
| `app.py` | FastAPI 应用工厂，CORS + 初始化 SkillLoader + SettingsStore + ConversationStore 并注入到 chat / routes + 注册路由 |
| `tools/base.py` | 工具注册框架：`@tool` 装饰器、`ToolDef`（含可选 `display` 回调）、`_REGISTRY`、`dispatch_tool()`/`get_tool_schemas()`/`format_tool_display()`/`safe_path()` |
| `tools/builtin/` | 内置工具：bash, read_file, write_file, edit_file, glob_search, load_skill, generate_image |
| `skills/loader.py` | SkillLoader：扫描 `skills_data/*.md`，解析 frontmatter，生成 skill 摘要注入 system prompt |
| `skills/__init__.py` | SkillLoader 单例管理（`init_skill_loader` / `get_skill_loader`） |
| `tests/test_cli.py` | 终端测试 CLI（直接调用 `chat_stream`，不经过 HTTP），启动时通过 store 创建一个会话再循环 |

### Agent Loop (chat.py)

`chat_stream(user_message, conversation_id)` 实现多轮工具调用循环：
1. 从 store 读出对应 conversation dict，操作其 `history` / `assistant_messages`
2. 每次迭代调用 OpenAI 流式 API（附带 tool schemas）
3. `_accumulate_stream()` 消费流，yield token / reasoning / reasoning_done 事件，累积 tool_calls
4. 纯文本回复（`finish_reason != "tool_calls"`）→ 写入历史 + `store.save()` + 同步调用 `_maybe_generate_title` 生成短标题（首轮且尚未生成时）→ yield `title_update`（如果有）→ yield done，结束
5. 工具调用 → 写入 assistant 消息，逐个执行工具，yield tool_call/tool_result 事件，把 tool 输出 append 到 history → `store.save()` → 继续下一轮迭代
6. 达到 `MAX_TOOL_ITERATIONS` 时 yield `done` + `reason="max_iterations_reached"` 强制结束

关键设计：
- 路由函数用同步 `def`（非 `async def`），FastAPI 自动线程池执行；流结束后才将完整 assistant 回复写入历史；异常时回滚本次新增的 history 行和对应的 message 元数据，再 save 一次。
- **会话级锁**：`/api/conversations/{id}/chat` 路由用 `lock.acquire(blocking=False)` 探测当前会话是否在流，被占用直接返回 409；锁在响应生成器的 `finally` 释放。不同会话锁独立 → 并发流式互不阻塞。
- **每个 OpenAI 轮次 = 一条 assistant 历史消息 = 一个前端气泡**。每轮开始前生成新的 `message_id`，并通过 `message_start` 事件通知前端创建气泡；该轮的 `thinking` / `tools` 元数据汇总到 `assistant_messages[message_id]`，并通过 `_meta_message_id` 字段挂在历史里的 assistant 消息上。
- 发给 OpenAI 前由 `_sanitize_for_openai()` 剥离所有 `_meta_*` 字段。
- `_accumulate_stream` 在收到 `delta.reasoning_content` 时进入"思考中"状态，遇到 `delta.content` / `delta.tool_calls` 时 close 当前思考段并 yield `reasoning_done`（含 `duration_ms`）；流结束兜底也会 close。
- `store.get_history_view()` 输出给前端时，每条 assistant 消息附带自己那一轮的 `thinking` / `tools` 元数据，用于刷新页面后恢复气泡内的折叠面板。

### ConversationStore (conversations/store.py)

- 单 conversation JSON：`{id, title, title_generated, created_at, updated_at, history, assistant_messages}`
- 内存缓存 + 双层锁（`_global_lock` 保护 cache/conv_locks 表；`_conv_locks[id]` 保护单会话写）
- 原子写：先写 `*.tmp` 再 `os.replace`
- `set_title_if_unset(id, title)`：仅在 `title_generated=False` 时更新（幂等）
- `cleanup(force=False)`：节流 60s。规则：`updated_at` 超 `CONV_TTL_DAYS` 删除；单文件超 `CONV_MAX_BYTES` 删除；总数超 `CONV_MAX_COUNT` 按 `updated_at` 升序删除最旧。保护：`len(cache) <= 1` 跳过；`lock.acquire(blocking=False)` 拿不到（streaming 中）跳过。
- 触发时机：`load_all()` 末尾 force 一次；每次 `save(id)` 之后调一次（节流）。

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
App.vue（双栏：sidebar + main-panel；多会话状态）
├── ConversationSidebar.vue（260px 固定，新建/列表/切换/重命名/删除 + streaming 脉冲点）
├── api.js（fetch 抽离：listConversations/createConversation/deleteConversation/renameConversation/fetchMessages/streamChat）
└── main-panel
    ├── ChatWindow.vue（消息列表 + 自动滚动）
    │   └── MessageBubble.vue（单条气泡，user 右对齐；assistant 含 thinking / tools 折叠面板 + 主文本）
    └── InputBar.vue（输入框 + 发送按钮）
```

**多会话状态模型**：
- `conversations: ref([])` —— meta 列表（按 updated_at 倒序）
- `messagesByConv: reactive({})` —— `{ [id]: Message[] }`，懒加载
- `streamingByConv: reactive({})` —— `{ [id]: boolean }`，按会话独立
- `activeId: ref(null)` —— 当前显示的会话
- `messages` / `streaming` 通过 `computed` 跟随 `activeId` 投影

**并发流式**：`onSend` 闭包 capture `convId = activeId.value` 和对应的 `list = messagesByConv[convId]`，回调里只动 `list`，与 `activeId` 解耦 —— 切走仍正确累积；同一会话同时只能一个流（前端 `disable` + 后端 409）。

**SSE 事件 `title_update`**：首轮 assistant 文本回复完成后，后端会同步调用一次非流式模型生成 5–12 字标题，通过该事件推回；前端收到后更新 `conversations` 中对应项 title。

assistant 消息在前端被规范化为 `{ role, content, thinking: { state, items, expanded }, tools: { state, items, expanded } }`：
- `thinking.items[i] = { text, duration_ms }`，`reasoning` token 持续追加到当前段，收到 `reasoning_done` 时写入 `duration_ms` 并标记完成。
- `tools.items[i] = { id, name, arguments, duration_ms, content, display }`，`tool_result` 通过 `id` 匹配回 `tool_call` 并填充结果。
- 流式期间 `App.vue` 收到 `message_start` 事件时：先把上一轮的 running 状态收尾；若当前气泡还没产出 `content` 则**复用**它（让本轮的 thinking / tools 继续累积进同一气泡），否则才 push 新气泡。这避免了"只有思考 / 工具调用、没有正文"的空壳气泡——它们会被合并到下一个有正文的气泡。
- 切换会话时 `fetchMessages(id)` 会先调用 `mergeAssistantHistory()`：把连续的"无 content 的 assistant 轮次"thinking / tools 累积到下一条有 content 的 assistant 消息上，再调用 `normalizeAssistant()` 包装成前端结构；尾部若仍有未合并的中间轮（如 `max_iterations_reached`），保留为独立气泡以免信息丢失。

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
| `title_update` | 首轮自动生成的会话标题（`id`, `title`），仅触发一次 |
| `done` | 对话回合结束（`reason` 仅在达到 `max_iterations` 时存在） |
| `error` | 异常信息（同时回滚本次新增的历史行与消息元数据） |

### 数据流

1. 前端 POST `/api/conversations/{id}/chat` → 后端 `chat_stream(message, id)` agent loop
2. 每轮：OpenAI 流式 API → 逐 token yield SSE → 前端 ReadableStream 解析 → Vue 响应式驱动打字机效果
3. 工具调用时：yield tool_call → 执行工具 → yield tool_result → 继续下一轮 OpenAI 调用
4. 每完整一轮 store 持久化到 `backend/data/conversations/{id}.json`

## No Tests

项目当前没有正式测试框架和单元测试。`backend/tests/test_cli.py` 是手动调试用的交互 CLI，不是自动化测试。

## 开发约定

在本项目的所有代码开发工作中，请严格遵守以下协作规则：

- **全程持续审视代码**，主动识别代码坏味道、不合理设计、冗余逻辑、不规范写法、可优化点。
- **一旦判定当前代码需要重构，立刻暂停新增功能开发，不得直接修改代码**。
- 向我清晰输出两部分内容：
  1. **问题说明**：指出代码具体问题、属于哪类代码坏味道、带来的隐患 / 弊端；
  2. **重构方案**：给出具体优化思路、改动范围、重构后的效果。
- **仅在我明确同意、确认方案后**，你再按照方案执行代码重构；若我提出修改意见，同步调整方案后再操作。
- 若无重构必要，正常推进开发即可。
