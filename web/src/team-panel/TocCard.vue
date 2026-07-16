<script setup>
import { ROLE_LABELS, badgeOf } from './roleMeta.js'

defineProps({
  tasks: { type: Array, default: () => [] },
  focusedTaskId: { type: String, default: null },
})
defineEmits(['focus'])

const STATUS_TEXT = {
  pending: '待确认', running: '进行中', awaiting_confirm: '待确认',
  finished: '完成', failed: '失败', cancelled: '已取消',
}

const isInteractive = (task) => !['pending', 'cancelled'].includes(task.status)
</script>

<template>
  <section class="slip toc-slip">
    <div class="r-eyebrow">
      <span>目录 · CONTENTS</span>
    </div>
    <TransitionGroup name="toc-insert" tag="nav" class="toc">
      <button
        v-for="(task, idx) in tasks"
        :key="task.id"
        class="toc-row"
        :class="[badgeOf(task.status).cls, { focused: task.id === focusedTaskId }]"
        :style="{ '--toc-order': idx }"
        :disabled="!isInteractive(task)"
        @click="isInteractive(task) && $emit('focus', task.id)"
        type="button"
      >
        <span class="toc-num">{{ String(idx + 1).padStart(2, '0') }}</span>
        <span class="toc-mid">
          <span class="toc-name">{{ ROLE_LABELS[task.agent_type] }}</span>
          <span class="toc-leader"></span>
        </span>
        <span class="toc-status">
          <i class="dot"></i>{{ STATUS_TEXT[task.status] }}
        </span>
      </button>
    </TransitionGroup>
  </section>
</template>

<style scoped>
.slip {
  margin: 0;
  padding: 0;
  background: transparent;
  border: 0;
}
.r-eyebrow {
  display: flex;
  align-items: center;
  font-family: var(--ch-serif);
  height: var(--ch-rail-head-height);
  padding: 1px 2px 10px;
  border-bottom: 1px solid var(--ch-rail-rule);
  font-size: var(--ch-rail-head-size);
  font-weight: var(--ch-rail-head-weight);
  line-height: var(--ch-rail-head-line);
  color: var(--ch-body);
  letter-spacing: var(--ch-rail-head-tracking);
  text-transform: uppercase;
  margin-bottom: 0;
  color: var(--ch-warm);
}

.toc {
  display: flex;
  flex-direction: column;
}

.toc-row {
  display: grid;
  width: 100%;
  min-height: 44px;
  grid-template-columns: 31px 1fr auto;
  align-items: center;
  gap: 8px;
  font-family: var(--ch-serif);
  cursor: pointer;
  padding: 0 2px;
  border: 0;
  border-bottom: 1px dashed var(--ch-rail-dash);
  background: transparent;
  text-align: left;
  transition: background-color .2s ease-out, color .2s ease-out;
}
.toc-row:disabled { cursor: default; }
.toc-num, .toc-name, .toc-status, .toc-status .dot { transition: color .22s ease-out, background-color .22s ease-out, border-color .22s ease-out, opacity .22s ease-out; }
.toc-insert-enter-active { transition: opacity .26s ease-out, transform .26s cubic-bezier(.2,.72,.25,1); transition-delay: calc(var(--toc-order, 0) * 28ms); }
.toc-insert-enter-from { opacity: 0; transform: translateY(7px); }
.toc-insert-move { transition: transform .26s cubic-bezier(.2,.72,.25,1); }

.toc-num {
  font-family: var(--ch-serif);
  font-size: var(--ch-rail-section-size);
  font-weight: 600;
  color: var(--ch-warm);
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
}

.toc-mid {
  display: flex;
  align-items: baseline;
  min-width: 0;
}

.toc-name {
  font-family: var(--ch-serif);
  font-size: var(--ch-rail-section-size);
  font-weight: 500;
  line-height: 1.35;
  color: var(--ch-body);
  white-space: nowrap;
}

.toc-leader { display: none; }

.toc-status {
  font-family: var(--ch-serif);
  font-size: var(--ch-rail-meta-size);
  font-weight: 500;
  line-height: 1;
  color: var(--ch-meta);
  display: inline-flex;
  align-items: center;
  gap: 5px;
  letter-spacing: 0.03em;
  white-space: nowrap;
}

.toc-status .dot {
  display: none;
}

.toc-row.running .toc-num,
.toc-row.waiting .toc-num { color: var(--ch-text); }
.toc-row.running .toc-name,
.toc-row.waiting .toc-name { color: var(--ch-text); font-weight: 500; }
.toc-row.running .toc-status,
.toc-row.waiting .toc-status { color: var(--ch-primary); }
.toc-row.running .toc-status .dot,
.toc-row.waiting .toc-status .dot {
  display: inline-block;
  width: 4px;
  height: 4px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: currentColor;
}
.toc-row.running .toc-status .dot { animation: tocPulse 1.7s ease-in-out infinite; }

.toc-row.done .toc-num { color: var(--ch-meta); }
.toc-row.done .toc-name { color: var(--ch-meta); }
.toc-row.done .toc-status { color: var(--ch-green); }

.toc-row.failed .toc-name { color: var(--ch-red); }
.toc-row.failed .toc-status { color: var(--ch-red); }

.toc-row.focused .toc-num { color: var(--ch-warm); }
.toc-row.focused .toc-name { color: var(--ch-text); }
.toc-row.focused .toc-status { color: var(--ch-warm); }
.toc-row.focused .toc-leader { border-bottom-color: var(--ch-warm); opacity: 0.45; }
.toc-row.focused.running .toc-status,
.toc-row.focused.waiting .toc-status { color: var(--ch-primary); }
.toc-row.focused.done .toc-status { color: var(--ch-green); }
.toc-row.focused.failed .toc-status { color: var(--ch-red); }

@keyframes tocPulse { 0%, 100% { opacity: .28; } 50% { opacity: 1; } }
</style>
