<script setup>
import { ROLE_LABELS, badgeOf } from './roleMeta.js'

defineProps({
  tasks: { type: Array, default: () => [] },
  focusedTaskId: { type: String, default: null },
})
defineEmits(['focus'])

const STATUS_TEXT = {
  pending: '-',
  running: '写着',
  awaiting_confirm: '待阅',
  finished: '成',
  failed: '败',
  cancelled: '-',
}
const CN_NUM = ['一', '二', '三', '四', '五']
</script>

<template>
  <nav class="toc">
    <div
      v-for="(t, i) in tasks"
      :key="t.id"
      class="toc-row"
      :class="[badgeOf(t.status).cls, { focused: t.id === focusedTaskId }]"
      @click="$emit('focus', t.id)"
    >
      <span class="toc-num">{{ CN_NUM[i] }}</span>
      <span class="toc-name">{{ ROLE_LABELS[t.agent_type] }}</span>
      <span class="toc-status">
        <span v-if="t.status === 'running'" class="toc-mini"></span>{{ STATUS_TEXT[t.status] }}
      </span>
    </div>
  </nav>
</template>

<style scoped>
.toc {
  display: flex;
  flex-direction: column;
  gap: 13px;
}

.toc-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  font-size: 13px;
  cursor: pointer;
  padding: 3px 0;
  font-family: var(--ch-serif);
}

.toc-num { color: var(--ch-faint); width: 14px; }
.toc-name { color: var(--ch-faint); }
.toc-status {
  font-size: 12px;
  color: var(--ch-faint);
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 5px;
}

.toc-row.done .toc-name,
.toc-row.done .toc-status { color: var(--ch-muted); }
.toc-row.running .toc-name,
.toc-row.running .toc-status { color: var(--ch-primary-2); font-weight: 600; }
.toc-row.waiting .toc-name,
.toc-row.waiting .toc-status { color: var(--ch-primary-2); font-weight: 600; }
.toc-row.failed .toc-name,
.toc-row.failed .toc-status { color: var(--ch-red); }
.toc-row.focused .toc-num { color: var(--ch-primary); }

.toc-mini {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ch-orange);
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: .55; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.15); }
}
</style>
