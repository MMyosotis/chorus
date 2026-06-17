# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Little Kitty — 带上下文记忆的 AI 对话助手，支持 tool calling 和动态 skill 加载。前后端分离架构：后端 FastAPI + OpenAI SDK 提供 SSE 流式对话（含 agent loop），前端 Vue 3 + Vite 提供聊天界面。

后端按 Java OOP 风格分层：`domain/models`（Pydantic 数据模型）→ `repositories`（各表唯一 SQL 入口）→ `services`（业务编排）→ `routes`（HTTP）。依赖单向 `routes → services → repositories → db`，构造器注入 + `AppContainer` 单点装配，无模块级全局单例。

## Commands

### 后端
```bash
uv sync                                              # 安装依赖
.venv/bin/uvicorn kitty.app:app --reload --port 8000 # 启动开发服务器
./scripts/start.sh                                   # 同时启动前后端

# 不走 HTTP 的本地调试 CLI（直接调用 ChatService.stream，方便观察 SSE 事件）
.venv/bin/python -m kitty.tests.test_cli
```

### 前端
```bash
cd frontend && npm install && npm run dev   # 安装依赖并启动开发服务器
cd frontend && npm run build                # 构建生产版本
```

### 环境变量
在 `.env` 中配置：
- `OPENAI_API_KEY` — API 密钥（必须）
- `OPENAI_BASE_URL` — API 基地址（默认 `https://api.openai.com/v1`）
- `MODEL_ID` — 模型名称（默认 `gpt-4o`）
- `MAX_TOOL_ITERATIONS` — agent loop 最大迭代次数（默认 `10`）
- `CONV_TTL_DAYS` — 会话过期天数，超过自动清理（默认 `30`）
- `CONV_MAX_BYTES` — 单个会话消息总字节数上限，超过删除（默认 `1048576`）
- `CONV_MAX_COUNT` — 会话总数上限，超过删除最旧（默认 `100`）
- `ARK_IMAGE_API_KEY` — 火山方舟图像生成 API 密钥（`generate_image` 工具使用，与对话密钥解耦）
- `ARK_IMAGE_BASE_URL` — 火山方舟图像 API 基地址（默认 `https://ark.cn-beijing.volces.com/api/v3`）
- `ARK_IMAGE_MODEL_SEEDREAM_4` — seedream-4 逻辑名映射的真实模型 ID（默认 `doubao-seedream-4-0-250828`）
- `ARK_IMAGE_MODEL_SEEDREAM_5_LITE` — seedream-5-lite 逻辑名映射的真实模型 ID（默认 `doubao-seedream-5-0-litenew`）
- `IMAGE_TEST_FAKE_URL` — 图像测试模式下的固定返回 URL（默认是一张已知可用的橘猫图，可覆盖换图）。测试开关本身只在控制台「设置」中切换，默认关闭，进程级状态、重启回到关

## 数据存放位置

- 运行时数据根目录 `DATA_DIR = 项目根 / data/`（在 `kitty/config.py` 定义，gitignored，启动自动创建）
- `data/little-kitty.db` — `sessions` + `messages` + `traces` 三张表（会话库）
- `data/settings.db` — `settings` 表（进程级 KV 配置，独立库，不受会话清理影响）
- `kitty/resources/skills/` — 技能 markdown（随源码版本管理，非运行时数据）

## Architecture

### 后端包结构 (`kitty/`)

| 包 / 模块 | 职责 |
|------|------|
| `config.py` | 从 `.env` 读取配置常量（含 `DATA_DIR`、`SKILLS_DIR`），纯静态值 |
| `app.py` | FastAPI 应用工厂 `create_app()`：构造 `AppContainer`、挂 `app.state.container`、CORS、注册路由 |
| `container.py` | `AppContainer`：单点装配所有 Repository / Service / Tool / Hook / ChatService，构造器注入，`startup()` 跑 load/cleanup |
| `domain/models/` | Pydantic v2 frozen 数据模型：`session`/`message`(sealed 联合)/`trace`/`tool`/`skill`/`events`(SSE sealed 联合)/`agent`(`AgentContext` 等 dataclass) |
| `repositories/` | 各表唯一 SQL 入口（不持锁/缓存/业务校验）：`connection`(线程局部 sqlite)、`session`/`message`/`trace`/`settings` |
| `services/` | 业务编排：`session`、`chat`、`settings`、`skill`、`title`、`cleanup`、`system_prompt_builder`（文件名无 `_service` 后缀，类名仍带 `Service`） |
| `hooks/` | `base`(Hook 单方法基类)、`manager`(HookManager 8 个具名方法 `on_xxx` 按字面顺序调用该事件 hook、fail-open)、`registry`(`build_hooks` 装配 9 个 hook 打包成 `HookBundle`) + `builtin/` 9 个类化 hook |
| `tools/` | `base`(Tool ABC + ToolRegistry + ToolContext + WorkspacePolicy)、`builtin/`(8 个工具，文件名无 `_tool` 后缀)、`clients/`(ark_image / baidu_search 外部依赖封装) |
| `routes/` | HTTP 路由 + `providers.py`(Depends 注入入口)：`sessions`、`chat`(SSE)、`settings`(/api/debug/test-mode) |
| `resources/skills/` | 技能 markdown（frontmatter: name/description/tags） |
| `tests/test_cli.py` | 手动调试 CLI（直接调 `ChatService.stream`，不经 HTTP） |

### Agent Loop (`services/chat.py`)

`ChatService.stream(session_id, user_message) -> Iterator[SseEvent]` 实现多轮工具调用循环，线性展开、每个 hook 调用点用注释标注副作用（plan 检验3 的生命周期图对应此函数）。hook 调用从 `HookManager.on_xxx(ctx)` 具名方法发起（不再经 `emit(Enum, ctx)` 反射分发），触发顺序写在各 `on_xxx` 方法的字面顺序里：

1. 记录入口前 messages 数量为回滚锚点；`on_loop_start` → SystemPromptHook 把 user 消息 append 入库
2. 每轮 `on_iteration_start`（分配 message_id）→ `on_before_model_request`（Sanitizer 调 `build_provider_messages` 写 `ctx.turn.provider_messages`；Trace 写 model_request）
3. 调 OpenAI 流式 API（消费 `ctx.turn.provider_messages`），模块函数 `consume_stream()` yield reasoning/token 事件、累积 text_parts / tool_calls / thinking
4. 纯文本回复（`finish_reason != "tool_calls"`）→ `on_assistant_text_response`（Trace 写 model_response；TextResponse append assistant 消息；Title 首轮生成标题）→ yield done，结束
5. 工具调用 → `on_tool_calls_detected`（Trace 写 model_response；ToolCall append assistant(tool_calls)、逐个执行工具、append tool 消息、yield tool_call/tool_result）→ 继续下一轮
6. 达 `MAX_TOOL_ITERATIONS` → `on_loop_end`（Trace 写 loop_end；Persistence yield done(reason)）
7. 异常 → `on_loop_error`（Rollback 删除本轮新增 messages + traces，yield error）

关键设计：
- **`AgentContext` 按生命周期细分**：回合级固定输入（session_id 等）留顶层；单轮累积状态收进 `TurnState`（每轮 `reset()`）；异常回滚账本 `RollbackLedger`；退出结果 `LoopOutcome`。hook 经注入的 `SessionService` 访问数据，不持 session/store 引用。
- 路由用同步 `def`，FastAPI 线程池执行；消息逐条 append 入库（产生即入库，非全量重写 save）；异常时 `truncate_after_snapshot` 回滚本轮新增。
- **会话级锁**：`SessionService.get_lock(session_id)` 返回 per-session `threading.Lock`，`/api/sessions/{id}/chat` 用 `lock.acquire(blocking=False)` 探测，被占用返回 409；锁在响应生成器 `finally` 释放。不同会话锁独立。
- **每个 OpenAI 轮次 = 一条 assistant 历史消息 = 一个前端气泡**。每轮 `message_start` 事件通知前端建气泡；该轮 thinking/tools 元数据由 `TraceRepository.aggregate_message_trace(message_id)` 重建。
- `SessionService.build_provider_messages()` 是传给 LLM 的消息序列**唯一**构建点：`[system] + 按 seq 的 user/assistant/tool 历史消息`。

### 存储层

- `ConnectionFactory`：线程局部 sqlite 连接，WAL + NORMAL 同步 + 外键约束开启。
- `SessionRepository` / `MessageRepository` / `TraceRepository` / `SettingsRepository`：各自表的唯一 SQL 入口，返回 Pydantic 模型。
- `messages` 表按消息粒度（user/assistant/tool），逐条 `append` 入库；`traces` 表靠 `message_id` 与 message 解耦关联。
- `SessionService` 编排三个 repo + 锁 + 清理入口；`CleanupService` 实现 TTL/字节/总量清理（删除经 `SessionService.delete`，不绕开锁）。

### Skill 系统

- `kitty/resources/skills/` 下放 markdown 文件，支持 frontmatter（name, description, tags）
- `SkillService` 启动时扫描缓存，`format_hints()` 生成摘要追加到 system prompt
- 模型通过 `load_skill` 工具按需加载完整 skill 内容
- `SystemPromptBuilder` 构造 system prompt（SYSTEM_PROMPT + skill hints），每次对话经 SanitizerHook 调 `build_provider_messages` 时刷新

### Tool 框架

- `Tool` ABC：类属性 `name`/`description`/`parameters`，`run(arguments, ctx) -> str`；`ToolRegistry.dispatch()` 统一执行/计时/包错，`format_display()` 返回单行人类可读描述（前端 chip）。
- `WorkspacePolicy.safe_path()` 确保文件操作路径不逃逸工作目录（`WorkspacePolicy(root=Path.cwd())`，构造器注入）。
- `GenerateImageTool` 依赖 `SettingsService.get_image_test_mode`（测试模式返回写死 URL）与 `ArkImageClient`；`BaiduSearchTool` 依赖 `BaiduSearchClient`。

### 前端 (frontend/src/)

```
App.vue（双栏：sidebar + main-panel；多会话状态）
├── SessionSidebar.vue（260px 固定，新建/列表/切换/重命名/删除 + streaming 脉冲点）
├── api.js（fetch 抽离：listSessions/createSession/deleteSession/renameSession/fetchMessages/streamChat）
└── main-panel
    ├── ChatWindow.vue（消息列表 + 自动滚动）
    │   └── MessageBubble.vue（单条气泡，user 右对齐；assistant 含 thinking / tools 折叠面板 + 主文本）
    └── InputBar.vue（输入框 + 发送按钮）
```

**多会话状态模型**：
- `sessions: ref([])` —— meta 列表（按 updated_at 倒序）
- `messagesBySession: reactive({})` —— `{ [id]: Message[] }`，懒加载
- `streamingBySession: reactive({})` —— `{ [id]: boolean }`，按会话独立
- `activeId: ref(null)` —— 当前显示的会话
- `messages` / `streaming` 通过 `computed` 跟随 `activeId` 投影

**并发流式**：`onSend` 闭包 capture `sessionId = activeId.value` 和对应的 `list = messagesBySession[sessionId]`，回调里只动 `list`，与 `activeId` 解耦 —— 切走仍正确累积；同一会话同时只能一个流（前端 `disable` + 后端 409）。

**SSE 事件 `title_update`**：首轮 assistant 文本回复完成后，后端会同步调用一次非流式模型生成 5–12 字标题，通过该事件推回；前端收到后更新 `sessions` 中对应项 title。

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
| `trace` | trace 控制台事件（`phase`, `iteration`, `message_id`, `ts`, `payload`） |
| `title_update` | 首轮自动生成的会话标题（`id`, `title`），仅触发一次 |
| `done` | 对话回合结束（`reason` 仅在达到 `max_iterations` 时存在） |
| `error` | 异常信息（同时回滚本次新增的历史行与消息元数据） |

### 数据流

1. 前端 POST `/api/sessions/{id}/chat` → 后端 `ChatService.stream(id, message)` agent loop
2. 每轮：OpenAI 流式 API → 逐 token yield SSE → 前端 ReadableStream 解析 → Vue 响应式驱动打字机效果
3. 工具调用时：yield tool_call → 执行工具 → yield tool_result → 继续下一轮 OpenAI 调用
4. 每条消息产生即逐条 append 入库到 `data/little-kitty.db` 的 `messages` 表

## No Tests

项目当前没有正式测试框架和单元测试。`kitty/tests/test_cli.py` 是手动调试用的交互 CLI，不是自动化测试。

## 开发约定

在本项目的所有代码开发工作中，请严格遵守以下协作规则：

- **全程持续审视代码**，主动识别代码坏味道、不合理设计、冗余逻辑、不规范写法、可优化点。
- **一旦判定当前代码需要重构，立刻暂停新增功能开发，不得直接修改代码**。
- 向我清晰输出两部分内容：
  1. **问题说明**：指出代码具体问题、属于哪类代码坏味道、带来的隐患 / 弊端；
  2. **重构方案**：给出具体优化思路、改动范围、重构后的效果。
- **仅在我明确同意、确认方案后**，你再按照方案执行代码重构；若我提出修改意见，同步调整方案后再操作。
- 若无重构必要，正常推进开发即可。

- **控制流嵌套不得超过 3 层**（if/for/while/with/try 各算一层，elif 同级不加深）。
