<script setup>
import { ref, watch, nextTick } from 'vue'
import MessageBubble from './MessageBubble.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  streaming: { type: Boolean, default: false },
})

const container = ref(null)

watch(
  () =>
    props.messages.map(
      (m) =>
        m.content +
        '|' +
        (m.thinking?.items?.length ?? 0) +
        ':' +
        (m.thinking?.items?.[m.thinking.items.length - 1]?.text?.length ?? 0) +
        '|' +
        (m.tools?.items?.length ?? 0)
    ),
  () => {
    nextTick(() => {
      if (container.value) {
        container.value.scrollTop = container.value.scrollHeight
      }
    })
  },
  { deep: true }
)
</script>

<template>
  <div ref="container" class="chat-window">
    <div class="chat-inner">
      <MessageBubble
        v-for="(msg, idx) in messages"
        :key="idx"
        :role="msg.role"
        :content="msg.content"
        :thinking="msg.thinking"
        :tools="msg.tools"
        :show-cursor="streaming && idx === messages.length - 1 && msg.role === 'assistant'"
      />
      <div v-if="messages.length === 0" class="empty-hint">
        <svg class="empty-paw" viewBox="0 0 512 512" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
          <path d="M256 224c-79.41 0-192 122.76-192 200.25 0 34.9 26.81 55.75 71.74 55.75 48.84 0 81.09-25.08 120.26-25.08 39.51 0 71.85 25.08 120.26 25.08 44.93 0 71.74-20.85 71.74-55.75C448 346.76 335.41 224 256 224zm-147.28-12.61c-10.4-34.65-42.44-57.09-71.56-50.13-29.12 6.96-44.29 40.69-33.89 75.34 10.4 34.65 42.44 57.09 71.56 50.13 29.12-6.96 44.29-40.69 33.89-75.34zm84.72-20.78c30.94-8.14 46.42-49.94 34.58-93.36s-46.52-72.01-77.46-63.87-46.42 49.94-34.58 93.36c11.84 43.42 46.52 72.01 77.46 63.87zm281.39-29.34c-29.12-6.96-61.15 15.48-71.56 50.13-10.4 34.65 4.77 68.38 33.89 75.34 29.12 6.96 61.15-15.48 71.56-50.13 10.4-34.65-4.77-68.38-33.89-75.34zm-156.27 29.34c30.94 8.14 65.62-20.45 77.46-63.87s-3.64-85.21-34.58-93.36-65.62 20.45-77.46 63.87 3.64 85.22 34.58 93.36z"/>
        </svg>
        <p>发送消息开始对话</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 20px 16px;
  background: #f8fafc;
}

.chat-inner {
  max-width: 768px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 240px;
  color: #94a3b8;
  font-size: 16px;
}

.empty-paw {
  width: 48px;
  height: 48px;
  color: #cbd5e1;
}
</style>
