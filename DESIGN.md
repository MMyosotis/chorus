# Little Kitty 项目设计文档

## 一、项目概述

Little Kitty 是一个带上下文记忆的 AI 对话助手 Web 应用。前端提供简洁清新的蓝色风格聊天界面，后端通过 OpenAI 兼容 API 实现流式对话。

**核心特性：**
- 单会话对话，内存存储历史
- SSE 流式输出，打字机效果
- 前后端分离架构
- 完全本地运行

**技术栈：**
- 后端：Python 3.9+、FastAPI、OpenAI SDK
- 前端：Vue 3、Vite
- 通信：HTTP + SSE（Server-Sent Events）

---

## 二、项目结构

```
little-kitty/
├── 启动前端.command              # 双击启动前端开发服务器
├── 启动后端.command              # 双击启动后端服务
├── pyproject.toml                # Python 项目配置和依赖
├── .env                          # 环境变量（API_KEY 等）
│
├── backend/
│   ├── __init__.py
│   ├── app.py                    # FastAPI 应用工厂 + CORS 配置
│   ├── config.py                 # 配置项（从 .env 读取）
│   ├── chat.py                   # 对话核心逻辑
│   └── routes/
│       ├── __init__.py
│       └── chat.py               # /api/chat 路由
│
└── frontend/
    ├── package.json              # 前端依赖配置
    ├── vite.config.js            # Vite 配置 + 开发代理
    ├── index.html                # 入口 HTML
    └── src/
        ├── main.js               # Vue 应用入口
        ├── App.vue               # 根组件，状态中心
        ├── components/
        │   ├── ChatWindow.vue    # 消息列表滚动区
        │   ├── MessageBubble.vue # 单条消息气泡
        │   └── InputBar.vue      # 底部输入栏
        └── styles/
            └── global.css        # 全局样式
```

---

## 三、API 接口设计

后端提供三个 RESTful 接口，均位于 `/api/chat` 前缀下。

### 3.1 发送消息（SSE 流式）

```
POST /api/chat
Content-Type: application/json

请求体：
{
  "message": "你好"
}

响应：text/event-stream
data: {"type":"token","content":"你"}

data: {"type":"token","content":"好"}

data: {"type":"done"}

错误情况：
data: {"type":"error","content":"错误信息"}
```

事件类型：
- `token`：单个文本片段，前端追加到当前消息
- `done`：本次回复结束
- `error`：发生错误

### 3.2 获取对话历史

```
GET /api/chat/history

响应：
{
  "messages": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！有什么可以帮你的吗？"}
  ]
}
```

仅返回 user/assistant 消息（不含 system）。用于页面刷新后恢复对话显示。

### 3.3 重置对话

```
POST /api/chat/reset

响应：
{
  "status": "ok"
}
```

清空内存中的对话历史。

---

## 四、后端设计

### 4.1 模块职责

| 模块 | 职责 |
|------|------|
| `backend/config.py` | 集中读取环境变量和常量定义 |
| `backend/chat.py` | 对话核心：OpenAI 客户端、历史管理、流式生成器 |
| `backend/routes/chat.py` | HTTP 路由层，封装 SSE 响应 |
| `backend/app.py` | FastAPI 应用工厂，注册中间件和路由 |

### 4.2 配置项（backend/config.py）

| 名称 | 来源 | 默认值 |
|------|------|--------|
| `API_KEY` | `OPENAI_API_KEY` 环境变量 | `""` |
| `BASE_URL` | `OPENAI_BASE_URL` 环境变量 | `https://api.openai.com/v1` |
| `MODEL_ID` | `MODEL_ID` 环境变量 | `gpt-4o` |
| `SYSTEM_PROMPT` | 硬编码 | "你是一个友好、健谈的 AI 助手..." |
| `MAX_TOKENS` | 硬编码 | `2048` |

### 4.3 对话核心（backend/chat.py）

模块级全局 `_history` 维护单会话上下文，初始包含 system prompt。

提供三个函数：
- `get_history()` — 返回排除 system 的消息列表
- `reset_history()` — 重置为初始状态
- `chat_stream(message)` — 同步生成器：先追加 user 消息，调用 OpenAI 流式接口，逐 chunk yield token，流结束后将完整回复拼合写入历史。异常时回滚已追加的 user 消息

**关键设计决策：**
- OpenAI SDK 的流式接口是同步迭代器，使用同步生成器而非 async generator
- 流结束后才写入完整回复，保证历史中每条 assistant 消息都是完整的

### 4.4 路由层（backend/routes/chat.py）

- 路由函数声明为 `def`（非 `async def`）
- FastAPI 会自动将同步函数放入线程池执行，避免阻塞事件循环
- `StreamingResponse` 包装事件生成器，逐条发送 SSE 事件
- 响应头设置 `Cache-Control: no-cache` 和 `X-Accel-Buffering: no`，防止缓冲

### 4.5 应用工厂（backend/app.py）

- 配置 CORS 中间件，允许 `http://localhost:5173` 跨域访问
- 注册 `chat` 路由
- 模块级暴露 `app` 实例供 uvicorn 加载

---

## 五、前端设计

### 5.1 组件结构

```
App.vue（状态中心）
├── ChatWindow.vue（消息列表 + 自动滚动）
│   └── MessageBubble.vue（单条消息气泡）
└── InputBar.vue（输入框 + 发送按钮）
```

### 5.2 组件职责

**App.vue（根组件）**

持有全部应用状态：
- `messages: ref([])` — 对话消息数组
- `streaming: ref(false)` — 是否正在流式输出

三个核心方法：
- `fetchHistory()` — 页面加载时从后端恢复历史
- `sendMessage(text)` — 发送消息并解析 SSE 流
- `newChat()` — 重置对话（有内容时弹出 confirm 确认）

**ChatWindow.vue**

- 接收 `messages` 和 `streaming` props
- watch 消息内容变化，自动滚动到底部
- 循环渲染 `MessageBubble`
- 空状态显示提示文案

**MessageBubble.vue**

- 接收 `role`、`content`、`showCursor` props
- 根据 `role` 决定左右对齐和颜色
- 转义 HTML 后保留换行（`\n` → `<br>`）
- 流式输出最后一条消息时显示闪烁光标

**InputBar.vue**

- 接收 `streaming` prop，emit `send` 事件
- Enter 发送、Shift+Enter 换行
- textarea 自适应高度（1-5 行）
- 流式输出期间禁用发送按钮

### 5.3 SSE 流式解析

使用 `fetch` + `ReadableStream`（不用 `EventSource`，因为需要 POST）：

1. 发送 POST 请求，拿到 `response.body.getReader()`
2. 循环 `reader.read()`，用 `TextDecoder` 解码为字符串
3. 累积到 buffer，按 `\n\n` 切割 SSE 事件
4. 每个事件去掉 `data: ` 前缀后 JSON.parse
5. 根据 `type` 字段处理：
   - `token` → 追加到 `messages[assistantIdx].content`
   - `error` → 显示错误提示
6. Vue 响应式系统自动驱动 DOM 更新，产生打字机效果

### 5.4 开发代理

`vite.config.js` 配置 `/api` → `http://localhost:8000`，前端开发时所有 `/api` 请求自动代理到后端，避免跨域问题。

---

## 六、样式设计

### 6.1 配色方案（蓝色基调）

| 用途 | 颜色 | 备注 |
|------|------|------|
| 顶栏背景 | `#1e40af` | blue-800 深蓝 |
| 用户气泡 | `#3b82f6` 白字 | blue-500 |
| 助手气泡 | `#f1f5f9` 深灰字 | slate-100 |
| 页面背景 | `#f8fafc` | slate-50 |
| 发送按钮 | `#2563eb` / hover `#1d4ed8` | blue-600 / blue-700 |
| 输入框边框 | `#cbd5e1` / focus `#3b82f6` | slate-300 / blue-500 |

### 6.2 页面布局

```
┌──────────────────────────────────────┐
│  🐾 Little Kitty           [新对话]  │  顶栏 56px，深蓝
├──────────────────────────────────────┤
│       ┌──────────────┐               │
│       │ 用户消息     │               │  右对齐，蓝色气泡
│       └──────────────┘               │
│  ┌──────────────┐                    │
│  │ 助手回复▌   │                    │  左对齐，浅灰气泡 + 光标
│  └──────────────┘                    │
│                                      │  消息区 flex-grow，可滚动
│                                      │  最大宽度 768px 居中
├──────────────────────────────────────┤
│  ┌────────────────────────┐ ┌──┐    │
│  │ 输入消息...             │ │▶ │    │  固定底部
│  └────────────────────────┘ └──┘    │
└──────────────────────────────────────┘
```

### 6.3 交互细节

- 打字机光标：流式输出时末尾显示闪烁 `|`，`@keyframes blink` 实现
- 自动滚动：每次内容更新通过 `nextTick` + `scrollTop` 滚到底部
- 发送按钮：流式中禁用并变浅蓝
- 空消息：自动拦截不发送
- 新对话：有内容时 `confirm` 二次确认
- 页面刷新：`onMounted` 拉取历史恢复显示
- 滚动条样式：自定义浅灰细滚动条

---

## 七、运行方式

### 7.1 首次运行

需要先在 `.env` 中配置 API：
```
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1   # 可选
MODEL_ID=gpt-4o                              # 可选
```

### 7.2 启动方式

**方式 A：双击启动脚本（推荐）**
- 双击 `启动后端.command` — 自动检查 `.venv`，缺失则 `uv sync`，然后启动 uvicorn
- 双击 `启动前端.command` — 自动检查 `node_modules`，缺失则 `npm install`，然后启动 vite

**方式 B：手动命令行**
```bash
# 终端 1
uv sync
.venv/bin/uvicorn backend.app:app --reload --port 8000

# 终端 2
cd frontend && npm install && npm run dev
```

### 7.3 访问

浏览器打开 http://localhost:5173

---

## 八、关键设计权衡

| 场景 | 选择 | 理由 |
|------|------|------|
| 后端框架 | FastAPI | 原生支持 SSE 流式响应，类型安全 |
| 前端框架 | Vue 3 | 学习成本低，模板语法直观 |
| 状态管理 | 不使用 Pinia | 单组件状态即可，避免过度设计 |
| UI 组件库 | 不使用 | 保持轻量，自定义样式更灵活 |
| SSE 实现 | fetch + ReadableStream | 支持 POST，比 EventSource 更灵活 |
| 路由函数 | 同步 `def` | OpenAI SDK 流式接口是同步的，FastAPI 自动线程池处理 |
| 会话存储 | 内存全局变量 | 单会话场景下最简单，重启即清空 |
| 历史写入时机 | 流结束后一次性写入 | 保证历史中消息完整，避免被截断 |

---

## 九、可能的扩展方向

如果未来需要演进，以下方向可考虑：

- **多会话支持**：将 `_history` 改为 `dict[session_id, list]`，前端增加会话列表侧栏
- **持久化存储**：引入 SQLite 保存对话历史
- **Markdown 渲染**：助手回复支持代码块、表格等富文本
- **生产部署**：FastAPI 直接托管前端打包后的静态文件，单端口部署
- **用户系统**：增加登录认证，按用户隔离会话
