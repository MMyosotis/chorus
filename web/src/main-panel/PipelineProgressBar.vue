<script setup>
import { computed } from 'vue'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({ graph: { type: Object, default: null } })

function segState(status) {
  if (status === 'finished') return 'done'
  if (status === 'running') return 'running'
  if (status === 'awaiting_confirm') return 'waiting'
  if (status === 'failed' || status === 'cancelled') return 'failed'
  return 'pending'
}

const tasks = computed(() => {
  const ts = props.graph?.tasks || []
  return [...ts].sort((a, b) => a.seq - b.seq)
})

const current = computed(() => {
  const t = tasks.value.find((x) => x.status !== 'finished' && x.status !== 'failed' && x.status !== 'cancelled')
  return t || tasks.value[tasks.value.length - 1] || null
})

const label = computed(() => {
  const ts = tasks.value
  if (!ts.length) return ''
  const cur = current.value
  if (!cur) return '创作完成'
  const idx = ts.indexOf(cur) + 1
  const role = ROLE_LABELS[cur.agent_type] || cur.agent_type
  if (cur.status === 'awaiting_confirm') return `等你确认 · 第 ${idx}/${ts.length} 步 · ${role}`
  if (cur.status === 'running') return `创作进行中 · 第 ${idx}/${ts.length} 步 · ${role}`
  return `第 ${idx}/${ts.length} 步 · ${role}`
})

// running 时优先用 current_activity.role_line 作短脉搏
function lineOf(t) {
  if (t.status === 'running') return t.current_activity?.role_line || ''
  if (t.status === 'awaiting_confirm') return t.narrative?.awaiting_line || ''
  if (t.status === 'finished') return t.narrative?.done_line || ''
  return ''
}
</script>

<template>
  <div v-if="tasks.length" class="progress-banner">
    <span class="progress-label">{{ label }}</span>
    <div class="progress-segs">
      <div v-for="t in tasks" :key="t.id" class="seg-cell">
        <span class="seg" :class="segState(t.status)" />
        <span class="seg-role">{{ ROLE_LABELS[t.agent_type] || t.agent_type }}</span>
        <span v-if="lineOf(t)" class="seg-line" :class="segState(t.status)">{{ lineOf(t) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.progress-banner {
  width: min(var(--ch-runtime-width), calc(100% - 32px));
  min-height: 38px;
  margin: 2px auto 10px;
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 22px;
  background: #fff;
  border: 1px solid var(--ch-border);
  border-radius: 999px;
  font-size: 12px;
  color: var(--ch-muted);
  flex-shrink: 0;
}
.progress-label {
  white-space: nowrap;
  font-weight: 760;
}
.progress-segs {
  display: flex;
  gap: 12px;
  flex: 1;
  align-items: center;
}
.seg-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}
.seg {
  height: 6px;
  border-radius: 999px;
  background: var(--ch-border);
}
.seg.running {
  background: linear-gradient(90deg, var(--ch-orange-mid), var(--ch-orange));
  animation: pulse 1.4s ease-in-out infinite;
}
.seg.waiting { background: var(--ch-amber); }
.seg.done { background: var(--ch-green-mid); }
.seg.failed { background: #f87171; }
.seg-role {
  display: none;
}
.seg-line {
  display: none;
}
.seg-line.running { color: var(--ch-orange); }
.seg-line.waiting { color: #b45309; }
.seg-line.done { color: #047857; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.58; } }

@media (max-width: 760px) {
  .progress-banner {
    padding: 8px 14px;
  }
  .progress-label {
    display: none;
  }
}
</style>
