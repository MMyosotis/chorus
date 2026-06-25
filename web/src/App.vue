<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
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
} from './api.js'
import { useTraceStore } from './composables/useTraceStore.js'
import { useTaskPolling } from './composables/useTaskPolling.js'
import ProgressBanner from './main-panel/ProgressBanner.vue'
import TeamPanel from './team-panel/TeamPanel.vue'

const traceStore = useTraceStore()
const taskPolling = useTaskPolling()
const consoleOpen = ref(false)

const sessions = ref([]) // [{id, title, created_at, updated_at}]
const messagesBySession = reactive({}) // { [id]: Message[] }
const streamingBySession = reactive({}) // { [id]: boolean }
const activeId = ref(null)

const messages = computed(() => messagesBySession[activeId.value] || [])
const streaming = computed(() => !!streamingBySession[activeId.value])
const activeGraph = computed(() => taskPolling.getGraph(activeId.value))
const activeTitle = computed(() => {
  const c = sessions.value.find((x) => x.id === activeId.value)
  return c ? c.title : ''
})

function makeEmptyAssistant() {
  return {
    role: 'assistant',
    content: '',
    thinking: { state: 'idle', items: [], expanded: false },
    tools: { state: 'idle', items: [], expanded: false },
    _seq: 0,
  }
}

function normalizeAssistant(msg) {
  const thinkingItems = Array.isArray(msg.thinking) ? msg.thinking : []
  const toolItems = Array.isArray(msg.tools) ? msg.tools : []
  let seq = 0
  return {
    role: 'assistant',
    content: msg.content || '',
    thinking: {
      state: thinkingItems.length > 0 ? 'completed' : 'idle',
      items: thinkingItems.map((it) => ({
        text: it.text || '',
        duration_ms: it.duration_ms ?? null,
        seq: ++seq,
      })),
      expanded: false,
    },
    tools: {
      state: toolItems.length > 0 ? 'completed' : 'idle',
      items: toolItems.map((it) => ({
        name: it.name,
        arguments: it.arguments || {},
        duration_ms: it.duration_ms ?? null,
        content: it.content || '',
        display: it.display || it.name,
        seq: ++seq,
      })),
      expanded: false,
    },
  }
}

function mergeAssistantHistory(raw) {
  const result = []
  let pendingThinking = []
  let pendingTools = []

  // 把 pending（无正文 assistant 累积下来的 thinking/tools）合并到 result 中最近一条 assistant。
  // 没有可合并目标时才落成独立空壳 bubble（兜底，避免信息全丢）。
  const flushPending = () => {
    if (!pendingThinking.length && !pendingTools.length) return
    for (let i = result.length - 1; i >= 0; i--) {
      if (result[i].role === 'assistant') {
        const target = result[i]
        let s = 0
        for (const x of target.thinking.items) if ((x.seq || 0) > s) s = x.seq
        for (const x of target.tools.items) if ((x.seq || 0) > s) s = x.seq
        for (const t of pendingThinking) {
          target.thinking.items.push({
            text: t.text || '',
            duration_ms: t.duration_ms ?? null,
            seq: ++s,
          })
        }
        for (const t of pendingTools) {
          target.tools.items.push({
            name: t.name,
            arguments: t.arguments || {},
            duration_ms: t.duration_ms ?? null,
            content: t.content || '',
            display: t.display || t.name,
            seq: ++s,
          })
        }
        if (target.thinking.items.length) target.thinking.state = 'completed'
        if (target.tools.items.length) target.tools.state = 'completed'
        pendingThinking = []
        pendingTools = []
        return
      }
    }
    result.push(
      normalizeAssistant({
        role: 'assistant',
        content: '',
        thinking: pendingThinking,
        tools: pendingTools,
      })
    )
    pendingThinking = []
    pendingTools = []
  }

  for (const m of raw) {
    if (m.role !== 'assistant') {
      flushPending()
      result.push({ role: m.role, content: m.content })
      continue
    }
    const t = Array.isArray(m.thinking) ? m.thinking : []
    const ts = Array.isArray(m.tools) ? m.tools : []
    const hasContent = !!(m.content && m.content.trim())
    if (!hasContent) {
      pendingThinking.push(...t)
      pendingTools.push(...ts)
      continue
    }
    result.push(
      normalizeAssistant({
        role: 'assistant',
        content: m.content,
        thinking: [...pendingThinking, ...t],
        tools: [...pendingTools, ...ts],
      })
    )
    pendingThinking = []
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

async function selectSession(id) {
  activeId.value = id
  await loadMessages(id)
}

async function onCreate() {
  try {
    const meta = await createSession()
    sessions.value.unshift(meta)
    messagesBySession[meta.id] = []
    activeId.value = meta.id
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
  if (wasActive) {
    if (sessions.value.length > 0) {
      activeId.value = sessions.value[0].id
      await loadMessages(activeId.value)
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

async function onSend(text) {
  const sessionId = activeId.value
  if (!sessionId) return
  if (!text.trim() || streamingBySession[sessionId]) return

  // 闭包 capture：所有引用都是 sessionId / list，与 activeId 解耦
  const list = messagesBySession[sessionId] || (messagesBySession[sessionId] = [])
  list.push({ role: 'user', content: text })
  streamingBySession[sessionId] = true

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
    if (c.thinking.state === 'running') c.thinking.state = 'completed'
    if (c.tools.state === 'running') c.tools.state = 'completed'
  }

  // 合并尾部"只有 thinking/tools、没有正文"的 assistant 气泡到前一个 assistant 上。
  // 用于 agent loop 末尾模型按工具约束保持沉默时，避免出现幽灵气泡。
  function mergeTrailingEmptyBubble() {
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
    if (!prev) return
    let s = 0
    for (const x of prev.thinking.items) if ((x.seq || 0) > s) s = x.seq
    for (const x of prev.tools.items) if ((x.seq || 0) > s) s = x.seq
    const merged = [
      ...last.thinking.items.map((x) => ({ ...x, kind: 'thinking' })),
      ...last.tools.items.map((x) => ({ ...x, kind: 'tool' })),
    ]
    merged.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
    for (const it of merged) {
      if (it.kind === 'thinking') {
        prev.thinking.items.push({
          text: it.text,
          duration_ms: it.duration_ms ?? null,
          seq: ++s,
        })
      } else {
        prev.tools.items.push({
          id: it.id,
          name: it.name,
          arguments: it.arguments,
          duration_ms: it.duration_ms ?? null,
          content: it.content,
          display: it.display,
          seq: ++s,
        })
      }
    }
    if (prev.thinking.items.length) prev.thinking.state = 'completed'
    if (prev.tools.items.length) prev.tools.state = 'completed'
    list.splice(list.length - 1, 1)
    assistantIdx = list.length - 1
  }

  const onEvent = (payload) => {
    // trace 事件先吃掉，不走气泡逻辑（后端是 trace 唯一权威源，含 tool_call/tool_result 也都以 trace 形式产出）
    if (payload.type === 'trace') {
      traceStore.addTrace(sessionId, payload)
      return
    }

    if (payload.type === 'message_start') {
      finalizeCurrent()
      const c = cur()
      if (!c || c.content) startNewAssistant()
    } else if (payload.type === 'reasoning') {
      const c = ensureAssistant()
      const t = c.thinking
      if (t.state !== 'running') {
        t.state = 'running'
        c._seq = (c._seq || 0) + 1
        t.items.push({ text: '', duration_ms: null, seq: c._seq })
      }
      const last = t.items[t.items.length - 1]
      last.text += payload.content
    } else if (payload.type === 'reasoning_done') {
      const c = cur()
      if (!c) return
      c.thinking.state = 'completed'
      const last = c.thinking.items[c.thinking.items.length - 1]
      if (last) last.duration_ms = payload.duration_ms
    } else if (payload.type === 'token') {
      ensureAssistant().content += payload.content
    } else if (payload.type === 'tool_call') {
      const c = ensureAssistant()
      const tools = c.tools
      tools.state = 'running'
      c._seq = (c._seq || 0) + 1
      tools.items.push({
        id: payload.id,
        name: payload.name,
        arguments: payload.arguments || {},
        duration_ms: null,
        content: '',
        display: payload.display || payload.name,
        running_label: payload.running_label || null,
        seq: c._seq,
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
      mergeTrailingEmptyBubble()
      streamingBySession[sessionId] = false
    } else if (payload.type === 'error') {
      ensureAssistant().content = `[错误] ${payload.content}`
      streamingBySession[sessionId] = false
    }
  }

  const { done } = streamChat(sessionId, text, onEvent)
  await done
  finalizeCurrent()
  mergeTrailingEmptyBubble()
  streamingBySession[sessionId] = false
  bumpSession(sessionId)
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
    activeId.value = sessions.value[0].id
    await loadMessages(activeId.value)
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
      <ChatWindow :messages="messages" :streaming="streaming" />
      <ProgressBanner :graph="activeGraph" />
      <InputBar :streaming="streaming" @send="onSend" />
    </div>
    <TeamPanel :graph="activeGraph" />
  </div>
  <ConsolePanel :active-id="activeId" :trace-store="traceStore" v-model:open="consoleOpen" />
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
  /* 柔和氛围光：基色 + 三个低透明度径向光斑，营造光感而非纯色块 */
  background:
    radial-gradient(820px 620px at 8% -6%, rgba(129, 140, 248, 0.13), transparent 60%),
    radial-gradient(720px 560px at 102% 0%, rgba(56, 189, 248, 0.10), transparent 58%),
    radial-gradient(900px 700px at 50% 112%, rgba(236, 72, 153, 0.05), transparent 62%),
    #f6f8fd;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.header {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 24px;
  height: 56px;
  /* 半透明白 + 背景模糊，让底部的氛围光透上来 */
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(20px) saturate(160%);
  -webkit-backdrop-filter: blur(20px) saturate(160%);
  color: #1e293b;
  border-bottom: 1px solid rgba(226, 232, 240, 0.55);
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.6) inset;
  flex-shrink: 0;
}

.session-title {
  font-size: 16px;
  font-weight: 500;
  color: #1e293b;
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
  border: 1px solid transparent;
  background: transparent;
  color: #5b6b85;
  border-radius: 9px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.18s, color 0.18s, border-color 0.18s, box-shadow 0.18s;
}

.header-console-btn:hover {
  background: rgba(99, 102, 241, 0.07);
  color: #6366f1;
  border-color: rgba(129, 140, 248, 0.25);
}

.header-console-btn.active {
  background: rgba(99, 102, 241, 0.10);
  border-color: rgba(129, 140, 248, 0.4);
  color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.08), 0 8px 24px rgba(99, 102, 241, 0.20);
}
</style>
