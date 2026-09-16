# Repository Guidelines

本文件面向在本仓库工作的贡献者与编码 agent，整合原 `CLAUDE.md` 的项目说明、配置和协作约定。实现说明已按当前代码校正；新增功能时同步维护相关说明。

## 项目概览与目录

Chorus 是多智能体图文博文创作助手：用户提出主题 → supervisor 理解并确认意图 → 工具建立任务图 → 子 agent 完成选题、文案、配图、汇总 → HIL 人工确认 → PostCard 成品。后端 FastAPI + OpenAI SDK + SQLAlchemy/SQLite，前端 Vue 3 + Vite。

**数据库是三 loop 间的通信媒介与单一事实源**。supervisor 建图，scheduler 轮询派发，subagent 写产物与进度；前端通过 SSE 和任务图轮询呈现结果。

| 路径 | 职责 |
| --- | --- |
| `chorus/config.py` | 模型表、旁路模型、工具白名单、数据路径、外部服务及日志配置 |
| `chorus/app.py` / `startup.py` | `create_app()` 构造器注入与内联装配；lifespan 管理启动和退出，`run_startup(scheduler)` 启动调度器 |
| `chorus/domain/` | 按业务概念组织模型、纯函数及单概念基础设施；包括 task、intent、message、skill、prompt、compact、memory、suggestion 等 |
| `chorus/agents/` | supervisor、subagent、scheduler 三 loop；共享 loop、runtime、truncation、chat_model、progress_sink |
| `chorus/tools/` | 工具模型、框架、注册表、`builtin/` 内置工具及 `clients/` 外部客户端 |
| `chorus/repo/` | 各表唯一 SQL 入口、Record 定义、Engine、事务装饰器与领域模型映射 |
| `chorus/services/` | 会话、消息、压缩、任务/HIL、意图、选项、记忆、设置、trace 和 lease 的应用编排 |
| `chorus/hooks/` | 扁平事件注册表；trace 观测、标题生成与记忆提取 |
| `chorus/routes/` | HTTP/SSE 适配；`providers.py` 从 `app.state` 注入依赖 |
| `chorus/resources/skills/` | 随源码管理的技能包，每包以 `SKILL.md` 为入口 |
| `chorus/tests/` | 按层分组的后端测试，`_helpers.py` 提供临时数据库与 stub |
| `web/src/` | Vue 组件、composables、`api.js` 与 `styles/`；静态资源在 `web/public/` |
| `web/src/tests/` / `web/e2e/` | Vitest 单测与 Playwright 浏览器测试 |
| `scripts/` | 联合启动、真实模型 E2E 与数据库重建工具 |
| `data/` | 被 Git 忽略的运行时数据库与日志；本地 `docs/` 也被忽略，不能作为共享规范的唯一来源 |

## 安装、运行与构建

以下命令均从仓库根目录执行：

```bash
uv sync                                            # 安装 Python 及开发依赖
npm --prefix web ci                                # 按锁文件安装前端依赖
./scripts/start.sh                                 # 同时启动前后端，Ctrl+C 一并停止
.venv/bin/uvicorn chorus.app:app --reload --port 8000 # 单独启动后端
npm --prefix web run dev                           # 单独启动 Vite
npm --prefix web run build                         # 构建到 web/dist/
npm --prefix web run preview                       # 预览前端构建产物
```

后端默认 `http://localhost:8000`，前端默认 `http://localhost:5173`；Vite 将 `/api` 代理到后端。`web/vite.config.js` 支持用 `PORT` 指定前端端口。

## 配置与数据

密钥值只写被忽略的 `.env`，配置表只存环境变量名；不要提交密钥、数据库、日志或生成文件。

- `CHAT_MODELS`：`model_name` 是展示名和存储键；每条包含 `base_url`、`api_key_env`、`model_id`。当前对话密钥为 `DEEPSEEK_API_KEY`。可选 `input_price` / `output_price` 单位为元/百万 token，两者齐全时显示 trace 费用。
- `BYPASS_MODEL`：须对应 `CHAT_MODELS` 中的 `model_name`，供标题、摘要、旁白、记忆和建议等旁路调用使用。当前代码已不使用 `TITLE_MODEL`。
- `IMAGE_MODELS`：每条包含 `model_name`、`provider`、厂商私有 `options`（`base_url`、`api_key_env`、`model_id`）；默认生图密钥为 `ARK_API_KEY`。新增厂商需新增 client，并在 `tools/builtin/generate_image.py` 注册 builder，再配置 provider。
- `BAIDU_SEARCH_API_KEY`：搜索密钥；`BAIDU_SEARCH_BASE_URL` 在配置中固定为千帆端点。联网搜索开关经 SettingsService 控制。
- `TOOL_WHITELISTS`：按 supervisor、idea、script、image、finalize 角色控制可见工具。
- 日志环境变量：`LOG_LEVEL`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT`、`LOG_RETENTION_DAYS`、`LOG_CLEANUP_INTERVAL`；日志目录为 `data/logs/`。
- 调度间隔与僵死超时 `_SCHEDULER_INTERVAL` / `_ZOMBIE_TIMEOUT` 位于 `agents/scheduler.py`；模型超时与输出预算留在使用模块，不集中到配置文件。
- `DATA_DIR` 为仓库根下 `data/`。单一 `data/chorus.db` 存会话、原始消息、模型现场、trace、任务/内容/产物/进度、意图/确认、选项、记忆和设置；表定义以 `repo/models.py` 为准。

`uv run python scripts/reset_db.py` 会清空并重建产品库，仅在明确需要重置时执行，不作为日常测试步骤。

## 架构与运行契约

### 分层与装配

依赖方向为 `routes → agents/services → repo → db`；agents 可以依赖 domain、services、tools 和 hooks。domain 不依赖 repo、services、hooks、tools 或 agents，但可持有服务于自身概念的文件系统、模型客户端等外部依赖。使用构造器注入；`create_app()` 内联装配，中间对象为局部变量，HTTP 所需 service 挂 `app.state`，运行期启动/退出副作用经 lifespan 管理，不新增模块级后端服务单例。

### 三 loop 与工具调用

- **Supervisor**：`stream(session_id, user_message)` 接收用户消息；`resume(session_id, tool_name, result_text)` 改写挂起工具结果后续跑。入口检查已定稿和活跃任务，策略负责提示词、SSE、成对落库与收尾。普通文本落库后先发 `done`，再执行 Stop hook，避免旁路调用拖住前端解禁。
- **Subagent**：scheduler claim 后用后台守护线程执行 `run(task_id)`。每轮检查任务状态和 heartbeat；lease 校验必须先于终态与产物写入，防止取消、回收或重抢后产生孤儿产物。历史留在内存，进度写 `task_progress`，过程写 traces，不把子 agent ReAct 历史放进 supervisor messages。
- **Scheduler**：启动幂等，先回收僵死任务，再轮询可调度任务；claim 写 running 与 owner_id，每任务直接起 `threading.Thread`，当前没有线程池并发上限。心跳超时翻为 failed，退出时 `scheduler.stop()`。调度事件直接写 trace，不挂 LLM hook。
- **共享内核**：supervisor/subagent 共用 `AgentLoop` 和 `LoopStrategy`。`AgentContext` 存回合输入，`TurnState` 每轮 reset，`LoopOutcome` 存退出结果；`TruncationGuard` 位于 `agents/truncation.py`，输出截断时放宽预算到 64000 并重试一次，仍失败交策略收尾，截断空正文不入历史。
- **工具协议**：`Tool.run(arguments, ctx) → ToolRunResult`，outcome 为 `Reply`（继续模型回合）或 `Suspend`（关流等待外部信号）；`ToolDispatch` 统一注册、选 schema、执行、计时和意外异常处理。工具通过 `resolve_external` 实现外部解挂语义。主循环根据 outcome 分流，不按工具名编排业务。
- 七个内置工具为 `load_skill`、`list_skill`、`generate_image`、`baidu_search`、`create_plan`、`present_options`、`update_intent_state`。均在 `tools/registry.py` 装配；supervisor 白名单为后三项。生图工具经 `ImageModelProvider` 选模型，测试模式由设置控制。
- `create_plan` 内部完成校验、展开任务和落库；业务失败返回纠错 `Reply`。意图通过工具和状态机驱动：empty → capturing → needs_clarification / ready_to_confirm → confirmed → dispatched；`next_action` 由状态派生，不由模型填写；确认前不得建图。

### 存储、消息与扩展

- Engine 启用 SQLite WAL、NORMAL 同步、外键与 busy_timeout，按 Record 幂等建表。repo 返回领域模型，使用短 Session 与 `@read` / `@write`；事务边界为方法边界，不新增跨表事务、缓存、锁或业务校验，业务状态集合由 domain 经 service 传入。
- 原始消息写 `messages` 供前端读取，正常新消息以相同标识双写 `provider_messages`。模型现场由 CompactService 维护：旧工具结果微压缩保配对，超阈值整段改为摘要；输入超长可应急压缩后重试一次。
- `MessageService.build_provider_messages()` 是 supervisor 模型消息序列的唯一构建点，策略负责收集上下文并注入意图/记忆。不要把副本历史或压缩逻辑散落到其他层。
- `tasks` 状态集合为 pending/running/awaiting_confirm/finished/failed/cancelled；产物和进度分表存储，ReAct 原始过程由 traces 覆盖，没有独立 steps 表。删除会话通过 SessionService 与外键 CASCADE 清理关联数据。
- 路由采用同步 `def`，由 FastAPI 线程池执行。当前没有后端会话级 chat 锁，同会话单流依赖前端 disable；SQLite busy_timeout 不能保证并发消息顺序或上下文一致。
- HookRegistry 使用按 event/source 分组的回调列表，事件为 BeforeModelRequest、AfterModelResponse、PreToolUse、PostToolUse、Stop。trace 用于观测，标题和记忆在 supervisor Stop 扩展；核心落库、轮首消息和异常占位不进 hook。
- `SkillLoader` 按需扫描 `chorus/resources/skills/*/SKILL.md`，每次现扫现解析、不缓存；frontmatter 支持 name/description/tags。摘要进入 prompt，完整内容通过工具加载；子文件读取必须保留路径越界及后缀校验。

### 前端与数据流

- `App.vue` 编排会话、SSE 和轮询；`SessionSidebar` / `NavDock` 提供导航，`main-panel/` 展示对话、意图、选项、HIL、校样与成品，`team-panel/` 展示角色、任务时间线与产物。设置、记忆和控制台有各自面板。
- 会话状态分别保存在 `messagesBySession`、`streamingBySession` 等映射，`activeId` 仅控制当前投影。流式回调捕获发送时的会话标识和列表，不能随切换会话写到另一会话。
- 一条用户交互链路对应一个 assistant 气泡，包括工具轮次及 HIL 挂起/续跑。`message_start` 标记模型轮次，不必新建气泡；续跑复用挂起气泡，历史通过 `messageHistory.js` 归并。
- `api.js` 用 POST + `fetch` / `ReadableStream` 解析 SSE，不用 EventSource。事件契约以 `domain/events.py` 为准：message_start、reasoning、reasoning_done、token、tool_call、tool_result、trace、title_update、done、suspend、error、busy、archived、intent_state、option_prompt。
- subagent/scheduler 不连接 SSE。`useTaskPolling` 拉任务图，非流式时刷新消息；图无活跃任务即停止，包括启动时已空闲的情况。仅忙转闲且定稿完成时触发完成回调。
- `taskCardProjection.js` 将任务/意图/选项投影为虚拟卡；`anchoredCards.js` 把卡片插在触发消息后。`artifactsProjection.js` 供右栏展示，`renderPostCard.js` 是成品 markdown 渲染入口，`roleMeta.js` 集中状态展示映射，`useTraceStore.js` 聚合各会话 trace。
- 前端确认、编辑、重试、取消经路由和 TaskService 更新状态/产物，再由 scheduler 或轮询推进界面；不得让前端自行维护另一套业务状态机。

## 测试与验证

```bash
uv run python -m pytest chorus/tests/               # pytest 收集后端测试
uv run python -m chorus.tests                       # 各测试模块 main() 逐一执行
uv run python -m chorus.tests.test_domain_task      # 单模块示例
npm --prefix web test                              # Vitest 单次运行
npm --prefix web run test:watch                     # Vitest 监听模式
npm --prefix web exec -- playwright install chromium # 首次安装浏览器
npm --prefix web run e2e                           # 已启动服务上的真实模型浏览器测试
uv run python scripts/e2e_intent_test.py             # 临时库上的真实模型意图链路
```

- 不追求全覆盖，没有数字覆盖率门槛。重点测试纯领域函数、状态机、repo smoke、关键编排和消息/事件顺序；为行为变更新增可复现的回归断言，不用测试复刻实现。
- 后端文件按 `test_domain_*`、`test_repo_*`、`test_service_*`、`test_agent_*`、`test_tools_*`、`test_route_*`、`test_integration_*`、`test_hooks*`、`test_app_*` 命名；保留 `main()` 以兼容裸跑。`_helpers.py` 的 `fresh_engine()` / `seed_session()` 提供临时库和种子，模型依赖用 FakeClient 或 stub。
- Vitest 使用 node 环境，收集 `web/src/tests/**/*.test.js`；重点覆盖纯函数、投影与 composable 状态，不为纯展示组件堆渲染测试。界面验证使用交互与文本断言，样式变更同时执行前端构建。
- Playwright 收集 `web/e2e/*.spec.js`，使用 Chromium，默认连接 5173；需先运行 `./scripts/start.sh` 并配齐模型密钥，不自动启动或重启现有服务。
- `scripts/e2e_*.py` 覆盖真实模型、服务或 HTTP/SSE 链路，使用临时库隔离。浏览器 E2E 会写产品库；清理规则见下方开发约定。

## 回答风格与界面验证

- 用户提问时，优先用直白简洁的语言给出结论，不主动铺陈代码细节与文件引用；明确要求结合代码或详细解释时，再附代码、行号和逐段说明。
- 保留原项目的文本验证约定：不调用截图功能，不以截图作为判读依据；使用可用浏览器工具的无障碍树、点击/输入、控制台和网络信息，结合源码验证前端。原文“本会话模型无图像识别能力”是旧会话描述，不作为当前模型能力事实。

## 基础格式与 Pull Request

Python 使用四空格缩进、类型标注、snake_case 函数/模块与 PascalCase 类；JavaScript/Vue 使用两空格、单引号和无分号风格。Vue 组件用 `PascalCase.vue`，composable 用 `useSomething.js`。目前没有配置统一 formatter/linter，遵循相邻代码及下方细则。

PR 说明应包含具体问题、变更后的行为、验证方式及相关 issue；UI 改动描述交互验证结果。验证结果写入 PR 或交付说明，提交信息遵守下方格式，不附测试结果尾巴。

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

- **减少不必要的防御分支**：写 `if`/`raise` 前先判断该分支是否真有路径到达，针对走不到的路径写防御是死代码。判据是追踪参数来源：上游已保证非空（如 loop 构造工具上下文时已传入有效会话标识、路由已 404 校验）、调用方硬编码字面量（如路由传的 signal 不可能是非法值）、生产装配总注入的依赖，这些路径上不要写 `if`/`raise`。但真实业务分支保留：工具内可预料失败返 `Reply` 让模型重试、校验失败返 correction、lease 校验等。
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

- **领域层（`domain/`）按业务概念扁平组织**，每个模块同放该概念的 Pydantic 模型（带只读行为，如 `Message.to_provider_dict()`、`SkillContent.from_markdown()`）、跨对象的纯领域函数（如 `build_provider_messages`、`clean_generated_title`），以及**围绕该单一概念的基础设施型 service / loader**（如 `SkillLoader` 扫盘读取 skill、`TitleGenerationService` 调 OpenAI 生成标题）。`domain` **不得 import** `chorus.repo` / `chorus.services` / `chorus.hooks`，但允许直接持有围绕自身概念的外部依赖（文件系统 / `openai` / `threading`）——只要它服务于本概念、而非跨概念编排。
- **编排层负责"取数据 → 调领域 → 存数据"与 agent loop 流程控制**：`agents/`（三 loop 编排：supervisor/subagent/scheduler）、`services/`（应用 / HIL 编排，如 `SessionService` 跨 repo、`TaskService` HIL + get_graph）、`routes/`（HTTP 适配）、`hooks/`（agent loop 横切扩展点）、`startup.py`（启动副作用）都不承载领域规则，只做协调——从 repo/外部取数据，喂给领域函数/模型/service，再把结果存回或返回。`create_app()` 只装配（new + 注入），不含启动副作用。
- **判别准则（看被操作的状态而非 import 的类型）**：一段逻辑若围绕**单一领域概念**操作其状态（如 skill、title，哪怕要扫文件 / 调 OpenAI / 持锁），归 `domain/`，与该概念的模型和纯函数同模块；若**同时操作两个以上领域概念的状态**（驱动 agent loop 多轮循环、跨多 repo 协调、协调多 service），归编排层。一句话："它服务于一个概念，还是粘合多个概念？"——前者领域，后者编排。
- **防 domain 杂项化滑坡**：domain 里的 infra service（loader / 调外部 API 的概念内 service）必须单一概念内聚；一旦长出跨概念协调，迁往 `services/`（编排层本就是跨概念协调的归宿），不新建目录。
- **扩展时保持边界**：当编排层需要新的运行时多方信息（如 system prompt 要拼接对话摘要、用户画像），**收集信息是编排**（在 hook/service 里凑齐），**拼装规则是领域**（领域函数接收已收集好的数据）。用值对象（如 `PromptContext`）承载多方信息，避免领域函数参数爆炸、签名频繁变动。

### Agent Loop 编排边界

- **最小回合自动机抽 kernel，业务语义进 strategy**：supervisor / subagent 共享 `AgentLoop.run`（`agents/loop.py`）驱动的最小回合自动机——准入 → reset → message_start 门 → 拼消息选 schema → BeforeModelRequest → 调模型 → 消费流 → AfterModelResponse → 工具/文本分流 → 终止判定；divergent 节点（历史来源、持久化、stream 消费方式、终态写入、progress）全进各自 `LoopStrategy`（`SupervisorLoopStrategy` / `SubagentLoopStrategy`）。**kernel 零 agent 分支**——不许出现 `if ctx.source == ...` / `isinstance(strategy, ...)`，出现即抽象失败，降级为只保留 工具派发逻辑 + 模型调用 helper 两层。各 service 主流程（`SupervisorService.stream` / `SubAgentService.run`）退化为「入口准入 + 构造 strategy + 跑 kernel」，单文件可读；核心业务提交（落库、构建 prompt、执行工具、SSE 核心事件 yield）在 kernel/strategy，不进 hook。
- **hook 是挂在稳定 loop 上的扩展点，不是主业务承载点**（遵循「挂在循环上，不写进循环里」）：loop 自己做主流程真身，hook 只做"前后织入 + 策略判断"。hook 收缩为扩展能力--观测（trace/日志/埋点）、收尾（title/summary）；load-bearing 收尾（轮首气泡、异常占位）归 `LoopStrategy`，不进 hook。策略（权限拦截/上下文补充）、增强（输入注入/输出检查）为文档化的未来扩展点，**现不承载**。
- **机制是 CC 式扁平注册表**：`event → list[callable]` 字典 + `trigger(event, ctx, *args) -> Iterator[SseEvent]`，loop 只调 `trigger`。**不引入** `Hook` ABC + `HookBundle` 命名字段 + `HookManager` 转发方法这类 1:1 退化的三层胶水。当前 `trigger` 观测-only（只 yield 事件，fail-open 吞异常记日志）；引入策略/拦截类 hook 时，`trigger` 加 verdict 返回 + loop 在对应事件加 `if blocked` 分支（演进路径，现不写死代码分支）。
- **异常分级**：**核心步骤 fail-closed**（append user / 构建 prompt / 落 assistant 消息--失败即上抛到外层 except，绝不静默继续，否则产生"消息没落库但循环继续"的静默数据不一致）；**工具失败按可预料性分级**--工具内可预料失败（参数缺失 / 校验错 / 落库失败等业务失败）由工具自身收口返 `Reply(correction)` 让模型重试（落库失败返 `Reply` 让模型重试（无事务兜底，崩了可能残留半图）），仅无法预料的意外异常由 `ToolDispatch.dispatch` fail-open 兜底转错误 `Reply`（不掺业务走向）；**扩展 hook fail-open**（经 `trigger`，失败只记日志，不阻断主流程）。分级由"是否经 trigger / 是否可预料"自然落地，无需显式配置。异常时 `SupervisorLoopStrategy.on_error` append 一条 `[Error]` 占位消息关闭本轮（写库失败静默，失败轮 assistant 本就未入库，库内干净，不截断历史），再返回 `ErrorEvent`。
- **顺序契约可测**：agent loop 重度依赖调用顺序与 `ctx.turn` 字段的读写时机，这类隐式契约**必须有用例锚定**（断言"给定输入 → 事件序列 + 入库消息序列"），改动主流程前先有安全网。
