# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chorus — **多智能体爆款图文博文创作助手**：用户一句话主题 → supervisor 建任务图 → 子 agent 流水线创作（选题/文案/配图/汇总）→ HIL 人工确认 → PostCard 成品。前后端分离：后端 FastAPI + OpenAI SDK，三 loop 架构（supervisor SSE 流式 / subagent 后台线程 ReAct / scheduler 守护线程派发）；前端 Vue 3 + Vite 三栏布局（左会话侧栏 / 主对话+创作面板 / 右角色栏）。

**DB 是三 loop 间通信媒介与单一事实源**：supervisor 建图写 `tasks` 表，scheduler 轮询 `tasks` 派发，subagent 写 `task_artifacts`/`task_progress`/`messages`，前端轮询 `get_graph` 渲染角色栏/HIL 卡片/成品。状态翻转（pending/running/awaiting_confirm/finished/failed/cancelled）是协调核心。

后端按 Java OOP 风格分层：`domain`（领域模型 + 纯领域逻辑 + 围绕单一概念的基础设施型 service，如 skill 扫描缓存、title 调 OpenAI 生成、task 状态机/pipeline/PostCard 契约）→ `tools`（工具子系统：模型 + 框架 + 内置工具 + 外部 client，依赖 `domain/skill` 与 `services`（如生图模型选择查 SettingsService），规模较大故独立成顶层包）→ `repo`（各表唯一 SQL 入口）→ `services`（应用 / HIL 编排：取数据→调领域→存数据）→ `agents`（三 loop 编排：supervisor / subagent / scheduler + 运行时脚手架）→ `routes`（HTTP）。依赖单向 `routes → agents/services → repo → db`，`agents` 依赖 `services`/`domain`/`tools`/`hooks`；`domain` 不依赖 `repo`/`services`/`hooks`/`tools`/`agents`，但允许直接持有围绕自身概念的外部依赖（文件系统 / openai / threading）。构造器注入，`create_app()` 内联装配（service 挂 `app.state`，中间对象为局部变量），副作用经 lifespan，无模块级全局单例。

## Commands

### 后端
```bash
uv sync                                              # 安装依赖
.venv/bin/uvicorn chorus.app:app --reload --port 8000 # 启动开发服务器
./scripts/start.sh                                   # 同时启动前后端

# 意图链路端到端（真实 LLM 跑创作场景，验证拦截续跑 + intent_states 表写入 + 卡片数据）
.venv/bin/python scripts/e2e_intent_test.py

# 一键跑全部自动化测试（逐模块裸跑；也可 `.venv/bin/python -m pytest chorus/tests/`）
.venv/bin/python -m chorus.tests

# 重建产品库（drop_all + create_all，清空 data/chorus.db；结构变动后用，不保留旧数据）
.venv/bin/python scripts/reset_db.py
```

### 前端
```bash
cd web && npm install && npm run dev   # 安装依赖并启动开发服务器
cd web && npm run build                # 构建生产版本
```

### 环境变量
在 `.env` 中配置：
- 对话模型密钥：`CHAT_MODELS` 每条用 `api_key_env` 指明取哪个环境变量（如 `DEEPSEEK_API_KEY` / `MINIMAX_API_KEY`），key 值写 `.env`，配置表只存变量名
- `ARK_IMAGE_API_KEY` — 火山方舟图像生成 API 密钥（`IMAGE_MODELS` 各条默认用此变量，与对话密钥解耦；某条生图模型也可指向独立变量）
- `BAIDU_SEARCH_API_KEY` / `BAIDU_SEARCH_BASE_URL` — 百度智能搜索生成 API（`baidu_search` 工具用，base_url 默认千帆 endpoint）

> 对话模型表 `CHAT_MODELS`、生图模型表 `IMAGE_MODELS` 与标题生成固定模型 `TITLE_MODEL`（字面量，须是 `CHAT_MODELS` 中某条的 model_name）均在 `chorus/config.py`。`CHAT_MODELS` 每条含 `model_name`（展示名 + 存储键）/ `base_url` / `api_key_env` / `model_id`（真实 API 模型名）；`IMAGE_MODELS` 每条含 `model_name`（展示名 + 存储键）/ `provider`（选哪个 builder，见 `tools/image_model.py`）/ `options`（厂商私有：base_url / api_key_env / model_id）。新增/删除对话模型改 `CHAT_MODELS`；新增生图厂商 = 写 client + 注册 builder + config 标 provider。调度实现参数 `SCHEDULER_INTERVAL`/`ZOMBIE_TIMEOUT` 住 `agents/scheduler.py`（单组件硬编码，不进 config）。

## 数据存放位置

- 运行时数据根目录 `DATA_DIR = 项目根 / data/`（在 `chorus/config.py` 定义，gitignored，启动自动创建）
- `data/chorus.db` — 单一 SQLite 库，含 `sessions` + `messages` + `traces` + `tasks` + `task_artifacts` + `task_progress` + `settings` 全部表（会话库 + 进程级 KV 配置同库，项目规模不大不分库）
- `chorus/resources/skills/` — 技能 markdown（随源码版本管理，非运行时数据）

## Architecture

### 后端包结构 (`chorus/`)

| 包 / 模块 | 职责 |
|------|------|
| `config.py` | 从 `.env` 读取配置常量（含 `DATA_DIR`、三张模型表、调度参数），纯静态值；`SKILLS_DIR` 在 `domain/skill/loader.py`（围绕 skill 概念，SkillLoader 默认扫描目录） |
| `app.py` | FastAPI 应用工厂 `create_app()`：内联装配所有 Repository / Service / Tool / Hook / 三 Agent / Scheduler（构造器注入，中间对象为局部变量），HTTP 需要的 service 挂 `app.state`；CORS、注册路由、副作用经 `_build_lifespan` |
| `startup.py` | `run_startup(session_service, scheduler)`：装配后的启动副作用——会话元数据加载、scheduler.start()（技能扫描在 `SkillLoader` 构造时完成，设置回灌在 `SettingsService` 构造时完成） |
| `domain/` | 领域层，**按业务概念扁平组织**，每个模块同放该概念的数据模型 + 纯操作 + 围绕该概念的基础设施型 service：`session`/`message`(sealed 联合 + `to_provider_dict()`/`build_provider_messages`/`build_history_view`，支持 `progress`/`plan` 等 subtype)/`trace`(多来源：supervisor/subagent/scheduler，靠 `message_id` 与 `task_id` 关联)/`skill`/`events`(SSE sealed 联合)/`log`(分级日志薄封装 + 按层命名取 logger)/`intent`(会话级意图状态机：IntentState + IntentStatus empty→capturing→…→dispatched + derive_next_action status→next_action 派生不模型填 + IntentStatePatch)/`option`(会话级选项征询：主 agent 出选择题，作答后续跑 loop)/`title`/`stream`(`consume_stream` supervisor 用 / `silent_consume` subagent 用 / `drain_stream` 复用 + `StreamResult`)/`prompt`(`supervisor` SYSTEM_PROMPT + `PromptContext`/`build_system_prompt`；`subagent` 各角色 prompt)/`task`(`models` Task/TaskContent 带只读行为(can_schedule/render_invoke) + StepSpec/CreationIntent(expand_to_tasks) + PostCard 成品契约 + `state` LEGAL_TRANSITIONS/topological_order + `pipeline` validate_steps + `profiles` AGENT_PROFILES + AgentProfile.parse_output/build_artifacts + `progress` 运行期进度快照值对象(TaskProgress/dump_progress) + `errors`，单一概念内聚为包) |
| `tools/` | 工具子系统（领域模型 + 框架，但因规模大而独立成顶层包）：`models` 纯模型 ToolSchema/ToolCall/ToolResult + `framework` select_schemas_by_names 与 Tool/ToolContext/ToolDispatch（登记+查 schema+派发） + `builtin/`(7 工具：load_skill / list_skill / generate_image / baidu_search / create_plan / present_options / update_intent_state) + `clients/`(ark_image / baidu_search 外部依赖封装)。**所有工具（含 create_plan）经 `ToolDispatch` 统一登记/派发**，schema 按 `config.TOOL_WHITELISTS` 白名单暴露给各 agent。依赖 `domain/skill` 与 `services`（如生图模型选择查 SettingsService），单向，不反向被依赖 |
| `agents/` | **三 loop 编排层**（取数据→调 domain/LLM/工具→存数据 + agent loop 流程控制）：`supervisor`(SupervisorService SSE 流式，建图/only_reply 路由，原 ChatService 迁入改造)、`subagent`(SubAgentService 后台线程 ReAct，写库不连 SSE)、`scheduler`(TaskScheduler 守护线程轮询派发 + zombie 回收，裸线程派发（无并发上限）)、`loop`(AgentLoop 共享 kernel + `LoopStrategy` 协议 + `dispatch_tool_calls`，supervisor/subagent 共用)、`runtime`(AgentContext/TurnState/LoopOutcome 运行时脚手架，三 loop 共享)、`chat_model`(ChatModelProvider.get_entry 取当前对话模型，子 agent 与 supervisor 同走)。`__init__.py` 用 PEP 562 `__getattr__` 懒加载打破循环 import |
| `repo/` | 各表唯一 SQL 入口（不持锁/缓存/业务校验、事务边界=方法边界每方法一事务不跨表、不硬编码业务状态集合）：`engine`(Engine 装配 + 建连 PRAGMA)、`models`(SQLAlchemy 2 declarative Record 定义)、`base`(BaseRepository 收 Engine 注入与短 Session 事务样板 + `@read`/`@write` 装饰器自动开 Session 注入 db 决定是否提交)、`mapping`(Record↔domain 同名字段投影)、`session`/`message`/`trace`/`settings`/`task`/`task_artifacts`/`task_progress`/`task_content`/`intent_state`/`intent_confirmation`/`option` |
| `services/` | 应用 / HIL 编排层（取数据→调 domain→存数据）：`session`(会话元数据 CRUD + 标题归一)、`message`(消息/trace 编排 + `build_provider_messages` 唯一构建点)、`trace`(TraceService 编排 TraceRepository)、`settings`、`task`(HIL confirm/retry/cancel_pipeline + get_graph)、`intent_state`(意图状态读写 + 版本号 + 确认门禁)、`option`(选项征询：提问单创建/查询/作答翻转)。**无 agent loop**——loop 已下沉到 `agents/`；纯领域逻辑在 `domain/`，单概念 infra service（skill/title）在 `domain/`，工具在 `tools/` |
| `hooks/` | CC 式扁平注册表：`registry`(HookRegistry `event -> list[callable]` + `trigger` fail-open 分发，5 个事件点 BeforeModelRequest/AfterModelResponse/PreToolUse/PostToolUse/Stop) + 2 个 handler（`trace` TraceEmitter 观测 / `title` TitlePostProcessor 收尾，绑 `source=supervisor`）。**无 Hook ABC / HookBundle / HookManager 胶水**。load-bearing 收尾（轮首气泡 message_start、异常占位消息）不进 hook，归各自 `LoopStrategy` |
| `routes/` | HTTP 路由 + `providers.py`(Depends 注入入口)：`sessions`(CRUD + messages/traces 视图)、`chat`(SSE 流式)、`task`(任务图查询 + HIL 写 + ReAct 过程)、`agents`(/api/agents/profiles 角色档案视图)、`settings`(/api/debug/test-mode + /api/settings 模型选项)、`skills`(技能子文件读取，前端拉渲染外壳)、`sse`(SSE 序列化与流式响应包装) |
| `resources/skills/` | 技能 markdown（frontmatter: name/description/tags） |
| `tests/` | 自动化测试（前缀分组：`test_domain_*`/`test_repo_*`/`test_service_*`/`test_agent_*`/`test_tools_*`/`test_route_*`/`test_integration_*`/`test_hooks_*`/`test_app_*`，共 42 模块），共享工具 `_helpers.py`，一键入口 `__main__.py` |
| `scripts/e2e_intent_test.py` | 意图链路端到端（真实 LLM 跑创作场景，验证拦截续跑 + intent_states 表写入 + 卡片数据），非自动化测试 |

### 三 Loop 架构 (`agents/`)

三个 loop 各自单文件可读全，主流程线性展开、hook 调用点注释标注副作用。`AgentContext` 按生命周期细分（`agents/runtime.py`，三 loop 共享）：回合级固定输入留顶层；单轮累积状态收进 `TurnState`（每轮 `reset()`）；退出结果 `LoopOutcome`（载异常）。多智能体扩展字段：`task_id`（subagent 用）、`source`（hook 区分 supervisor/subagent 来源）。

#### 1. SupervisorService.stream (`agents/supervisor.py`，SSE 流式)

`stream(session_id, user_message, *, model, image_model, web_search) -> Iterator[SseEvent]` —— 用户对话入口，单轮决策：普通对话走原生 content 流式（only_reply）；创作请求经 `create_plan` 工具建任务图。loop 按 `isinstance(outcome, Reply|Terminal)` 分流，**不认识工具名、不认 Terminal 载荷类型**——工具副作用在工具内收口，主流程只管终止。

1. append user 消息 -> `while True` 每轮：`ctx.turn.reset(i)` + 分配 message_id -> `strategy.message_start` 发 `message_start` -> `build_system_prompt` + `MessageService.build_provider_messages` 写 `ctx.turn.provider_messages` -> `trigger("BeforeModelRequest")`
2. 调 OpenAI 流式 API（挂 `TOOL_WHITELISTS["supervisor"]` 选出的 schema），`consume_stream()` yield reasoning/token 事件、累积 text_parts / tool_calls
3. `trigger("AfterModelResponse")` → 无 tool_call → **only_reply**：append assistant 文本消息 → yield done → `trigger("Stop")`（标题生成）→ 结束
4. 有 tool_call → `SupervisorLoopStrategy.after_tools`（kernel `dispatch_tool_calls` 派发后调度）：collect-then-persist 成对落库（一条 assistant(tool_calls=[全部]) + N tool(result)）→ 全 Reply 则回传模型继续 loop；首个 Terminal → `_handle_terminal`（只 yield done + `trigger("Stop")`，不认载荷）→ 结束。建图全过程（`validate_steps` → `CreationIntent.expand_to_tasks` → 逐条 insert tasks）在 `create_plan` 工具 `run` 内，校验/落库失败返 `Reply(correction)` 由模型自纠
5. 异常 -> `except` 记 `ctx.outcome.exception` -> `strategy.on_error`（append `[Error]` 占位消息关闭本轮，写库失败静默）-> yield `ErrorEvent`

#### 2. SubAgentService.run (`agents/subagent.py`，后台线程，写库不连 SSE)

scheduler 占槽 pending->running 后 submit 到线程池。`run(task_id)`：load task -> setup（入口 lease 校验 + aside/label 进度快照 + `TaskContent.render_invoke` + 选 schema）-> `AgentLoop.run` 驱动最小回合自动机，业务差异（内存 history + `silent_consume` 静默消费 + 进度快照写入 + lease 终态写入）进 `SubagentLoopStrategy`：每轮 heartbeat + status 复查（协作式取消）-> 调模型 -> 无 tool_call 则 `AgentProfile.parse_output` + `_finalize`（lease 校验 -> 翻转 running->awaiting_confirm|finished -> 写 artifacts/narrative）-> 有 tool_call 则 `dispatch_tool_calls` + history 回灌 -> 异常经 `on_error` -> `_guarded_fail`（lease 校验 -> 翻转 running->failed）。**与 supervisor 共享 `AgentLoop` kernel**（最小回合自动机 + `dispatch_tool_calls`），决策模式差异全进各自 `LoopStrategy`。横切经扁平 hook，ctx 带 `source=subagent + task_id`；hook 事件用 `list()` 消费丢弃（subagent 不连 SSE，trace 已在 hook 内写库）。subagent 历史只在内存 + `task_progress` 表，**不进 messages**；ReAct 轮次号仅内存计数（撞 `_MAX_STEPS` 用），不落库不喂 trace。

关键设计：
- **协作式取消**：每轮迭代复查任务态，状态漂移（如已 cancelled）立即早退，不残留孤儿产物。
- **_finalize lease 校验先于产物落库**：先 lease 校验通过再翻转 running->终态 + upsert artifacts/narrative；lease 失效（状态漂移/被回收重抢）则不落产物，避免孤儿 artifacts。
- 子 agent 与 supervisor 同走 SettingsService 当前对话模型（不按角色分模型），经 `ChatModelProvider.get_entry()` 取。

#### 3. TaskScheduler (`agents/scheduler.py`，守护线程，无 LLM 无 hook)

`start()` 幂等：先 zombie 回收，再周期 `_tick`。无 LLM loop、无事件点可挂 hook--schedule 事件（dispatch/zombie_reclaim）直接内联 `trace.add` 写库。无并发上限：每个可调度 task 直接 `threading.Thread` 起线程跑 `subagent.run`（守护线程）。占槽 `claim` 设 running + 写 owner_id，行已不存在则跳过下轮再试。zombie 回收：running task 心跳超 `ZOMBIE_TIMEOUT` 视为僵死，翻转 running->failed。lifespan 退出时 `scheduler.stop()`。

#### 共用约定
- 路由用同步 `def`，FastAPI 线程池执行；消息逐条 append 入库（产生即入库）。同 session 的 messages 写入靠前端 disable 单流兜底（无后端会话锁强制），`MessageService` 直接 `append` 一次直写。
- **无会话级锁**：同会话并发 chat 无后端强制串行，靠前端 `disable` 兜底；sqlite `busy_timeout` 防写冲突 corruption，但不保证消息顺序与上下文一致。subagent/scheduler 写 task_artifacts/task_progress，不经 chat 路径。
- **一条用户交互链路 = 一个前端 assistant 气泡**。supervisor 每个 OpenAI 轮次仍各自落一条 assistant 历史消息，前端将同一用户消息之后、HIL 挂起/续跑期间的轮次归并为同一气泡；`message_start` 只标记流式轮次开始。thinking/tools 元数据由 `TraceRepository.aggregate_message_trace(message_id)` 重建。
- `MessageService.build_provider_messages()` 是传给 LLM 的消息序列**唯一**构建点：`[system] + 按 seq 的 user/assistant/tool 历史消息`。
- **异常分级**：核心步骤 fail-closed / 工具可预料失败返 `Reply` 让模型重试 / 意外异常与扩展 hook fail-open（详见「Agent Loop 编排边界」）。

### 意图状态链路（会话级工作记忆）

主 agent 每轮调 `update_intent_state` 工具，把对用户意图的理解写进 `IntentState`（创作字段 / `intent_status` / `progress_percent`），独立于 message history 存 `intent_states` 表（每会话一行最新快照，CASCADE 随会话删）。

- 状态机 `IntentStatus`：empty → capturing →（needs_clarification | ready_to_confirm）→ confirmed → dispatched。`next_action` 由 status 经 `derive_next_action` 单一映射派生，**不让模型填**——避免 status 与 next_action 不自洽。此即「去代码强制」：意图流程由模型经工具 + 状态机驱动，不在 Python 里硬编码分支。
- `update_intent_state`（supervisor 白名单首位）是注册型 builtin 工具，只更新意图状态、不建任务；`IntentStateService` 负责读写 + 版本号 + 确认门禁。建图仍由 `create_plan` 在 confirmed（next_action=create_plan_after_confirm）后触发。
- 前端：`IntentConfirmCard`（main-panel 确认门）+ `IntentStateCard`（team-panel 意图状态展示）。

### 存储层

- `build_engine`：SQLAlchemy Engine，建连时开 PRAGMA（WAL + NORMAL 同步 + 外键约束 + busy_timeout），并按 Record 定义幂等建全部表（替代旧的线程局部连接工厂）。
- 各 repo 是各自表的唯一 SQL 入口，返回 Pydantic 领域模型（Record↔domain 双向映射在 repo 内收口：同名字段经 `shared_fields` 投影，各 repo 继承 `BaseRepository` 复用 Engine 注入与事务样板，方法标 `@read`/`@write` 装饰器自动开短 Session 注入 db 并按读/写决定是否提交--防漏 commit），**事务边界=方法边界（短 Session + 每方法显式 commit，不跨表）、不硬编码业务状态集合**（状态集合由 service 从 domain 传入，如 `cancel_pipeline(pipeline_id, CANCELLABLE_STATUSES)`）：`SessionRepository` / `MessageRepository` / `TraceRepository` / `SettingsRepository` / `TaskRepository`(`transition`/`claim` + `cancel_pipeline` + `find_by_session_statuses` + `count_by_session_statuses`) / `TaskArtifactsRepository` / `TaskProgressRepository` / `TaskContentRepository` / `IntentStateRepository` / `IntentConfirmationRepository` / `OptionPromptRepository`。
- `messages` 表按消息粒度（user/assistant/tool）逐条 `append` 入库，支持 `progress`/`plan` 等 subtype；`traces` 表靠 `message_id` 与 `task_id` 双键关联，多来源（supervisor/subagent/scheduler）。
- `tasks` 表是三 loop 通信媒介：状态翻转是协调核心；`task_artifacts` 存产物/selected，`task_progress` 存运行期进度快照（一任务一行 upsert，字数/结构单元/临时信号/意图旁白）。ReAct 原始过程由 `traces` 表（model_request/model_response/tool_call/tool_result）覆盖，无独立 steps 表。
- `SessionService` 编排 session repo；删除会话经 `SessionService.delete`（带 CASCADE 级联清消息/轨迹）。

### Skill 系统

- `chorus/resources/skills/` 下放 markdown 文件，支持 frontmatter（name, description, tags）
- `SkillLoader` 启动时扫描缓存，`format_hints()` 生成摘要追加到 system prompt
- 模型通过 `load_skill` 工具按需加载完整 skill 内容
- `domain.prompt.build_system_prompt` 构造 system prompt（`SYSTEM_PROMPT` 默认文案 + skill hints），每次对话经 MessageHook 调 `build_provider_messages` 时刷新

### Tool 框架

- `Tool` ABC（`tools/framework.py`）：类属性 `name`/`description`/`parameters`，`run(arguments, ctx) -> str`；`ToolDispatch.dispatch()` 统一执行/计时/包错，`format_display()` 返回单行人类可读描述（前端 chip）。
- `ToolDispatch`（`tools/framework.py`，由 `tools/registry.py` 的 `build_tool_dispatch` 装配）注册 7 工具（load_skill / list_skill / generate_image / baidu_search / create_plan / present_options / update_intent_state），`select_schemas(names)` 按 `config.TOOL_WHITELISTS` 白名单为各 agent 选 schema：supervisor 与 subagent 都从同一 registry 取，白名单**按角色分**（supervisor + idea/script/image/finalize），supervisor 白名单 = update_intent_state + create_plan + present_options。
- `create_plan` 是**注册型 builtin 工具**（`tools/builtin/create_plan.py`，对模型是普通工具：有 schema、被 dispatch、有 trace、tool_call 落库），建图全过程（`validate_steps` → `CreationIntent.expand_to_tasks` → 逐条 insert tasks）在工具 `run` 内收口，校验/落库失败返 `Reply(correction)` 由模型自纠；supervisor 主流程只据 `Terminal` 终止本轮、不认载荷类型。
- 内置工具与 client 同处 `tools/`：`builtin/`(load_skill / list_skill / generate_image / baidu_search / create_plan / present_options / update_intent_state) + `clients/`(ark_image / baidu_search urllib 封装)。
- `GenerateImageTool` 依赖 `SettingsService.get_image_test_mode`（测试模式返回写死 URL）、`ArkImageClient` 与注入的默认模型 id；`BaiduSearchTool` 依赖 `BaiduSearchClient`。

### 前端 (web/src/)

三栏布局：左 `SessionSidebar`（会话侧栏）/ 中 `main-panel`（对话 + 创作）/ 右 `TeamPanel`（角色栏）；`ConsolePanel`/`SettingsPanel` 为浮层。

```
App.vue（三栏 + 多会话状态 + task 轮询编排）
├── SessionSidebar.vue（新建/列表/切换/重命名/删除 + streaming 脉冲点 + 设置入口）
├── NavDock.vue（全局导航 dock）
├── main-panel/
│   ├── ChatWindow.vue（消息列表，按 kind 分支：hil->HilCard / postcard->ArtifactCard / confirmed->ConfirmedCard / recovery->RecoveryCard / 否则 MessageBubble）
│   │   ├── MessageBubble.vue（单条气泡，user 右对齐；assistant 含 thinking/tools 折叠 + 主文本）
│   │   ├── HilCard.vue（awaiting_confirm 候选/预览/缩略图 + 确认/重跑/放弃）
│   │   ├── ArtifactCard.vue（postcard 成品卡片，markdown 渲染走 composables/renderPostCard）
│   │   ├── ConfirmedCard.vue（已确认任务回看）
│   │   └── RecoveryCard.vue（异常/中断恢复引导）
│   ├── RunningPanel.vue（任务图运行进度，原 ProgressBanner）
│   ├── InputBar.vue（输入框 + 发送按钮）
│   ├── ConsolePanel.vue（trace 控制台，按来源分组、组内按时间顺序 + 打开时轮询补 subagent/scheduler 未连 SSE 的 trace）
│   ├── PlatformPreviewShell.vue（平台预览外壳，支持图集）
│   ├── ManuscriptHeader.vue（文稿头部）
│   ├── OptionCard.vue（选项征询卡片）
│   ├── HilRecap.vue（HIL 回看）
│   ├── IntentConfirmCard.vue（意图确认门）
│   └── ScriptProof.vue（文案校对）
├── team-panel/
│   ├── TeamPanel.vue（角色栏容器）
│   ├── AgentAvatar.vue（角色头像 + 标签，按 agentType/status 渲染，原 RoleCard）
│   ├── IntentStateCard.vue（意图状态展示）
│   ├── PipelineTimeline.vue（任务图时间线）
│   ├── ArtifactsCard.vue（产物汇总，点击聚焦任务）
│   ├── roleMeta.js（status->徽章/标签映射集中处）
│   └── styleTags.js（样式标签映射）
├── SettingsPanel.vue（modal：对话/生图模型 + 联网搜索开关）
├── api.js（fetch 抽离：sessions CRUD + messages/traces + streamChat + 模型选项 + getTaskGraph/confirmTask/retryTask/cancelPipeline）
└── composables/
    ├── useTaskPolling.js（每会话任务图轮询，非流式时顺带刷新消息）
    ├── useTraceStore.js（trace 单例 store，按会话聚合）
    ├── renderPostCard.js（PostCard 成品 markdown 渲染单一来源）
    ├── messageHistory.js（助手历史消息规整/合并成单气泡）
    ├── taskCardProjection.js（任务图快照到对话区虚拟卡投影）
    ├── artifactsProjection.js（任务图快照到右栏创作产出段投影）
    ├── anchoredCards.js（虚拟卡片插在其触发的助手消息之后）
    ├── bindShell.js（mustache 风格槽位绑定）
    └── messageActivity.js（assistant 活跃度判定）
```

**多会话状态模型**（`App.vue`）：
- `sessions: ref([])` —— meta 列表（按 updated_at 倒序）
- `messagesBySession: reactive({})` —— `{ [id]: Message[] }`，懒加载
- `streamingBySession: reactive({})` —— `{ [id]: boolean }`，按会话独立
- `activeId: ref(null)` —— 当前显示的会话；`messages`/`streaming`/`activeGraph` 经 `computed` 跟随 `activeId` 投影

**并发流式**：`onSend` 闭包 capture `sessionId = activeId.value` 和对应 `list`，回调里只动 `list`，与 `activeId` 解耦——切走仍正确累积；同一会话同时只能一个流（前端 `disable`）。

**任务轮询编排**（`useTaskPolling` + `App.vue`）：
- `done` 后 `forceReloadMessages` 取回非流式 friendly_reply/progress 气泡并启动/继续轮询；建图产物靠轮询 `get_graph` 渲染角色栏/HIL 卡片/成品。
- subagent/scheduler **不连 SSE**，其产物（awaiting_confirm / finalize finished task）不在 messages 表 → `injectTaskCards` 把这类 task 映射成虚拟消息条目（`kind: 'hil'|'postcard'`）注入 `messagesBySession[id]` 流，供 ChatWindow 内嵌 HilCard/ArtifactCard；每次刷新先清旧虚拟条目再按 graph 重建。
- `configure({ isStreaming, reloadMessages })`：流式时停轮询、靠 SSE 推进；非流式时 tick 拉取 graph + 重拉 messages。切走会话 `active=false` 自停。

**assistant 消息前端结构** `{ role, content, thinking: { state, items, expanded }, tools: { state, items, expanded } }`：
- `thinking.items[i] = { text, duration_ms }`，`reasoning` token 持续追加到当前段，`reasoning_done` 写 `duration_ms`。
- `tools.items[i] = { id, name, arguments, duration_ms, content, display }`，`tool_result` 经 `id` 匹配回 `tool_call`。
- 流式期间 `message_start`：先把上一轮 running 收尾；当前气泡还没产出 `content` 则复用它（让本轮 thinking/tools 累积进同一气泡），否则 push 新气泡——避免"只有思考/工具、无正文"的空壳气泡合并到下一个有正文的气泡。
- 切换会话 `fetchMessages(id)` 先 `mergeAssistantHistory()`：连续"无 content 的 assistant 轮次"thinking/tools 累积到下一条有 content 的 assistant 消息上，再 `normalizeAssistant()` 包装；尾部未合并中间轮（异常中断）保留为独立气泡。

SSE 解析用 `fetch` + `ReadableStream`（不用 EventSource，因为 POST）。Vite 开发代理 `/api` → `http://localhost:8000`。前端无测试框架，门 = `npm run build` + 后端回归 + TestClient lifespan。

### SSE 事件类型

| type | 说明 |
|------|------|
| `message_start` | 新一轮 supervisor assistant 消息开始（含 `id`），前端据此创建新气泡 |
| `reasoning` | 思考阶段 token 片段（`delta.reasoning_content`），归属到当前气泡 |
| `reasoning_done` | 当前思考段结束（含 `duration_ms`） |
| `token` | 流式正文文本片段，归属到当前气泡 |
| `tool_call` | 模型请求调用工具（`id`, `name`, `arguments`, `display`） |
| `tool_result` | 工具执行结果（`tool_call_id`, `name`, `content`, `duration_ms`） |
| `trace` | trace 控制台事件（`phase`, `message_id`, `task_id`, `source`, `ts`, `payload`） |
| `title_update` | 首轮自动生成的会话标题（`id`, `title`），仅触发一次 |
| `done` | 对话回合结束（正常文本回复结束即发，无额外字段） |
| `error` | 异常信息（`SupervisorLoopStrategy.on_error` 已 append 一条 `[Error]` 占位消息关闭本轮--失败轮 assistant 本就未入库，库内干净，不截断历史） |

### 数据流

1. 前端 POST `/api/sessions/{id}/chat` → `SupervisorService.stream(id, message)` → SSE 流回前端
2. **普通对话**：supervisor only_reply → 逐 token yield SSE → 前端打字机 → done
3. **创作请求**：supervisor 解析 create_plan -> 建图落库 -> yield `done`；前端 `done` 后启动 `useTaskPolling`
4. **后台流水线**：scheduler 轮询 `tasks` -> 占槽 pending->running -> submit `SubAgentService.run`（后台线程 ReAct，写 task_progress/task_artifacts）-> 翻转 running->awaiting_confirm|finished|failed；subagent/scheduler 不连 SSE，前端靠轮询 `get_graph` + 重拉 messages 驱动角色栏/HIL 卡片/成品
5. **HIL**：前端 `confirm`/`retry`/`cancel` → `TaskService` 翻转 → scheduler 下轮派发； awaiting_confirm/finalize-finished task 经 `injectTaskCards` 注入消息流
6. 每条 supervisor 消息产生即逐条 append 入库到 `data/chorus.db` 的 `messages` 表

## 测试

项目以 pytest 为 dev 依赖（`uv add --dev pytest`），但**不追求全覆盖**——只对纯领域函数 / 状态机 / repo smoke / 关键编排路径用表驱动断言锚定（spec 第 8 节：「状态机/纯函数不测是最大浪费」）。测试文件在 `chorus/tests/`，**按层前缀分组**（`test_domain_*` / `test_repo_*` / `test_service_*` / `test_agent_*` / `test_tools_*` / `test_route_*` / `test_integration_*` / `test_hooks_*` / `test_app_*`），每个文件带 `main()` 入口聚合所有 `test_` 函数。运行方式：

- 单文件：`python -m chorus.tests.test_<name>`（裸跑）
- 一键全跑：`python -m chorus.tests`（逐模块裸跑 + 汇总）或 `python -m pytest chorus/tests/`（pytest 收集）

文件清单（每个文件首行 docstring 注明用途与覆盖范围）：

- `test_domain_task.py` — 任务图纯函数：PostCard 契约 / 状态机 LEGAL_TRANSITIONS / Task.can_schedule / 状态集合 / select_display_pipeline / AgentProfile 注册表与 parse_output / pipeline 校验-展开-渲染
- `test_domain_intent.py` — 意图状态机：IntentStatus 流转 / derive_next_action status->next_action 派生 / IntentStatePatch
- `test_domain_option.py` — 选项征询：提问单创建与作答翻转
- `test_domain_prompt.py` — 系统提示词拼装：supervisor（含 create_plan + profiles 注入）/ subagent 各角色（ARTIFACTS/NARRATIVE 锚点 + 禁 emoji）
- `test_domain_aside.py` / `test_domain_log.py` / `test_domain_markdown.py` / `test_domain_stream.py` / `test_domain_message.py` / `test_domain_title.py` / `test_domain_events.py` / `test_domain_skill.py` — 各 domain 纯函数 smoke（旁白 / 日志 / markdown 渲染 / 流消费 / 消息 / 标题 / 事件 / 技能）
- `test_repo_connection.py` / `test_repo_message.py` / `test_repo_trace.py` / `test_repo_task.py` / `test_repo_task_artifacts.py` / `test_repo_task_progress.py` / `test_repo_task_content.py` / `test_repo_intent_state.py` / `test_repo_intent_confirmation.py` / `test_repo_option.py` — 各 repo 的 smoke test（哑查询 / cancel_pipeline / 多来源 trace / 意图状态与确认留档 / 选项留档等）
- `test_service_task.py` / `test_service_session.py` — HIL 与会话 CRUD 的编排层 smoke
- `test_agent_subagent.py` / `test_agent_scheduler.py` / `test_agent_supervisor.py` / `test_agent_supervisor_isolation.py` / `test_agent_runtime.py` / `test_agent_loop.py` / `test_agent_progress.py` — 三 loop + 运行时状态契约 + loop kernel + 隔离 + 进度快照写入
- `test_app_assembly.py` — `create_app()` 装配契约（service 挂 app.state / lifespan 副作用）
- `test_tools_select.py` / `test_tools_create_plan.py` / `test_tools_outcome.py` / `test_tools_list_skill.py` / `test_tools_present_options.py` — 工具 schema 选择 / 建图工具 / 工具 outcome 分级 / 技能枚举 / 选项征询
- `test_hooks.py` — 扁平注册表 trigger 分发
- `test_route_task.py` / `test_route_intent_confirmation.py` / `test_route_option.py` — task / 意图确认 / 选项 路由 HTTP 适配（404/422 映射）
- `test_integration_pipeline.py` — 端到端 4 链路 smoke（建图->subagent->confirm->scheduler 派发，FakeClient 模拟 LLM）
- `_helpers.py` — 共享 `fresh_conn()` / `seed_session()`（临时 DB + sessions 父行种子）；`__main__.py` — 一键跑全入口

## 回答风格

- 我提问时，优先用直白简洁的语言给出结论，不主动铺陈代码细节与文件引用。
- 只有当我明确要求结合代码 / 详细解释时，再附代码、行号与逐段说明。

## 模型能力边界

- **本会话模型无图像识别能力，严禁调用截图功能**：不使用 `browser_take_screenshot` 等截图工具，也不以截图作为判读依据；验证前端改动改用 Playwright MCP 文本类工具（`browser_snapshot` 无障碍树 / `browser_click`·`browser_type` 驱动交互 / `browser_console_messages` 控制台 / `browser_network_requests` 网络）配合源码阅读。

## 开发约定

在本项目的所有代码开发工作中，请严格遵守以下协作规则：

- **全程持续审视代码**，主动识别代码坏味道、不合理设计、冗余逻辑、不规范写法、可优化点。
- **一旦判定当前代码需要重构，立刻暂停新增功能开发，不得直接修改代码**。
- 向我清晰输出两部分内容：
  1. **问题说明**：指出代码具体问题、属于哪类代码坏味道、带来的隐患 / 弊端；
  2. **重构方案**：给出具体优化思路、改动范围、重构后的效果。
- **仅在我明确同意、确认方案后**，你再按照方案执行代码重构；若我提出修改意见，同步调整方案后再操作。
- 若无重构必要，正常推进开发即可。
- **E2E 临时库跑完自动清理**：`scripts/e2e_*.py` 用临时库隔离（不写 `data/chorus.db`），atexit 跑完即净，无需询问。**只有写产品库 `data/chorus.db` 的测试**（如前端 Playwright E2E 真跑）产生的会话与数据，跑完先询问是否删除，不自动清理。

- **提交后默认合入主分支**：完成代码提交后，默认把从分支 fast-forward 合入 `main` 并删除从分支，除非我明确说保留在从分支上。

- **控制流嵌套不得超过 3 层**（if/for/while/with/try 各算一层，elif 同级不加深）。

- **减少不必要的防御分支**：写 `if`/`raise` 前先判断该分支是否真有路径到达，针对走不到的路径写防御是死代码。判据是追踪参数来源：上游已保证非空（如 `ToolContext.session_id` 来自非 Optional 的 `AgentContext.session_id`、路由已 404 校验）、调用方硬编码字面量（如路由传的 signal 不可能是非法值）、生产装配总注入的依赖，这些路径上不要写 `if`/`raise`。但真实业务分支保留：工具内可预料失败返 `Reply` 让模型重试、校验失败返 correction、lease 校验等。
- **生产代码不准出现给测试的专属逻辑**：生产装配总注入的依赖必填（不得 `=None` 默认、非 Optional），不得有为测试兜底的 `if xxx is None` 守卫；测试需要降级行为时由测试侧注入 stub（如 `_helpers.stub_*`），生产代码不兜底。

### 代码风格

**注释规范**：

1. **文件头注释内容不超过 3 行**（docstring 三引号起止行不计，只数注释文字行）。
2. **函数/方法内首行 docstring 不超过 1 行**——多段说明、调用顺序罗列、返回值复述都算违规。
3. **`#` 单行注释要简短，且只允许出现在函数或类内部**，不得出现在模块顶层（定义之间）。
4. **用可读性好的中文**，除共识词（agent / SSE / HIL / ReAct / pipeline / scheduler / subagent / supervisor / hook / trace / prompt / token / lease / zombie / PostCard / KV 等）外，不要把变量名/标识符/类名/事件名写进注释，换中文概念表述（如「上下文」「单轮」「终止信号」）。
5. **能自注释的内容不再写注释**——返回类型已说明的返回值、方法名已表达的作用、`hasXxx`/`isXxx` 布尔方法、代码本身可见的设计属性，都不重复写。
6. **写完用 `git diff` 逐条扫新增的 `#` / `//` / `/*` / `"""`，逐条对照上述自检**——不要写完就交。CSS 注释作分区可留，但不得含 rationale。

**单字母命名**：

- 无含义单字母一律改简短实名，覆盖：`for <单字母> in` 循环变量（含推导式）、**元组解包循环变量**（`for c, d in pairs`，非 dict 惯用法）、**函数参数**、**lambda 参数**、**单字母局部变量**（`q = ...` / `n = len(...)` / `p = AGENT_PROFILES[...]`）。按上下文定名：`p`→path/profile/part、`t`→task/tool/call/trace、`r`→row/ref、`s`→skill/session/summary、`m`→message/model、`k`（在 `XxxRecord.__table__.columns` 中）→field、`d`→dep/dispatch、`n`→count、`q`→query、`c`→call/created、`g`→graph、`a`→aside、`v`→view、`e`→event。两字母缩写（如 `td`）同样费解，一并清理。
- **保留的惯用单字母**：`i`（索引）、`k`/`v`（`for k, v in d.items()` dict 解包）、`_`（丢弃占位）、`except ... as e:`（异常对象）。
- 改名时注意不要遮蔽同函数 `Depends()` 注入的参数名——此时挑更精准的名（如 `SessionSummary` 项→`summary`、`TraceEntry` 项→`entry`）而非套映射。

### 前端 UI 规范

**字体**：

- 字体族：中文移动端优先苹方（`PingFang SC`）、桌面端微软雅黑（`Microsoft YaHei`），英文推荐 `Inter`；单个界面字体种类控制在 2 款以内。
- 字号一律取偶数，避免真机边缘模糊。层级：大标题 `24/28/32px`、页面/正文标题 `18/20px`、常规正文 `14/16px`、辅助说明/小标签 `12px`。
- 行高：正文为字号的 `1.5-1.6` 倍，标题 `1.2-1.3` 倍。

**间距（8px 黄金法则）**：

- 元素间距、内边距、外边距都必须是 8 的倍数（`8/16/24/32px`），杜绝 `15px`、`22px` 这类非 8 倍数值。

> 改前端样式时先对照本节自检字号是否偶数、间距是否 8 的倍数，再提交。

### 提交信息规范

遵循 Conventional Commits，正文用**混合三段式**（段可缺省，简单提交留空正文）：

```
<type>(<scope>): <subject>

背景：<动机 / 上下文，可缺省>

改动：
- <变更点，统一 - bullet>

影响：<值得注意的后果，可缺省>
```

- **标题**：`<type>(<scope>): <subject>`，type 取 feat/fix/refactor/chore/docs/test 等，中文描述变更
- **正文三段**：以「背景：」「改动：」「影响：」起头，**三段之间空一行**（标题与首段之间也空一行，缺省段连同其空行一并省略）；「改动：」是核心（有正文则必有，`-` bullet 列变更点），「背景：」「影响：」仅在有内容时写、不凑数；标题自解释的简单提交正文留空
- **禁写三类一次性内容**：测试结果尾巴（「N 模块全绿」「build 通过」）、一次性 DB 迁移说明（「已重建 chorus.db」）、旧 commit hash 引用（历史重写后 hash 指向错误提交，改描述性表述如「去事务那次改动」）
- **不带 trailer**：不附加 `Co-Authored-By` 等署名 trailer

### 领域层与编排层分离

后端区分**领域层**（`domain/`）与**编排层**（`services/` + `routes/` + `hooks/` + `startup.py`），新增代码按下述原则归位：

- **领域层（`domain/`）按业务概念扁平组织**，每个模块同放该概念的 Pydantic 模型（带只读行为，如 `Message.to_provider_dict()`、`SkillContent.from_markdown()`）、跨对象的纯领域函数（如 `build_provider_messages`、`clean_generated_title`），以及**围绕该单一概念的基础设施型 service / loader**（如 `SkillLoader` 扫盘缓存 skill、`TitleGenerationService` 调 OpenAI 生成标题）。`domain` **不得 import** `chorus.repo` / `chorus.services` / `chorus.hooks`，但允许直接持有围绕自身概念的外部依赖（文件系统 / `openai` / `threading`）——只要它服务于本概念、而非跨概念编排。
- **编排层负责"取数据 → 调领域 → 存数据"与 agent loop 流程控制**：`agents/`（三 loop 编排：supervisor/subagent/scheduler）、`services/`（应用 / HIL 编排，如 `SessionService` 跨 repo、`TaskService` HIL + get_graph）、`routes/`（HTTP 适配）、`hooks/`（agent loop 横切扩展点）、`startup.py`（启动副作用）都不承载领域规则，只做协调——从 repo/外部取数据，喂给领域函数/模型/service，再把结果存回或返回。`create_app()` 只装配（new + 注入），不含启动副作用。
- **判别准则（看被操作的状态而非 import 的类型）**：一段逻辑若围绕**单一领域概念**操作其状态（如 skill、title，哪怕要扫文件 / 调 OpenAI / 持锁），归 `domain/`，与该概念的模型和纯函数同模块；若**同时操作两个以上领域概念的状态**（驱动 agent loop 多轮循环、跨多 repo 协调、协调多 service），归编排层。一句话："它服务于一个概念，还是粘合多个概念？"——前者领域，后者编排。
- **防 domain 杂项化滑坡**：domain 里的 infra service（loader / 调外部 API 的概念内 service）必须单一概念内聚；一旦长出跨概念协调，迁往 `services/`（编排层本就是跨概念协调的归宿），不新建目录。
- **扩展时保持边界**：当编排层需要新的运行时多方信息（如 system prompt 要拼接对话摘要、用户画像），**收集信息是编排**（在 hook/service 里凑齐），**拼装规则是领域**（领域函数接收已收集好的数据）。用值对象（如 `PromptContext`）承载多方信息，避免领域函数参数爆炸、签名频繁变动。

### Agent Loop 编排边界

- **最小回合自动机抽 kernel，业务语义进 strategy**：supervisor / subagent 共享 `AgentLoop.run`（`agents/loop.py`）驱动的最小回合自动机——准入 → reset → message_start 门 → 拼消息选 schema → BeforeModelRequest → 调模型 → 消费流 → AfterModelResponse → 工具/文本分流 → 终止判定；divergent 节点（历史来源、持久化、stream 消费方式、终态写入、progress）全进各自 `LoopStrategy`（`SupervisorLoopStrategy` / `SubagentLoopStrategy`）。**kernel 零 agent 分支**——不许出现 `if ctx.source == ...` / `isinstance(strategy, ...)`，出现即抽象失败，降级为只保留 `dispatch_tool_calls` + 模型调用 helper 两层。各 service 主流程（`SupervisorService.stream` / `SubAgentService.run`）退化为「入口准入 + 构造 strategy + 跑 kernel」，单文件可读；核心业务提交（落库、构建 prompt、执行工具、SSE 核心事件 yield）在 kernel/strategy，不进 hook。
- **hook 是挂在稳定 loop 上的扩展点，不是主业务承载点**（遵循「挂在循环上，不写进循环里」）：loop 自己做主流程真身，hook 只做"前后织入 + 策略判断"。hook 收缩为扩展能力--观测（trace/日志/埋点）、收尾（title/summary）；load-bearing 收尾（轮首气泡、异常占位）归 `LoopStrategy`，不进 hook。策略（权限拦截/上下文补充）、增强（输入注入/输出检查）为文档化的未来扩展点，**现不承载**。
- **机制是 CC 式扁平注册表**：`event → list[callable]` 字典 + `trigger(event, ctx, *args) -> Iterator[SseEvent]`，loop 只调 `trigger`。**不引入** `Hook` ABC + `HookBundle` 命名字段 + `HookManager` 转发方法这类 1:1 退化的三层胶水。当前 `trigger` 观测-only（只 yield 事件，fail-open 吞异常记日志）；引入策略/拦截类 hook 时，`trigger` 加 verdict 返回 + loop 在对应事件加 `if blocked` 分支（演进路径，现不写死代码分支）。
- **异常分级**：**核心步骤 fail-closed**（append user / 构建 prompt / 落 assistant 消息--失败即上抛到外层 except，绝不静默继续，否则产生"消息没落库但循环继续"的静默数据不一致）；**工具失败按可预料性分级**--工具内可预料失败（参数缺失 / 校验错 / 落库失败等业务失败）由工具自身收口返 `Reply(correction)` 让模型重试（落库失败返 `Reply` 让模型重试（无事务兜底，崩了可能残留半图）），仅无法预料的意外异常由 `ToolDispatch.dispatch` fail-open 兜底转错误 `Reply`（不掺业务走向）；**扩展 hook fail-open**（经 `trigger`，失败只记日志，不阻断主流程）。分级由"是否经 trigger / 是否可预料"自然落地，无需显式配置。异常时 `SupervisorLoopStrategy.on_error` append 一条 `[Error]` 占位消息关闭本轮（写库失败静默，失败轮 assistant 本就未入库，库内干净，不截断历史），再返回 `ErrorEvent`。
- **顺序契约可测**：agent loop 重度依赖调用顺序与 `ctx.turn` 字段的读写时机，这类隐式契约**必须有用例锚定**（断言"给定输入 → 事件序列 + 入库消息序列"），改动主流程前先有安全网。
