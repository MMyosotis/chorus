<script setup>
import { computed } from 'vue'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

// status → 进度条段状态
function segState(status) {
  if (status === 'finished') return 'done'
  if (status === 'running') return 'running'
  if (status === 'awaiting_confirm') return 'waiting'
  if (status === 'failed' || status === 'cancelled') return 'failed'
  return 'pending'
}

const props = defineProps({ graph: { type: Object, default: null } })

const tasks = computed(() => {
  const ts = props.graph?.tasks || []
  return [...ts].sort((a, b) => a.seq - b.seq)
})

const current = computed(() => {
  // 当前步 = 第一个非终态（running/awaiting_confirm/pending），否则末步
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
</script>

<template>
  <div v-if="tasks.length" class="progress-banner">
    <span class="progress-label">{{ label }}</span>
    <div class="progress-segs">
      <span
        v-for="t in tasks"
        :key="t.id"
        class="seg"
        :class="segState(t.status)"
        :title="ROLE_LABELS[t.agent_type] || t.agent_type"
      />
    </div>
  </div>
</template>

<style scoped>
.progress-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: rgba(255, 255, 255, 0.6);
  border-top: 1px solid rgba(226, 232, 240, 0.5);
  font-size: 13px;
  color: #475569;
  flex-shrink: 0;
}
.progress-label {
  white-space: nowrap;
}
.progress-segs {
  display: flex;
  gap: 4px;
  flex: 1;
}
.seg {
  flex: 1;
  height: 4px;
  border-radius: 2px;
  background: #e2e8f0;
}
.seg.running {
  background: linear-gradient(90deg, #818cf8, #6366f1);
  animation: pulse 1.2s ease-in-out infinite;
}
.seg.waiting { background: #fbbf24; }
.seg.done { background: #34d399; }
.seg.failed { background: #f87171; }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
