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
    props.messages.map((m) => {
      const tItems = m.tools?.items || []
      const toolsSig = tItems
        .map((t) => `${t.content?.length ?? 0}:${t.duration_ms ?? ''}`)
        .join(',')
      return (
        m.content +
        '|' +
        (m.thinking?.items?.length ?? 0) +
        ':' +
        (m.thinking?.items?.[m.thinking.items.length - 1]?.text?.length ?? 0) +
        '|' +
        tItems.length +
        '|' +
        toolsSig
      )
    }),
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
  background: transparent;
  scrollbar-gutter: stable;
}

.chat-inner {
  max-width: 768px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 36px;
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
  letter-spacing: 0.5px;
}
</style>
