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
  <section class="slip toc-slip">
    <div class="knob orange"></div>
    <div class="r-eyebrow">
      <span>目录</span>
    </div>
    <nav class="toc">
      <div
        v-for="(task, idx) in tasks"
        :key="task.id"
        class="toc-row"
        :class="[badgeOf(task.status).cls, { focused: task.id === focusedTaskId }]"
        @click="$emit('focus', task.id)"
      >
        <span class="toc-num">{{ CN_NUM[idx] }}</span>
        <span class="toc-name">{{ ROLE_LABELS[task.agent_type] }}</span>
        <span class="toc-status">
          <span v-if="task.status === 'running'" class="toc-mini"></span>{{ STATUS_TEXT[task.status] }}
        </span>
      </div>
    </nav>
  </section>
</template>

<style scoped>
.slip {
  position: relative;
  background: var(--ch-bg-warm);
  border: 1px solid var(--ch-hair);
  padding: 22px 14px 14px;
  box-shadow:
    0 6px 16px -6px rgba(0, 0, 0, 0.05),
    0 2px 4px -1px rgba(0, 0, 0, 0.02);
}
.knob {
  position: absolute;
  top: -7px;
  left: 50%;
  transform: translateX(-50%);
  width: 15px;
  height: 15px;
  border-radius: 50%;
  z-index: 2;
}
.knob.orange {
  background: var(--ch-orange);
  box-shadow:
    inset 0 1px 1.5px rgba(255, 255, 255, 0.55),
    inset 0 -1px 1.5px rgba(0, 0, 0, 0.18),
    0 2px 3px rgba(0, 0, 0, 0.25);
}
.r-eyebrow {
  display: flex;
  align-items: center;
  font-family: var(--ch-serif);
  font-size: 13px;
  font-weight: 600;
  color: var(--ch-body);
  letter-spacing: 0.1em;
  margin-bottom: 14px;
}

.toc {
  display: flex;
  flex-direction: column;
}

.toc-row {
  display: grid;
  grid-template-columns: 20px 1fr auto;
  align-items: baseline;
  gap: 10px;
  font-family: var(--ch-serif);
  cursor: pointer;
  padding: 8px 0;
}
.toc-row::after {
  content: "";
  grid-column: 1 / -1;
  height: 1px;
  margin-top: 5px;
  background-image: linear-gradient(to right, var(--ch-hair) 50%, transparent 0%);
  background-size: 5px 1px;
  background-repeat: repeat-x;
  background-position: left center;
}
.toc-row:last-child::after { display: none; }

.toc-num { font-size: 15px; font-weight: 600; color: var(--ch-muted); line-height: 1; }
.toc-name { font-size: 12px; color: var(--ch-faint); }
.toc-status {
  font-size: 11px;
  color: var(--ch-faint);
  display: flex;
  align-items: center;
  gap: 5px;
}

.toc-row.done .toc-num { color: var(--ch-muted); }
.toc-row.done .toc-name,
.toc-row.done .toc-status { color: var(--ch-muted); }
.toc-row.running .toc-num { color: var(--ch-primary); }
.toc-row.running .toc-name,
.toc-row.running .toc-status { color: var(--ch-primary-2); font-weight: 600; }
.toc-row.failed .toc-name,
.toc-row.failed .toc-status { color: var(--ch-red); }
.toc-row.focused .toc-num { color: var(--ch-primary); }

.toc-mini {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ch-orange);
  animation: tocPulse 1.4s ease-in-out infinite;
}

@keyframes tocPulse {
  0%, 100% { opacity: .55; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.35); }
}
</style>
