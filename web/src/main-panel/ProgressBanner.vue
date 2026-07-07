<script setup>
import { computed, onMounted, ref } from 'vue'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'
import { getAgentProfiles } from '../api.js'

function segState(status) {
  if (status === 'finished') return 'done'
  if (status === 'running') return 'running'
  if (status === 'awaiting_confirm') return 'waiting'
  if (status === 'failed' || status === 'cancelled') return 'failed'
  return 'pending'
}

const props = defineProps({ graph: { type: Object, default: null } })

const profiles = ref({})
onMounted(async () => {
  profiles.value = await getAgentProfiles()
})

const tasks = computed(() => props.graph?.tasks || [])

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

function lineOf(t) {
  const nar = t.narrative || {}
  if (t.status === 'running') return profiles.value[t.agent_type]?.enter_line || ''
  if (t.status === 'awaiting_confirm') return nar.awaiting_line || ''
  if (t.status === 'finished') return nar.done_line || ''
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
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--ch-surface);
  border-top: 1px solid var(--ch-border);
  font-size: 13px;
  color: var(--ch-body);
  flex-shrink: 0;
}
.progress-label { white-space: nowrap; }
.progress-segs {
  display: flex;
  gap: 8px;
  flex: 1;
}
.seg-cell {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.seg {
  height: 4px;
  border-radius: 2px;
  background: var(--ch-border);
}
.seg.running {
  background: var(--ch-orange);
  animation: pulse 1.2s ease-in-out infinite;
}
.seg.waiting { background: var(--ch-primary); }
.seg.done { background: var(--ch-green); }
.seg.failed { background: var(--ch-red); }
.seg-role {
  font-size: 12px;
  color: var(--ch-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.seg-line {
  font-size: 11px;
  color: var(--ch-faint);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.seg-line.running { color: var(--ch-orange); }
.seg-line.waiting { color: var(--ch-primary-2); }
.seg-line.done { color: var(--ch-green); }
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
