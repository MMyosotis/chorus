<script setup>
import { ref, onMounted } from 'vue'
import ChatWindow from './components/ChatWindow.vue'
import InputBar from './components/InputBar.vue'

const messages = ref([])
const streaming = ref(false)

async function fetchHistory() {
  try {
    const res = await fetch('/api/chat/history')
    const data = await res.json()
    messages.value = data.messages || []
  } catch {
    // 后端未启动时忽略
  }
}

async function sendMessage(text) {
  if (!text.trim() || streaming.value) return

  messages.value.push({ role: 'user', content: text })
  streaming.value = true

  // 追加空的 assistant 消息，流式填充
  messages.value.push({ role: 'assistant', content: '' })
  const assistantIdx = messages.value.length - 1

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
          if (payload.type === 'token') {
            messages.value[assistantIdx].content += payload.content
          } else if (payload.type === 'error') {
            messages.value[assistantIdx].content = `[错误] ${payload.content}`
          }
        } catch {
          // 忽略解析失败的行
        }
      }
    }
  } catch (e) {
    messages.value[assistantIdx].content = `[连接错误] ${e.message}`
  }

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
        <span class="logo">🐾</span>
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
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  background: #1e40af;
  color: #fff;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo {
  font-size: 22px;
}

.title {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.new-chat-btn {
  padding: 6px 16px;
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 6px;
  background: transparent;
  color: #fff;
  font-size: 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.new-chat-btn:hover {
  background: rgba(255, 255, 255, 0.15);
}
</style>
