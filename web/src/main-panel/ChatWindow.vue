<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import MessageBubble from './MessageBubble.vue'
import HilCard from './HilCard.vue'
import PostCard from './PostCard.vue'
import RecoveryCard from './RecoveryCard.vue'
import IntentConfirmCard from './IntentConfirmCard.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  streaming: { type: Boolean, default: false },
  sessionId: { type: String, default: '' },
  sessionUpdatedAt: { type: Number, default: null },
})

defineEmits(['hil-confirmed', 'hil-retried', 'hil-cancelled', 'intent-confirm', 'intent-revise'])

const container = ref(null)

const dateline = computed(() => {
  const ts = props.sessionUpdatedAt
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}.${m}.${day}`
})

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
      <div v-if="dateline" class="dateline">
        <span>{{ dateline }}</span>
        <span class="sep">·</span>
        <span>讨论</span>
      </div>
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
        <IntentConfirmCard
          v-else-if="msg.kind === 'intent-confirm'"
          :state="msg.state"
          @confirm="$emit('intent-confirm')"
          @revise="$emit('intent-revise')"
        />
        <MessageBubble
          v-else
          :role="msg.role"
          :content="msg.content"
          :thinking="msg.thinking"
          :tools="msg.tools"
          :active="streaming && idx === messages.length - 1 && msg.role === 'assistant'"
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
  scrollbar-gutter: stable both-edges;
}

.chat-inner {
  max-width: var(--ch-runtime-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--ch-turn-gap);
}

.dateline {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 12px;
  color: var(--ch-faint);
  letter-spacing: 0.3px;
}

.dateline .sep {
  color: var(--ch-border-2);
}

.dateline::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--ch-hair);
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
