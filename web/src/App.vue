<script setup>
import { ref, reactive, computed, watch, onMounted } from 'vue'
import ChatWindow from './main-panel/ChatWindow.vue'
import InputBar from './main-panel/InputBar.vue'
import SessionSidebar from './SessionSidebar.vue'
import ConsolePanel from './main-panel/ConsolePanel.vue'
import {
  listSessions,
  createSession,
  deleteSession,
  renameSession,
  fetchMessages,
  streamChat,
  getIntentState,
  confirmIntent,
  reopenIntent,
  cancelPipeline,
} from './api.js'
import { useTraceStore } from './composables/useTraceStore.js'
import { useTaskPolling } from './composables/useTaskPolling.js'
import PipelineProgressBar from './main-panel/PipelineProgressBar.vue'
import PipelineRuntimeDock from './main-panel/PipelineRuntimeDock.vue'
import TeamPanel from './team-panel/TeamPanel.vue'

const traceStore = useTraceStore()
const taskPolling = useTaskPolling()
const consoleOpen = ref(false)

const sessions = ref([])
const messagesBySession = reactive({})
const streamingBySession = reactive({})
const intentStateBySession = reactive({})
const activeId = ref(null)
const inputBarRef = ref(null)

const focusedTaskId = ref(null)

function onTaskFocus(taskId) {
  focusedTaskId.value = taskId
}

const messages = computed(() => messagesBySession[activeId.value] || [])
const streaming = computed(() => !!streamingBySession[activeId.value])
const activeGraph = computed(() => taskPolling.getGraph(activeId.value))
const hasActiveTask = computed(() => !!activeGraph.value?.active)
const activeIntentState = computed(() => intentStateBySession[activeId.value] || null)
const activeTitle = computed(() => {
  const c = sessions.value.find((x) => x.id === activeId.value)
  return c ? c.title : ''
})

function makeEmptyAssistant() {
  return {
    role: 'assistant',
    content: '',
    thinking: { state: 'idle' },
    tools: { state: 'idle', items: [] },
  }
}

function normalizeAssistant(msg) {
  const toolItems = Array.isArray(msg.tools) ? msg.tools : []
  return {
    role: 'assistant',
    content: msg.content || '',
    thinking: { state: 'idle' },
    tools: {
      state: 'idle',
      items: toolItems.map((it) => ({
        name: it.name,
        arguments: it.arguments || {},
        duration_ms: it.duration_ms ?? null,
        content: it.content || '',
        display: it.display || it.name,
      })),
    },
  }
}

function mergeAssistantHistory(raw) {
  const result = []
  let pendingTools = []

  // 把累积的无正文工具调用合并到最近一条助手消息，无目标才落独立气泡兜底
  const flushPending = () => {
    if (!pendingTools.length) return
    for (let i = result.length - 1; i >= 0; i--) {
      if (result[i].role === 'assistant') {
        const target = result[i]
        for (const t of pendingTools) {
          target.tools.items.push({
            name: t.name,
            arguments: t.arguments || {},
            duration_ms: t.duration_ms ?? null,
            content: t.content || '',
            display: t.display || t.name,
          })
        }
        pendingTools = []
        return
      }
    }
    result.push(
      normalizeAssistant({
        role: 'assistant',
        content: '',
        tools: pendingTools,
      })
    )
    pendingTools = []
  }

  for (const m of raw) {
    if (m.role !== 'assistant') {
      flushPending()
      result.push({ role: m.role, content: m.content })
      continue
    }
    const ts = Array.isArray(m.tools) ? m.tools : []
    const hasContent = !!(m.content && m.content.trim())
    if (!hasContent) {
      pendingTools.push(...ts)
      continue
    }
    result.push(
      normalizeAssistant({
        role: 'assistant',
        content: m.content,
        tools: [...pendingTools, ...ts],
      })
    )
    pendingTools = []
  }
  flushPending()
  return result
}

async function loadMessages(id) {
  if (messagesBySession[id]) {
    traceStore.loadFromServer(id)
    return
  }
  try {
    const raw = await fetchMessages(id)
    messagesBySession[id] = mergeAssistantHistory(raw)
    traceStore.loadFromServer(id)
  } catch (e) {
    if (e.status === 404) {
      // 该会话已被后端清理
      sessions.value = sessions.value.filter((c) => c.id !== id)
      delete messagesBySession[id]
      delete streamingBySession[id]
      if (activeId.value === id) {
        if (sessions.value.length > 0) {
          activeId.value = sessions.value[0].id
          await loadMessages(activeId.value)
        } else {
          await onCreate()
        }
        alert('该会话已过期，已自动切换')
      }
    } else {
      messagesBySession[id] = []
    }
  }
}

async function loadIntentState(id) {
  try {
    intentStateBySession[id] = await getIntentState(id)
  } catch {
    intentStateBySession[id] = null
  }
}

async function selectSession(id) {
  activeId.value = id
  await Promise.all([loadMessages(id), loadIntentState(id)])
  injectTaskCards(id)
  injectIntentCard(id)
  // 进入会话若已有活跃任务图，恢复轮询
  taskPolling.start(id)
  focusedTaskId.value = null
}

async function forceReloadMessages(id) {
  try {
    const raw = await fetchMessages(id)
    messagesBySession[id] = mergeAssistantHistory(raw)
    injectTaskCards(id)
    injectIntentCard(id)
  } catch {
    // 轮询期间忽略
  }
}

function injectTaskCards(id) {
  const list = messagesBySession[id]
  if (!list) return
  const graph = taskPolling.getGraph(id)
  // 去掉旧虚拟卡后重注入，避免重复
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].kind === 'hil' || list[i].kind === 'postcard' || list[i].kind === 'recovery') list.splice(i, 1)
  }
  if (!graph) return
  for (const t of (graph.tasks || [])) {
    if (t.status === 'awaiting_confirm') {
      list.push({ kind: 'hil', task: t, id: 'hil:' + t.id, role: 'assistant' })
    } else if (t.status === 'failed') {
      list.push({ kind: 'recovery', task: t, id: 'recovery:' + t.id, role: 'assistant' })
    } else if (t.agent_type === 'finalize' && t.status === 'finished') {
      list.push({ kind: 'postcard', task: t, id: 'postcard:' + t.id, role: 'assistant' })
    }
  }
}

// ready_to_confirm 时把确认单作为虚拟消息注入对话区，与 hil/postcard 同机制
function injectIntentCard(id) {
  const list = messagesBySession[id]
  if (!list) return
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].kind === 'intent-confirm') list.splice(i, 1)
  }
  const state = intentStateBySession[id]
  if (state && state.intent_status === 'ready_to_confirm') {
    list.push({ kind: 'intent-confirm', state, id: 'intent-confirm', role: 'assistant' })
  }
}

watch(activeIntentState, () => {
  if (activeId.value) injectIntentCard(activeId.value)
})

taskPolling.configure({
  isStreaming: (sid) => !!streamingBySession[sid],
  reloadMessages: forceReloadMessages,
})

function onHilConfirmed(taskId) {
  const sid = activeId.value
  if (!sid) return
  forceReloadMessages(sid)
}
function onHilRetried(taskId) {
  const sid = activeId.value
  if (!sid) return
  taskPolling.start(sid) // 重跑后重新轮询跟踪进度
}
function onHilCancelled(sid) {
  taskPolling.stop()
  forceReloadMessages(sid)
}

async function onCreate() {
  try {
    const meta = await createSession()
    sessions.value.unshift(meta)
    messagesBySession[meta.id] = []
    intentStateBySession[meta.id] = null
    activeId.value = meta.id
    loadIntentState(meta.id)
  } catch (e) {
    alert(`新建失败: ${e.message}`)
  }
}

async function onDelete(id) {
  try {
    await deleteSession(id)
  } catch (e) {
    alert(`删除失败: ${e.message}`)
    return
  }
  const wasActive = activeId.value === id
  sessions.value = sessions.value.filter((c) => c.id !== id)
  delete messagesBySession[id]
  delete streamingBySession[id]
  delete intentStateBySession[id]
  if (wasActive) {
    if (sessions.value.length > 0) {
      activeId.value = sessions.value[0].id
      await Promise.all([loadMessages(activeId.value), loadIntentState(activeId.value)])
    } else {
      await onCreate()
    }
  }
}

async function onRename({ id, title }) {
  try {
    const meta = await renameSession(id, title)
    const idx = sessions.value.findIndex((c) => c.id === id)
    if (idx >= 0) sessions.value[idx] = { ...sessions.value[idx], ...meta }
  } catch (e) {
    alert(`重命名失败: ${e.message}`)
  }
}

function bumpSession(id) {
  const idx = sessions.value.findIndex((c) => c.id === id)
  if (idx > 0) {
    const [it] = sessions.value.splice(idx, 1)
    it.updated_at = Date.now() / 1000
    sessions.value.unshift(it)
  } else if (idx === 0) {
    sessions.value[0].updated_at = Date.now() / 1000
  }
}

function createStreamHandler(sessionId) {
  const list = messagesBySession[sessionId] || (messagesBySession[sessionId] = [])

  let assistantIdx = -1
  const cur = () => (assistantIdx >= 0 ? list[assistantIdx] : null)

  function startNewAssistant() {
    list.push(makeEmptyAssistant())
    assistantIdx = list.length - 1
  }
  function ensureAssistant() {
    if (!cur()) startNewAssistant()
    return cur()
  }
  function finalizeCurrent() {
    const c = cur()
    if (!c) return
    // 状态条仅在进行时显示，结束即消失
    if (c.thinking.state === 'running') c.thinking.state = 'idle'
    if (c.tools.state === 'running') c.tools.state = 'idle'
  }

  // 尾部无正文气泡：工具并入上一条助手消息后丢弃
  function dropTrailingEmptyBubble() {
    if (list.length < 2) return
    const last = list[list.length - 1]
    if (last.role !== 'assistant') return
    if (last.content && last.content.trim()) return
    let prev = null
    for (let i = list.length - 2; i >= 0; i--) {
      if (list[i].role === 'assistant') {
        prev = list[i]
        break
      }
    }
    if (prev && last.tools.items.length) {
      for (const it of last.tools.items) {
        prev.tools.items.push({
          id: it.id,
          name: it.name,
          arguments: it.arguments,
          duration_ms: it.duration_ms ?? null,
          content: it.content,
          display: it.display,
        })
      }
    }
    list.splice(list.length - 1, 1)
    assistantIdx = list.length - 1
  }

  const onEvent = (payload) => {
    // trace 事件直接入 store，不走气泡逻辑
    if (payload.type === 'trace') {
      traceStore.addTrace(sessionId, payload)
      return
    }
    if (payload.type === 'intent_state') {
      intentStateBySession[sessionId] = payload.state
      return
    }

    if (payload.type === 'message_start') {
      finalizeCurrent()
      const c = cur()
      if (!c || c.content) startNewAssistant()
    } else if (payload.type === 'reasoning') {
      const c = ensureAssistant()
      if (c.thinking.state !== 'running') c.thinking.state = 'running'
    } else if (payload.type === 'reasoning_done') {
      const c = cur()
      if (!c) return
      // 思考结束即消失状态条
      if (c.thinking.state === 'running') c.thinking.state = 'idle'
    } else if (payload.type === 'token') {
      ensureAssistant().content += payload.content
    } else if (payload.type === 'tool_call') {
      const c = ensureAssistant()
      const tools = c.tools
      tools.state = 'running'
      tools.items.push({
        id: payload.id,
        name: payload.name,
        arguments: payload.arguments || {},
        duration_ms: null,
        content: '',
        display: payload.display || payload.name,
        running_label: payload.running_label || null,
      })
    } else if (payload.type === 'tool_result') {
      const c = cur()
      if (!c) return
      const tools = c.tools
      const item =
        tools.items.find((it) => it.id === payload.tool_call_id) ||
        tools.items.find((it) => it.name === payload.name && it.duration_ms === null)
      if (item) {
        item.duration_ms = payload.duration_ms
        item.content = payload.content
      }
      // 全部工具已落定则退出工具态
      if (tools.state === 'running' && !tools.items.some((it) => it.duration_ms == null)) {
        tools.state = 'idle'
      }
    } else if (payload.type === 'title_update') {
      const idx = sessions.value.findIndex((c) => c.id === payload.id)
      if (idx >= 0) {
        sessions.value[idx] = {
          ...sessions.value[idx],
          title: payload.title,
        }
      }
    } else if (payload.type === 'done') {
      finalizeCurrent()
      dropTrailingEmptyBubble()
      streamingBySession[sessionId] = false
      // 重拉取回非流式落库的气泡并续轮询
      forceReloadMessages(sessionId).finally(() => taskPolling.start(sessionId))
    } else if (payload.type === 'busy') {
      // 活跃任务准入拒绝的瞬时信号：不解禁输入框、不注入气泡，进度由任务图反映
      streamingBySession[sessionId] = false
    } else if (payload.type === 'error') {
      ensureAssistant().content = `[错误] ${payload.content}`
      streamingBySession[sessionId] = false
    }
  }

  return { onEvent, finalizeCurrent, dropTrailingEmptyBubble }
}

async function runAssistantStream(sessionId, streamFactory) {
  streamingBySession[sessionId] = true
  const handler = createStreamHandler(sessionId)
  const { done } = streamFactory(handler.onEvent)
  await done
  handler.finalizeCurrent()
  handler.dropTrailingEmptyBubble()
  streamingBySession[sessionId] = false
  bumpSession(sessionId)
}

async function onSend(text) {
  const sessionId = activeId.value
  if (!sessionId) return
  if (!text.trim() || streamingBySession[sessionId] || hasActiveTask.value) return

  const list = messagesBySession[sessionId] || (messagesBySession[sessionId] = [])
  list.push({ role: 'user', content: text })
  await runAssistantStream(sessionId, (onEvent) => streamChat(sessionId, text, onEvent))
}

async function onIntentConfirm() {
  const sessionId = activeId.value
  if (!sessionId || streamingBySession[sessionId] || hasActiveTask.value) return
  const list = messagesBySession[sessionId] || (messagesBySession[sessionId] = [])
  list.push({ role: 'user', content: '确认并开始' })
  await runAssistantStream(sessionId, (onEvent) => confirmIntent(sessionId, onEvent))
}

async function onIntentRevise() {
  const sessionId = activeId.value
  if (!sessionId || streamingBySession[sessionId]) return
  try {
    intentStateBySession[sessionId] = await reopenIntent(sessionId)
    inputBarRef.value?.focus()
  } catch (e) {
    alert(`打开意图修改失败: ${e.message}`)
  }
}

async function onIntentStopAndRevise() {
  const sessionId = activeId.value
  if (!sessionId || streamingBySession[sessionId]) return
  try {
    await cancelPipeline(sessionId)
    taskPolling.stop()
    intentStateBySession[sessionId] = await reopenIntent(sessionId)
    await forceReloadMessages(sessionId)
    inputBarRef.value?.focus()
  } catch (e) {
    alert(`停止并修改失败: ${e.message}`)
  }
}

onMounted(async () => {
  try {
    const list = await listSessions()
    sessions.value = list
  } catch {
    sessions.value = []
  }
  if (sessions.value.length === 0) {
    await onCreate()
  } else {
    // 复用会话切换完整路径，让刷新后的任务图靠轮询恢复
    await selectSession(sessions.value[0].id)
  }
})
</script>

<template>
  <div class="app-shell">
    <SessionSidebar
      :sessions="sessions"
      :active-id="activeId"
      :streaming-map="streamingBySession"
      @select="selectSession"
      @create="onCreate"
      @delete="onDelete"
      @rename="onRename"
    />
    <div class="main-panel">
      <header class="header">
        <span class="session-title">{{ activeTitle }}</span>
        <button class="header-console-btn" @click="consoleOpen = !consoleOpen"
          :class="{ active: consoleOpen }" title="控制台">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </button>
      </header>
      <ChatWindow
        :messages="messages"
        :streaming="streaming"
        :session-id="activeId || ''"
        @hil-confirmed="onHilConfirmed"
        @hil-retried="onHilRetried"
        @hil-cancelled="onHilCancelled"
        @intent-confirm="onIntentConfirm"
        @intent-revise="onIntentRevise"
      />
      <PipelineRuntimeDock
        :graph="activeGraph"
        :focused-task-id="focusedTaskId"
        :session-id="activeId || ''"
        @finish-done="forceReloadMessages(activeId)"
      />
      <PipelineProgressBar :graph="activeGraph" />
      <InputBar ref="inputBarRef" :streaming="streaming" :has-active-task="hasActiveTask" @send="onSend" />
    </div>
    <TeamPanel
      :graph="activeGraph"
      :focused-task-id="focusedTaskId"
      :intent-state="activeIntentState"
      :has-active-task="hasActiveTask"
      @focus="onTaskFocus"
      @stop-and-revise="onIntentStopAndRevise"
    />
  </div>
  <ConsolePanel :active-id="activeId" :trace-store="traceStore" v-model:open="consoleOpen" />
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  background: var(--ch-bg-warm);
  padding: 0;
  gap: 0;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
  height: 100%;
  background: #ffffff;
  border: none;
  box-shadow: none;
}

.header {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 34px;
  height: 64px;
  background: #ffffff;
  color: var(--ch-text);
  border-bottom: 1px solid var(--ch-border);
  flex-shrink: 0;
}

.session-title {
  font-size: 18px;
  font-family: var(--ch-serif);
  font-weight: 600;
  color: var(--ch-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.header-console-btn {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 34px;
  height: 34px;
  border: 1px solid var(--ch-border);
  background: #fff;
  color: var(--ch-muted);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.18s, color 0.18s, border-color 0.18s, box-shadow 0.18s;
}

.header-console-btn:hover {
  background: var(--ch-primary-soft);
  color: var(--ch-primary);
  border-color: var(--ch-border-2);
}

.header-console-btn.active {
  background: var(--ch-bg-cool);
  border-color: var(--ch-border-2);
  color: var(--ch-body);
  box-shadow: none;
}

@media (max-width: 900px) {
  .app-shell {
    padding: 0;
  }
}
</style>
