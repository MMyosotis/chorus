<script setup>
import { computed } from 'vue'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({ graph: { type: Object, default: null } })

function stepState(status) {
  if (status === 'finished') return 'done'
  if (status === 'running') return 'running'
  if (status === 'awaiting_confirm') return 'waiting'
  if (status === 'failed' || status === 'cancelled') return 'failed'
  return 'pending'
}

const tasks = computed(() => props.graph?.tasks || [])

const current = computed(() => {
  const next = tasks.value.find(
    (task) => task.status !== 'finished' && task.status !== 'failed' && task.status !== 'cancelled',
  )
  return next || tasks.value[tasks.value.length - 1] || null
})

const label = computed(() => {
  if (!tasks.value.length) return ''
  const active = current.value
  if (!active) return '创作完成'
  const idx = tasks.value.indexOf(active) + 1
  const role = ROLE_LABELS[active.agent_type] || active.agent_type
  if (active.status === 'awaiting_confirm') return `等你确认 · 第 ${idx}/${tasks.value.length} 步`
  if (active.status === 'running') return `创作进行中 · 第 ${idx}/${tasks.value.length} 步`
  return `第 ${idx}/${tasks.value.length} 步`
})
</script>

<template>
  <div v-if="tasks.length" class="progress-banner">
    <span class="progress-label">{{ label }}</span>
    <div class="pipe">
      <template v-for="(task, i) in tasks" :key="task.id">
        <span v-if="i > 0" class="pipe-sep" aria-hidden="true">›</span>
        <span class="pipe-step" :class="stepState(task.status)">
          <span v-if="stepState(task.status) === 'done'" class="pipe-tick" aria-hidden="true">✓</span>
          <span class="pipe-name">{{ ROLE_LABELS[task.agent_type] || task.agent_type }}</span>
        </span>
      </template>
    </div>
  </div>
</template>

<style scoped>
.progress-banner {
  width: min(var(--ch-runtime-width), calc(100% - 32px));
  margin: 2px auto 12px;
  display: flex;
  align-items: baseline;
  gap: 14px;
  padding: 0 4px;
  font-size: 12.5px;
  color: var(--ch-muted);
  flex-shrink: 0;
}
.progress-label {
  white-space: nowrap;
  font-weight: 500;
  color: var(--ch-faint);
  flex-shrink: 0;
}
.pipe {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: 6px;
  min-width: 0;
  overflow: hidden;
}
.pipe-sep {
  color: var(--ch-border-2);
  font-size: 13px;
  flex-shrink: 0;
  line-height: 1;
}
.pipe-step {
  display: inline-flex;
  align-items: baseline;
  gap: 3px;
  white-space: nowrap;
}
.pipe-tick {
  color: var(--ch-green);
  font-size: 11px;
}
.pipe-name {
  color: var(--ch-faint);
  letter-spacing: 0.2px;
}

.pipe-step.done .pipe-name { color: var(--ch-muted); }
.pipe-step.running .pipe-name {
  color: var(--ch-orange);
  font-family: var(--ch-serif);
  font-weight: 600;
  font-size: 13.5px;
}
.pipe-step.waiting .pipe-name {
  color: var(--ch-primary);
  font-family: var(--ch-serif);
  font-weight: 600;
  font-size: 13.5px;
}
.pipe-step.failed .pipe-name { color: var(--ch-red); }

@media (max-width: 760px) {
  .progress-banner { gap: 8px; }
  .progress-label { display: none; }
}
</style>
