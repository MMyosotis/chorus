<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'

import AgentAvatar from './AgentAvatar.vue'
import { ROLE_LABELS, badgeOf } from './roleMeta.js'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
})
defineEmits(['view-logs'])

const DEFAULT_MEMBERS = [
  { id: 'standby-idea', agent_type: 'idea', status: 'pending', placeholder: true },
  { id: 'standby-script', agent_type: 'script', status: 'pending', placeholder: true },
  { id: 'standby-image', agent_type: 'image', status: 'pending', placeholder: true },
  { id: 'standby-finalize', agent_type: 'finalize', status: 'pending', placeholder: true },
]

const members = computed(() => {
  const seen = new Set()
  const active = props.tasks.filter((task) => {
    if (!task.agent_type || seen.has(task.agent_type)) return false
    seen.add(task.agent_type)
    return true
  })
  return active.length ? active : DEFAULT_MEMBERS
})

const counts = computed(() => {
  const c = { running: 0, awaiting: 0, finished: 0, failed: 0 }
  for (const task of props.tasks) {
    if (task.status === 'running') c.running++
    else if (task.status === 'awaiting_confirm') c.awaiting++
    else if (task.status === 'finished') c.finished++
    else if (task.status === 'failed') c.failed++
  }
  return c
})

const summaryPhrase = computed(() => {
  const c = counts.value
  if (!props.tasks.length) return '等待开始'
  const parts = []
  if (c.running) parts.push(`${c.running} 人工作中`)
  if (c.awaiting) parts.push(`${c.awaiting} 项待确认`)
  if (c.failed) parts.push(`${c.failed} 项失败`)
  if (parts.length) return parts.join(' · ')
  return c.finished ? '全部完成' : '等待开始'
})

const now = ref(Date.now())
let timer = null
function startTick() {
  if (timer) return
  timer = setInterval(() => { now.value = Date.now() }, 1000)
}
function stopTick() {
  if (timer) { clearInterval(timer); timer = null }
}
watch(() => counts.value.running > 0, (active) => (active ? startTick() : stopTick()), { immediate: true })
onUnmounted(stopTick)

const elapsedText = computed(() => {
  let earliest = null
  for (const task of props.tasks) {
    if (task.status !== 'running') continue
    const started = task.progress && task.progress.activity_started_at
    if (started && (earliest === null || started < earliest)) earliest = started
  }
  if (earliest === null) return ''
  const seconds = Math.max(0, Math.floor(now.value / 1000 - earliest))
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m >= 60) return `已用 ${Math.floor(m / 60)} 时 ${m % 60} 分`
  if (m > 0) return `已用 ${m} 分 ${s.toString().padStart(2, '0')} 秒`
  return `已用 ${s} 秒`
})

const expanded = ref(false)
</script>

<template>
  <section class="pipeline-card" aria-labelledby="pipeline-title">
    <header class="pipeline-head">
      <h2 id="pipeline-title">团队进展</h2>
      <button type="button" class="logs-link" @click="$emit('view-logs')">查看原始日志</button>
    </header>

    <div class="team-compact">
      <div class="avatar-group">
        <AgentAvatar
          v-for="member in members"
          :key="member.id"
          :agent-type="member.agent_type"
          :status="member.status"
          :standby="member.placeholder"
          :size="32"
        />
      </div>
      <p class="team-summary">
        <span class="summary-dot" aria-hidden="true"></span>
        <span class="summary-phrase">{{ summaryPhrase }}</span>
        <span v-if="elapsedText" class="summary-elapsed">{{ elapsedText }}</span>
      </p>
    </div>

    <button type="button" class="expand-toggle" :aria-expanded="expanded" @click="expanded = !expanded">
      {{ expanded ? '收起详情' : '展开详情' }}
      <svg class="chevron" :class="{ up: expanded }" viewBox="0 0 24 24" aria-hidden="true">
        <path d="m6 9 6 6 6-6" />
      </svg>
    </button>

    <ol v-if="expanded" class="pipeline">
      <li
        v-for="member in members"
        :key="member.id"
        class="stage"
        :class="[badgeOf(member.status).cls, { standby: member.placeholder }]"
      >
        <span class="stage-marker">
          <AgentAvatar :agent-type="member.agent_type" :status="member.status" :standby="member.placeholder" :size="36" />
        </span>
        <span class="stage-name">{{ ROLE_LABELS[member.agent_type] }}</span>
        <span class="stage-status">
          <i class="stage-dot" aria-hidden="true"></i>{{ badgeOf(member.status).label }}
        </span>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.pipeline-card {
  padding: var(--ch-space-4);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.pipeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ch-space-2);
}

.pipeline-head h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 24px;
  white-space: nowrap;
}

.logs-link {
  padding: 0;
  border: none;
  background: none;
  color: var(--ch-text-muted);
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  cursor: pointer;
  transition: color .2s ease-out;
}

.logs-link:hover { color: var(--ch-accent); }

.team-compact {
  margin-top: var(--ch-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--ch-space-2);
}

.avatar-group {
  display: flex;
  gap: 8px;
}

.team-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  color: var(--ch-text-secondary);
  font-size: 13px;
  font-weight: 500;
  line-height: 20px;
}

.summary-dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
  background: var(--ch-text-muted);
}

.summary-phrase {
  color: var(--ch-text);
}

.summary-elapsed {
  margin-left: 4px;
  color: var(--ch-text-muted);
  font-variant-numeric: tabular-nums;
}

.expand-toggle {
  margin-top: var(--ch-space-3);
  padding: 0;
  border: none;
  background: none;
  color: var(--ch-text-muted);
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: color .2s ease-out;
}

.expand-toggle:hover { color: var(--ch-text); }

.chevron {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
  transition: transform .2s ease-out;
}

.chevron.up { transform: rotate(180deg); }

.pipeline {
  display: flex;
  flex-direction: column;
  gap: var(--ch-space-2);
  margin: var(--ch-space-3) 0 0;
  padding: 0;
  list-style: none;
}

.stage {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--ch-space-3);
  min-height: 36px;
}

.stage-marker { display: grid; place-items: center; }

.stage-name {
  min-width: 0;
  overflow: hidden;
  color: var(--ch-text);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.stage-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 24px;
  padding: 0 8px;
  border-radius: var(--ch-radius-pill);
  background: var(--ch-surface-3);
  color: var(--ch-text-muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
}

.stage-dot {
  width: 6px;
  height: 6px;
  flex: 0 0 6px;
  border-radius: 50%;
  background: currentColor;
}

.stage.running .stage-status {
  background: var(--ch-accent-soft);
  color: var(--ch-accent-soft-text);
}

.stage.running .stage-dot { animation: stagePulse 1.7s ease-in-out infinite; }

.stage.waiting .stage-status {
  background: var(--ch-warning-soft);
  color: var(--ch-warning-text);
}

.stage.done .stage-status {
  background: var(--ch-success-soft);
  color: var(--ch-success-text);
}

.stage.failed .stage-status {
  background: var(--ch-danger-soft);
  color: var(--ch-danger-text);
}

.stage.cancelled .stage-status {
  background: var(--ch-surface-3);
  color: var(--ch-text-faint);
}

.stage.standby .stage-name { color: var(--ch-text-muted); }

@keyframes stagePulse {
  0%, 100% { opacity: .35; }
  50% { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .stage.running .stage-dot,
  .chevron { animation: none; transition: none; }
}
</style>
