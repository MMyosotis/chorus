# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Little Kitty — 带上下文记忆的 AI 对话助手，支持 tool calling 和动态 skill 加载。前后端分离架构：后端 FastAPI + OpenAI SDK 提供 SSE 流式对话（含 agent loop），前端 Vue 3 + Vite 提供聊天界面。

后端按 Java OOP 风格分层：`domain`（领域模型 + 纯领域逻辑 + 围绕单一概念的基础设施型 service，如 skill 扫描缓存、title 调 OpenAI 生成）→ `tools`（工具子系统：模型 + 框架 + 内置工具 + 外部 client，依赖 `domain/skill`，规模较大故独立成顶层包）→ `repositories`（各表唯一 SQL 入口）→ `services`（应用 / agent 编排：取数据→调领域→存数据）→ `routes`（HTTP）。依赖单向 `routes → services → repositories → db`；`domain` 不依赖 `repositories`/`services`/`hooks`/`tools`，但允许直接持有围绕自身概念的外部依赖（文件系统 / openai / threading）。构造器注入，`create_app()` 内联装配（service 挂 `app.state`，中间对象为局部变量），无模块级全局单例。

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
cd web && npm install && npm run dev   # 安装依赖并启动开发服务器
cd web && npm run build                # 构建生产版本
```

### 环境变量
在 `.env` 中配置：
- `DEFAULT_CHAT_MODEL_ID` — 启动默认对话模型 + 标题生成固定模型（须是 `CHAT_MODELS` 中某条的 id，默认 `DeepSeek V4 Flash`）
- 对话模型密钥：`CHAT_MODELS` 每条用 `api_key_env` 指明取哪个环境变量（如 `DEEPSEEK_API_KEY` / `MINIMAX_API_KEY`），key 值写 `.env`，配置表只存变量名
- `ARK_IMAGE_API_KEY` — 火山方舟图像生成 API 密钥（`IMAGE_MODELS` 各条默认用此变量，与对话密钥解耦；某条生图模型也可指向独立变量）
- `IMAGE_TEST_FAKE_URL` — 图像测试模式下的固定返回 URL（默认是一张已知可用的橘猫图，可覆盖换图）。测试开关本身只在控制台「设置」中切换，默认关闭，进程级状态、重启回到关

> 对话模型表 `CHAT_MODELS` 与生图模型表 `IMAGE_MODELS` 均在 `kitty/config.py`，结构同构：每条含 `id`（展示名 + 存储键）/ `base_url` / `api_key_env` / `model_id`（真实 API 模型名）。新增/删除/换 provider 改这两张表即可。

## 数据存放位置

- 运行时数据根目录 `DATA_DIR = 项目根 / data/`（在 `kitty/config.py` 定义，gitignored，启动自动创建）
- `data/little-kitty.db` — `sessions` + `messages` + `traces` 三张表（会话库）
- `data/settings.db` — `settings` 表（进程级 KV 配置，独立库，与会话库解耦）
- `kitty/resources/skills/` — 技能 markdown（随源码版本管理，非运行时数据）

## Architecture

### 后端包结构 (`kitty/`)

| 包 / 模块 | 职责 |
|------|------|
| `config.py` | 从 `.env` 读取配置常量（含 `DATA_DIR`），纯静态值；`SKILLS_DIR` 在 `domain/skill/loader.py`（围绕 skill 概念，SkillLoader 默认扫描目录） |
| `app.py` | FastAPI 应用工厂 `create_app()`：内联装配所有 Repository / Service / Tool / Hook / ChatService（构造器注入，中间对象为局部变量），3 个 HTTP 需要的 service 挂 `app.state`；CORS、注册路由 |
| `startup.py` | `run_startup(skill_service, settings_service, session_service)`：装配后的启动副作用——技能扫描、设置回灌、会话元数据加载 |
| `domain/` | 领域层，**按业务概念扁平组织**，每个模块同放该概念的数据模型 + 纯操作 + 围绕该概念的基础设施型 service：`session`/`message`(sealed 联合 + `to_provider_dict()`/`build_provider_messages`/`build_history_view`)/`trace`/`skill`(`models` 纯模型 SkillSummary/SkillContent(含 from_markdown) + `loader` SkillLoader 扫盘缓存 + format_skill_hints 纯操作，单一概念内聚为包)/`events`(SSE sealed 联合)/`agent`(`AgentContext` 等 dataclass)/`prompt`(`SYSTEM_PROMPT` 默认文案 + `PromptContext`/`build_system_prompt`，多方信息收集在 application 层、拼装规则在此)/`title`(`clean_generated_title`/`normalize_title`/`STORED_TITLE_MAX_LEN` + `TitleGenerationService` 调 OpenAI 生成) |
| `tools/` | 工具子系统（领域模型 + 框架，但因规模大而独立成顶层包）：`models` 纯模型 ToolSchema/ToolCall/ToolResult + `framework` 选择规则 select_tool_schemas 与 Tool/ToolContext/ToolRegistry 框架 + `builtin/`(4 工具：load_skill / output_plan / generate_image / baidu_search) + `clients/`(ark_image / baidu_search 外部依赖封装)。依赖 `domain/skill`（`LoadSkillTool` 用 `SkillLoader`），单向，不反向被依赖 |
| `repositories/` | 各表唯一 SQL 入口（不持锁/缓存/业务校验）：`connection`(线程局部 sqlite)、`session`/`message`/`trace`/`settings` |
| `services/` | 应用 / agent 编排层（取数据→调 domain→存数据）：`session`、`chat`、`settings`（文件名无 `_service` 后缀，类名仍带 `Service`）。纯领域逻辑已剥离到 `domain/`；围绕单一概念的基础设施型 service（skill / title）也下沉到 `domain/`，工具框架与实现则在 `tools/` |
| `hooks/` | `base`(Hook 单方法基类)、`manager`(HookManager 7 个具名方法 `on_xxx` 按字面顺序调用该事件 hook、fail-open)、`registry`(`build_hooks` 装配 8 个 hook 打包成 `HookBundle`) + `builtin/` 8 个类化 hook |
| `routes/` | HTTP 路由 + `providers.py`(Depends 注入入口)：`sessions`、`chat`(SSE)、`settings`(/api/debug/test-mode) |
| `resources/skills/` | 技能 markdown（frontmatter: name/description/tags） |
| `tests/test_cli.py` | 手动调试 CLI（直接调 `ChatService.stream`，不经 HTTP） |

### Agent Loop (`services/chat.py`)

`ChatService.stream(session_id, user_message) -> Iterator[SseEvent]` 实现多轮工具调用循环，线性展开、每个 hook 调用点用注释标注副作用（plan 检验3 的生命周期图对应此函数）。hook 调用从 `HookManager.on_xxx(ctx)` 具名方法发起（不再经 `emit(Enum, ctx)` 反射分发），触发顺序写在各 `on_xxx` 方法的字面顺序里：

1. 记录入口前 messages 数量为回滚锚点；`on_loop_start` → AppendHook 把 user 消息 append 入库
2. 每轮 `on_iteration_start`（分配 message_id）→ `on_before_model_request`（MessageHook 调 `build_provider_messages` 写 `ctx.turn.provider_messages`；Trace 写 model_request）
3. 调 OpenAI 流式 API（消费 `ctx.turn.provider_messages`），模块函数 `consume_stream()` yield reasoning/token 事件、累积 text_parts / tool_calls / thinking
4. 纯文本回复（`finish_reason != "tool_calls"`）→ `on_assistant_text_response`（Trace 写 model_response；TextResponse append assistant 消息；Title 首轮生成标题）→ yield done，结束
5. 工具调用 → `on_tool_calls_detected`（Trace 写 model_response；ToolCall append assistant(tool_calls)、逐个执行工具、append tool 消息、yield tool_call/tool_result）→ 继续下一轮
6. 异常 → `on_loop_error`（Rollback 删除本轮新增 messages + traces，yield error）

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
- `SessionService` 编排三个 repo + 锁；删除会话经 `SessionService.delete`（带 CASCADE，不绕开锁）。

### Skill 系统

- `kitty/resources/skills/` 下放 markdown 文件，支持 frontmatter（name, description, tags）
- `SkillLoader` 启动时扫描缓存，`format_hints()` 生成摘要追加到 system prompt
- 模型通过 `load_skill` 工具按需加载完整 skill 内容
- `domain.prompt.build_system_prompt` 构造 system prompt（`SYSTEM_PROMPT` 默认文案 + skill hints），每次对话经 MessageHook 调 `build_provider_messages` 时刷新

### Tool 框架

- `Tool` ABC（`tools/framework.py`）：类属性 `name`/`description`/`parameters`，`run(arguments, ctx) -> str`；`ToolRegistry.dispatch()` 统一执行/计时/包错，`format_display()` 返回单行人类可读描述（前端 chip）。
- 内置工具与 client 同处 `tools/`：`builtin/`(load_skill / output_plan / generate_image / baidu_search) + `clients/`(ark_image / baidu_search urllib 封装)。
- `GenerateImageTool` 依赖 `SettingsService.get_image_test_mode`（测试模式返回写死 URL）、`ArkImageClient` 与注入的默认模型 id；`BaiduSearchTool` 依赖 `BaiduSearchClient`。

### 前端 (web/src/)

```
App.vue（双栏：sidebar + main-panel；多会话状态）
├── SessionSidebar.vue（260px 固定，新建/列表/切换/重命名/删除 + streaming 脉冲点）
├── api.js（fetch 抽离：listSessions/createSession/deleteSession/renameSession/fetchMessages/fetchTraces/streamChat/getTestMode/setTestMode）
└── main-panel
    ├── ChatWindow.vue（消息列表 + 自动滚动）
    │   └── MessageBubble.vue（单条气泡，user 右对齐；assistant 含 thinking / tools 折叠面板 + 主文本）
    ├── InputBar.vue（输入框 + 发送按钮）
    └── ConsolePanel.vue（trace 控制台面板，消费 useTraceStore 收集的 trace 事件）
（composables/useTraceStore.js — trace 事件聚合；styles/global.css — 全局样式；main.js — 入口）
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
- 切换会话时 `fetchMessages(id)` 会先调用 `mergeAssistantHistory()`：把连续的"无 content 的 assistant 轮次"thinking / tools 累积到下一条有 content 的 assistant 消息上，再调用 `normalizeAssistant()` 包装成前端结构；尾部若仍有未合并的中间轮（如异常中断），保留为独立气泡以免信息丢失。

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
| `done` | 对话回合结束（正常文本回复结束即发，无额外字段） |
| `error` | 异常信息（同时回滚本次新增的历史行与消息元数据） |

### 数据流

1. 前端 POST `/api/sessions/{id}/chat` → 后端 `ChatService.stream(id, message)` agent loop
2. 每轮：OpenAI 流式 API → 逐 token yield SSE → 前端 ReadableStream 解析 → Vue 响应式驱动打字机效果
3. 工具调用时：yield tool_call → 执行工具 → yield tool_result → 继续下一轮 OpenAI 调用
4. 每条消息产生即逐条 append 入库到 `data/little-kitty.db` 的 `messages` 表

## 测试

项目以 pytest 为 dev 依赖（`uv add --dev pytest`），但**不追求全覆盖**——只对纯领域函数 / 状态机 / repo smoke 用表驱动断言锚定（spec 第 8 节：「状态机/纯函数不测是最大浪费」）。测试文件在 `kitty/tests/`，用 `python -m kitty.tests.test_<name>` 跑（每个文件带 `main()` 入口聚合所有 `test_` 函数，可裸跑也可 pytest 跑）：

- `test_cli.py` — 手动调试交互 CLI（直接调 `ChatService.stream`，不经 HTTP），非自动化测试
- `test_chat_pipeline.py` — supervisor only_reply 顺序契约 smoke test（FakeOpenAIStream 脚本化 chunk）
- `test_task_state.py` — 任务图纯函数表驱动断言（状态机 / pipeline / PostCard）
- `test_task_repo.py` / `test_task_artifacts_steps.py` / `test_connection.py` / `test_trace_repo.py` / `test_message_repo.py` — 各 repo 的 smoke test

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

### 领域层与编排层分离

后端区分**领域层**（`domain/`）与**编排层**（`services/` + `routes/` + `hooks/` + `startup.py`），新增代码按下述原则归位：

- **领域层（`domain/`）按业务概念扁平组织**，每个模块同放该概念的 Pydantic 模型（带只读行为，如 `Message.to_provider_dict()`、`SkillContent.from_markdown()`）、跨对象的纯领域函数（如 `build_provider_messages`、`clean_generated_title`），以及**围绕该单一概念的基础设施型 service / loader**（如 `SkillLoader` 扫盘缓存 skill、`TitleGenerationService` 调 OpenAI 生成标题）。`domain` **不得 import** `kitty.repositories` / `kitty.services` / `kitty.hooks`，但允许直接持有围绕自身概念的外部依赖（文件系统 / `openai` / `threading`）——只要它服务于本概念、而非跨概念编排。
- **编排层负责"取数据 → 调领域 → 存数据"与 agent loop 流程控制**：`services/`（应用 / agent 编排，如 `SessionService` 跨三 repo + 锁、`ChatService` 驱动 agent loop）、`routes/`（HTTP 适配）、`hooks/`（agent loop 横切编排）、`startup.py`（启动副作用）都不承载领域规则，只做协调——从 repo/外部取数据，喂给领域函数/模型/service，再把结果存回或返回。`create_app()` 只装配（new + 注入），不含启动副作用。
- **判别准则**：一段逻辑若围绕**单一领域概念**（如 skill、title），即使它要扫文件 / 调 OpenAI / 持锁，也归 `domain/`，与该概念的模型和纯函数同模块；若它**跨多个概念编排**（驱动 agent loop 多轮循环、跨多 repo 事务、协调多个 service），归编排层。一句话："它服务于一个概念，还是粘合多个概念？"——前者领域，后者编排。
- **扩展时保持边界**：当编排层需要新的运行时多方信息（如 system prompt 要拼接对话摘要、用户画像），**收集信息是编排**（在 hook/service 里凑齐），**拼装规则是领域**（领域函数接收已收集好的数据）。用值对象（如 `PromptContext`）承载多方信息，避免领域函数参数爆炸、签名频繁变动。

### Agent Loop 编排边界

- **主流程单文件可读全**：agent loop 的主流程（append user → build messages → call model → persist response → execute tools → finalize）**必须在 `ChatService.stream()` 一个文件内顺序可读**，核心业务提交（落库、构建 prompt、执行工具、SSE 核心事件 yield）在 loop 内，不进 hook。
- **hook 是挂在稳定 loop 上的扩展点，不是主业务承载点**（遵循「挂在循环上，不写进循环里」）：loop 自己做主流程真身，hook 只做"前后织入 + 策略判断"。hook 收缩为扩展能力——观测（trace/日志/埋点）、收尾（title/summary）、异常恢复（rollback）；策略（权限拦截/上下文补充）、增强（输入注入/输出检查）为文档化的未来扩展点，**现不承载**。
- **机制是 CC 式扁平注册表**：`event → list[callable]` 字典 + `trigger(event, ctx, *args) -> Iterator[SseEvent]`，loop 只调 `trigger`。**不引入** `Hook` ABC + `HookBundle` 命名字段 + `HookManager` 转发方法这类 1:1 退化的三层胶水。当前 `trigger` 观测-only（只 yield 事件，fail-open 吞异常记日志）；引入策略/拦截类 hook 时，`trigger` 加 verdict 返回 + loop 在对应事件加 `if blocked` 分支（演进路径，现不写死代码分支）。
- **异常分级**：**核心步骤 fail-closed**（append user / 构建 prompt / 执行工具 / 落 assistant 消息——失败即上抛到外层 except，yield ErrorEvent 回滚本轮，绝不静默继续，否则产生"消息没落库但循环继续"的静默数据不一致）；**扩展 hook fail-open**（经 `trigger`，失败只记日志，不阻断主流程）。分级由"是否经 trigger"自然落地，无需显式配置。
- **顺序契约可测**：agent loop 重度依赖调用顺序与 `ctx.turn` 字段的读写时机，这类隐式契约**必须有用例锚定**（断言"给定输入 → 事件序列 + 入库消息序列"），改动主流程前先有安全网。

### Domain 内聚判据（红线）

- **单概念内聚留 domain，跨概念协调出 domain**：判别看**被操作的状态**而非 import 的类型——一段逻辑若只围绕单一概念操作其状态（哪怕要扫文件 / 调 OpenAI / 持锁，如 `SkillLoader` 只为 skill、`TitleGenerationService` 只为 title），归 `domain/`；若**同时操作两个以上领域概念的状态**（跨多 repo 事务、协调多 service），归编排层（`services/`）。
- **不引入 `application` / `infrastructure` / `interfaces` 等 Clean Architecture 目录名**：本项目按业务概念扁平组织，`routes` 已是 HTTP 适配、`repositories` 已是基础设施入口，换名不解决实际问题、只增导航成本。
- **防 domain 杂项化滑坡**：domain 里的 infra service（loader / 调外部 API 的概念内 service）必须**单一概念内聚**；一旦某对象长出跨概念协调，迁往 `services/`（编排层本就是跨概念协调的归宿），不新建目录。
