# 系统架构

Chorus 是前后端分离的多 Agent 创作应用：后端 FastAPI + OpenAI SDK，前端 Vue 3 + Vite。核心是**三条相互独立的执行循环（loop）**，通过 SQLite 数据库共享任务状态与产物——**数据库是三条 loop 的通信媒介与单一事实源**；其中 scheduler 会直接启动线程执行 subagent。

```
浏览器前端 (Vue 3)
  │ SSE 流式对话                │ 轮询会话视图（HTTP 接口）
  ▼                            ▼
supervisor                FastAPI 会话视图接口
（主对话 agent）              （读库聚合）
  │ 建图写任务                     │
  ▼                               ▼
┌─────────────  SQLite（单一事实源）  ─────────────┐
│  tasks / messages / task_artifacts / task_progress … │
└──────────────────────────────────────────────────┘
  ▲ 占槽并派发               ▲ 进度/产物写回
  scheduler ──────── 派发 ────────► subagent

supervisor / subagent ──► 对话模型（OpenAI 兼容）
subagent ──► 内置工具（生图 / 搜索 / 技能加载）
```

## 三条 loop

| Loop | 形态 | 职责 |
| --- | --- | --- |
| **supervisor** | SSE 流式，随请求执行 | 主对话 agent：流式回复普通对话；创作请求经意图确认后调 `create_plan` 建任务图（写 `tasks` 表） |
| **scheduler** | 守护线程，无 LLM | 周期轮询 `tasks` 表，把 `pending` 任务占槽翻为 `running` 并派发；超时未心跳的 `running` 任务回收为 `failed` |
| **subagent** | 后台线程，ReAct 循环 | 执行单个任务（选题 / 文案 / 配图 / 排版），多轮调模型与工具，把进度与产物写回数据库；正常产出翻转为 `awaiting_confirm` 等待人工确认（失败置 `failed`），`finished` 由用户确认经 TaskService 写入 |

三条 loop 各自单文件可读（`chorus/agents/` 下 `supervisor.py` / `scheduler.py` / `subagent.py`），supervisor 与 subagent 共享同一套 agent loop 内核（`agents/loop.py`），业务差异进各自的策略对象。

## 任务状态机与人工确认

`tasks` 表的状态翻转是协调核心：

```
pending ──► running ──► awaiting_confirm ──(用户确认)──► finished
              │  │            │
              │  │           (用户重跑)
              │  │            ▼
              │  └─► failed  pending（写回反馈后重新派发）
              └─(用户放弃)──► cancelled
```

- 子 agent 完成候选产出后置 `awaiting_confirm`，前端渲染 HIL 卡片，用户**确认 / 重跑 / 放弃**：确认将当前任务翻转为 `finished`，此前一直处于 `pending` 的下游任务由此进入可派发状态，scheduler 下一轮执行；重跑把当前任务翻回 `pending` 并写回反馈，交给同一 agent 重做。
- 排版任务的 `finished` 产物即 PostCard 成品，前端渲染为可继续对话修改的成品卡片。
- 写入终态前经过**租约校验**（状态归属检查），防止陈旧线程在被回收重抢后写入孤儿产物。
- 子 agent 每轮循环复查任务状态，实现**协作式取消**：状态被外部翻转（如用户取消流水线）即立即退出，不残留产物。

## 数据库：通信媒介

单库 `data/chorus.db`（SQLite，WAL 模式），主要表：

| 表 | 写入方 | 内容 |
| --- | --- | --- |
| `sessions` / `messages` | supervisor | 会话与消息**原始事实**，前端读取渲染 |
| `provider_messages` | supervisor | 发给模型的现场消息（压缩后结果），与 messages 同标识双写 |
| `traces` | 三方 | 模型请求 / 响应 / 工具调用轨迹，靠 `message_id` 与 `task_id` 关联多来源 |
| `tasks` | supervisor 建、scheduler 占、subagent 翻转 | 任务图与状态 |
| `task_artifacts` | subagent | 各阶段产物与选中项 |
| `task_progress` | subagent | 运行期进度快照（一任务一行，覆盖写） |

上下文压缩两级：估算超阈值才微压缩（滑出最近窗口的旧工具结果正文换占位，行留原位保配对），压完仍超阈值才整段覆写为摘要行。

## 前端呈现：SSE + 轮询

supervisor 连 SSE，逐 token 推送对话与工具事件；subagent 与 scheduler 不连 SSE，其产物由前端**定时轮询会话视图**（`GET /api/sessions/{id}/view`）驱动渲染——后端视图把 `awaiting_confirm` / finished / running 的任务折叠成卡片气泡（HIL 卡 / 成品卡 / 进度面板），前端照渲染。任务全部终态后轮询自停。

## 分层依赖

后端按 Java OOP 风格分层，依赖单向：

```
routes → agents / services → repo → db
             │
             ▼
        domain（领域层）  tools（工具子系统）
```

- `domain/`：按业务概念扁平组织的领域层——模型、纯领域函数、围绕单一概念的基础设施型 service（如技能扫描、标题生成）。不依赖 repo / services / hooks。
- `agents/`：三条 loop 的编排层（取数据 → 调 domain / LLM / 工具 → 存数据 + 循环流程控制）。
- `services/`：应用与 HIL 编排（跨 repo 协调、确认门禁、任务租约等）。
- `repo/`：各表的唯一 SQL 入口，返回 Pydantic 领域模型；事务边界 = 方法边界。
- `tools/`：工具框架 + 内置工具（建图 / 生图 / 搜索 / 技能）+ 外部 client，按白名单暴露给各 agent。
- `hooks/`：扁平注册表式扩展点（观测 / 收尾），fail-open，不承载主业务。

## 意图状态链路

主 agent 在调用 `update_intent_state` 工具时把对用户意图的理解写入 `intent_states` 表（独立于消息历史）：意图字段 + 状态机 `empty → capturing → needs_clarification | ready_to_confirm → confirmed → dispatched`，`next_action` 由状态单一映射派生。意图确认（HIL 门禁）通过后才允许建任务图。

## 想深入了解

- 各表的读写契约与压缩细节：`chorus/repo/`、`chorus/services/compact.py`
- 提示词装配：`chorus/domain/prompt/`（每个 agent 一个模块，打开即见全部拼装位置）
- 更多工程约定见根目录 `CLAUDE.md`（面向编码 agent 的开发文档）
