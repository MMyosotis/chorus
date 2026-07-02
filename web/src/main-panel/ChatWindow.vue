<script setup>
import { ref, watch, nextTick } from 'vue'
import MessageBubble from './MessageBubble.vue'
import HilCard from './HilCard.vue'
import PostCard from './PostCard.vue'
import RecoveryCard from './RecoveryCard.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  streaming: { type: Boolean, default: false },
  sessionId: { type: String, default: '' },
})

defineEmits(['hil-confirmed', 'hil-retried', 'hil-cancelled'])

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
        (m.thinking?.state ?? 'idle') +
        '|' +
        (m.tools?.state ?? 'idle') +
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
      <template v-for="(msg, idx) in messages" :key="msg.id || idx">
        <HilCard
          v-if="msg.kind === 'hil'"
          :task="msg.task"
          :session-id="sessionId"
          @confirmed="$emit('hil-confirmed', $event)"
          @retried="$emit('hil-retried', $event)"
          @cancelled="$emit('hil-cancelled', $event)"
        />
        <PostCard v-else-if="msg.kind === 'postcard'" :task="msg.task" />
        <RecoveryCard
          v-else-if="msg.kind === 'recovery'"
          :task="msg.task"
          :session-id="sessionId"
          @retried="$emit('hil-retried', $event)"
          @cancelled="$emit('hil-cancelled', $event)"
        />
        <MessageBubble
          v-else
          :role="msg.role"
          :content="msg.content"
          :thinking="msg.thinking"
          :tools="msg.tools"
          :show-cursor="streaming && idx === messages.length - 1 && msg.role === 'assistant'"
        />
      </template>
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
  padding: 34px 16px 10px;
  background: transparent;
  scrollbar-gutter: stable;
}

.chat-inner {
  max-width: var(--ch-chat-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 240px;
  color: var(--ch-faint);
  font-size: 16px;
  letter-spacing: 0.5px;
}
</style>
