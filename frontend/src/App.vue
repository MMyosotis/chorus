<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import ChatWindow from './components/ChatWindow.vue'
import InputBar from './components/InputBar.vue'
import ConversationSidebar from './components/ConversationSidebar.vue'
import {
  listConversations,
  createConversation,
  deleteConversation,
  renameConversation,
  fetchMessages,
  streamChat,
} from './api.js'

const conversations = ref([]) // [{id, title, created_at, updated_at}]
const messagesByConv = reactive({}) // { [id]: Message[] }
const streamingByConv = reactive({}) // { [id]: boolean }
const activeId = ref(null)

const messages = computed(() => messagesByConv[activeId.value] || [])
const streaming = computed(() => !!streamingByConv[activeId.value])
const activeTitle = computed(() => {
  const c = conversations.value.find((x) => x.id === activeId.value)
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

  const flushPending = () => {
    if (!pendingThinking.length && !pendingTools.length) return
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
  if (messagesByConv[id]) return
  try {
    const raw = await fetchMessages(id)
    messagesByConv[id] = mergeAssistantHistory(raw)
  } catch (e) {
    if (e.status === 404) {
      // 该会话已被后端清理
      conversations.value = conversations.value.filter((c) => c.id !== id)
      delete messagesByConv[id]
      delete streamingByConv[id]
      if (activeId.value === id) {
        if (conversations.value.length > 0) {
          activeId.value = conversations.value[0].id
          await loadMessages(activeId.value)
        } else {
          await onCreate()
        }
        alert('该会话已过期，已自动切换')
      }
    } else {
      messagesByConv[id] = []
    }
  }
}

async function selectConversation(id) {
  activeId.value = id
  await loadMessages(id)
}

async function onCreate() {
  try {
    const meta = await createConversation()
    conversations.value.unshift(meta)
    messagesByConv[meta.id] = []
    activeId.value = meta.id
  } catch (e) {
    alert(`新建失败: ${e.message}`)
  }
}

async function onDelete(id) {
  try {
    await deleteConversation(id)
  } catch (e) {
    alert(`删除失败: ${e.message}`)
    return
  }
  const wasActive = activeId.value === id
  conversations.value = conversations.value.filter((c) => c.id !== id)
  delete messagesByConv[id]
  delete streamingByConv[id]
  if (wasActive) {
    if (conversations.value.length > 0) {
      activeId.value = conversations.value[0].id
      await loadMessages(activeId.value)
    } else {
      await onCreate()
    }
  }
}

async function onRename({ id, title }) {
  try {
    const meta = await renameConversation(id, title)
    const idx = conversations.value.findIndex((c) => c.id === id)
    if (idx >= 0) conversations.value[idx] = { ...conversations.value[idx], ...meta }
  } catch (e) {
    alert(`重命名失败: ${e.message}`)
  }
}

function bumpConversation(id) {
  const idx = conversations.value.findIndex((c) => c.id === id)
  if (idx > 0) {
    const [it] = conversations.value.splice(idx, 1)
    it.updated_at = Date.now() / 1000
    conversations.value.unshift(it)
  } else if (idx === 0) {
    conversations.value[0].updated_at = Date.now() / 1000
  }
}

async function onSend(text) {
  const convId = activeId.value
  if (!convId) return
  if (!text.trim() || streamingByConv[convId]) return

  // 闭包 capture：所有引用都是 convId / list，与 activeId 解耦
  const list = messagesByConv[convId] || (messagesByConv[convId] = [])
  list.push({ role: 'user', content: text })
  streamingByConv[convId] = true

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

  const onEvent = (payload) => {
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
      const idx = conversations.value.findIndex((c) => c.id === payload.id)
      if (idx >= 0) {
        conversations.value[idx] = {
          ...conversations.value[idx],
          title: payload.title,
        }
      }
    } else if (payload.type === 'done') {
      finalizeCurrent()
      streamingByConv[convId] = false
    } else if (payload.type === 'error') {
      ensureAssistant().content = `[错误] ${payload.content}`
      streamingByConv[convId] = false
    }
  }

  const { done } = streamChat(convId, text, onEvent)
  await done
  finalizeCurrent()
  streamingByConv[convId] = false
  bumpConversation(convId)
}

onMounted(async () => {
  try {
    const list = await listConversations()
    conversations.value = list
  } catch {
    conversations.value = []
  }
  if (conversations.value.length === 0) {
    await onCreate()
  } else {
    activeId.value = conversations.value[0].id
    await loadMessages(activeId.value)
  }
})
</script>

<template>
  <div class="app-shell">
    <ConversationSidebar
      :conversations="conversations"
      :active-id="activeId"
      :streaming-map="streamingByConv"
      @select="selectConversation"
      @create="onCreate"
      @delete="onDelete"
      @rename="onRename"
    />
    <div class="main-panel">
      <header class="header">
        <span class="conv-title">{{ activeTitle }}</span>
      </header>
      <ChatWindow :messages="messages" :streaming="streaming" />
      <InputBar :streaming="streaming" @send="onSend" />
    </div>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  height: 100vh;
  width: 100%;
  overflow: hidden;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.header {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 24px;
  height: 56px;
  background: #ffffff;
  color: #1e293b;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.conv-title {
  font-size: 16px;
  font-weight: 500;
  color: #1e293b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
