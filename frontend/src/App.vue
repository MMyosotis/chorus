<script setup>
import { ref, onMounted } from 'vue'
import ChatWindow from './components/ChatWindow.vue'
import InputBar from './components/InputBar.vue'

const messages = ref([])
const streaming = ref(false)

function makeEmptyAssistant() {
  return {
    role: 'assistant',
    content: '',
    thinking: { state: 'idle', items: [], expanded: false },
    tools: { state: 'idle', items: [], expanded: false },
  }
}

function normalizeAssistant(msg) {
  // 后端历史中 thinking/tools 是数组；前端结构需要 state/expanded 包装
  const thinkingItems = Array.isArray(msg.thinking) ? msg.thinking : []
  const toolItems = Array.isArray(msg.tools) ? msg.tools : []
  return {
    role: 'assistant',
    content: msg.content || '',
    thinking: {
      state: thinkingItems.length > 0 ? 'completed' : 'idle',
      items: thinkingItems.map((it) => ({
        text: it.text || '',
        duration_ms: it.duration_ms ?? null,
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
      })),
      expanded: false,
    },
  }
}

// 把连续的"无 content 的 assistant 轮次"并入下一条有 content 的 assistant 消息，
// 这样中间纯思考 / 工具调用的轮次不会单独显示成空气泡。
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
      // 跨界：先把 pending 落地，免得跨过 user 把元数据贴到下一轮
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
  // 尾部仍有 pending（如 max_iterations 全程未产出 content）→ 保留为一个独立气泡，避免信息丢失
  flushPending()
  return result
}

async function fetchHistory() {
  try {
    const res = await fetch('/api/chat/history')
    const data = await res.json()
    const raw = data.messages || []
    messages.value = mergeAssistantHistory(raw)
  } catch {
    // 后端未启动时忽略
  }
}

async function sendMessage(text) {
  if (!text.trim() || streaming.value) return

  messages.value.push({ role: 'user', content: text })
  streaming.value = true

  // 当前 assistant 气泡的索引；后端每个 OpenAI 轮次发一次 message_start，
  // 我们就 push 一个新气泡并把游标切过去。
  let assistantIdx = -1
  const cur = () => (assistantIdx >= 0 ? messages.value[assistantIdx] : null)

  function startNewAssistant() {
    messages.value.push(makeEmptyAssistant())
    assistantIdx = messages.value.length - 1
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

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text }),
    })

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      const parts = buffer.split('\n\n')
      buffer = parts.pop()

      for (const part of parts) {
        const line = part.trim()
        if (!line.startsWith('data: ')) continue
        try {
          const payload = JSON.parse(line.slice(6))
          if (payload.type === 'message_start') {
            // 新一轮：先把上一轮的 running 状态收尾。
            // 如果当前气泡还没产出 content，则复用它，让后续 thinking / tools 继续累积到同一气泡，
            // 避免出现"只有思考和工具调用、没有正文"的空壳气泡。
            finalizeCurrent()
            const c = cur()
            if (!c || c.content) startNewAssistant()
          } else if (payload.type === 'reasoning') {
            const c = ensureAssistant()
            const t = c.thinking
            if (t.state !== 'running') {
              t.state = 'running'
              t.items.push({ text: '', duration_ms: null })
            }
            const last = t.items[t.items.length - 1]
            last.text += payload.content
          } else if (payload.type === 'reasoning_done') {
            const c = cur()
            if (!c) continue
            c.thinking.state = 'completed'
            const last = c.thinking.items[c.thinking.items.length - 1]
            if (last) last.duration_ms = payload.duration_ms
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
            })
          } else if (payload.type === 'tool_result') {
            const c = cur()
            if (!c) continue
            const tools = c.tools
            const item =
              tools.items.find((it) => it.id === payload.tool_call_id) ||
              tools.items.find((it) => it.name === payload.name && it.duration_ms === null)
            if (item) {
              item.duration_ms = payload.duration_ms
              item.content = payload.content
            }
          } else if (payload.type === 'done') {
            finalizeCurrent()
          } else if (payload.type === 'error') {
            ensureAssistant().content = `[错误] ${payload.content}`
          }
        } catch {
          // 忽略解析失败的行
        }
      }
    }
  } catch (e) {
    ensureAssistant().content = `[连接错误] ${e.message}`
  }

  finalizeCurrent()
  streaming.value = false
}

async function newChat() {
  if (messages.value.length > 0 && !confirm('确定要开始新对话吗？当前对话将被清空。')) {
    return
  }
  await fetch('/api/chat/reset', { method: 'POST' })
  messages.value = []
}

onMounted(fetchHistory)
</script>

<template>
  <div class="app">
    <header class="header">
      <div class="header-left">
        <svg class="logo" viewBox="0 0 512 512" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
          <path d="M256 224c-79.41 0-192 122.76-192 200.25 0 34.9 26.81 55.75 71.74 55.75 48.84 0 81.09-25.08 120.26-25.08 39.51 0 71.85 25.08 120.26 25.08 44.93 0 71.74-20.85 71.74-55.75C448 346.76 335.41 224 256 224zm-147.28-12.61c-10.4-34.65-42.44-57.09-71.56-50.13-29.12 6.96-44.29 40.69-33.89 75.34 10.4 34.65 42.44 57.09 71.56 50.13 29.12-6.96 44.29-40.69 33.89-75.34zm84.72-20.78c30.94-8.14 46.42-49.94 34.58-93.36s-46.52-72.01-77.46-63.87-46.42 49.94-34.58 93.36c11.84 43.42 46.52 72.01 77.46 63.87zm281.39-29.34c-29.12-6.96-61.15 15.48-71.56 50.13-10.4 34.65 4.77 68.38 33.89 75.34 29.12 6.96 61.15-15.48 71.56-50.13 10.4-34.65-4.77-68.38-33.89-75.34zm-156.27 29.34c30.94 8.14 65.62-20.45 77.46-63.87s-3.64-85.21-34.58-93.36-65.62 20.45-77.46 63.87 3.64 85.22 34.58 93.36z"/>
        </svg>
        <span class="title">Little Kitty</span>
      </div>
      <button class="new-chat-btn" @click="newChat">新对话</button>
    </header>
    <ChatWindow :messages="messages" :streaming="streaming" />
    <InputBar :streaming="streaming" @send="sendMessage" />
  </div>
</template>

<style scoped>
.app {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 100%;
  overflow: hidden;
  position: relative;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  background: #ffffff;
  color: #1e293b;
  border-bottom: 1px solid #e2e8f0;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo {
  width: 26px;
  height: 26px;
  color: #3b82f6;
}

.title {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #3b82f6;
}

.new-chat-btn {
  padding: 6px 16px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  background: transparent;
  color: #475569;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.new-chat-btn:hover {
  background: #f1f5f9;
  border-color: #3b82f6;
  color: #3b82f6;
}
</style>
