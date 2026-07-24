<script setup>
import { computed } from 'vue'

import AgentAvatar from './AgentAvatar.vue'
import { ROLE_LABELS, ROLE_ORDER, badgeOf } from './roleMeta.js'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  intentState: { type: Object, default: null },
})

const DEFAULT_MEMBERS = ROLE_ORDER.map((agentType) => ({
  id: `standby-${agentType}`,
  agent_type: agentType,
  status: 'pending',
  placeholder: true,
}))

const members = computed(() => {
  const seen = new Set()
  const activeMembers = props.tasks.filter((task) => {
    if (!task.agent_type || seen.has(task.agent_type)) return false
    seen.add(task.agent_type)
    return true
  })
  const intentStatus = props.intentState?.intent_status || 'empty'
  const chiefEditor = {
    id: 'chief-editor',
    agent_type: 'chief',
    status: ['empty', 'capturing', 'needs_clarification', 'ready_to_confirm'].includes(intentStatus)
      ? 'running'
      : 'finished',
    placeholder: false,
  }
  return [chiefEditor, ...(activeMembers.length ? activeMembers : DEFAULT_MEMBERS)]
})
</script>

<template>
  <section class="pipeline-card" aria-labelledby="pipeline-title">
    <header class="pipeline-head">
      <h2 id="pipeline-title">团队进展</h2>
    </header>

    <ol class="pipeline">
      <li
        v-for="member in members"
        :key="member.id"
        class="stage"
        :class="[badgeOf(member.status).cls, { standby: member.placeholder }]"
      >
        <span class="stage-marker">
          <AgentAvatar
            :agent-type="member.agent_type"
            :status="member.status"
            :standby="member.placeholder"
            :size="40"
          />
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
  margin-bottom: var(--ch-space-3);
}

.pipeline-head h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 24px;
  white-space: nowrap;
}

.pipeline {
  display: flex;
  flex-direction: column;
  gap: var(--ch-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.stage {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--ch-space-3);
  min-height: 40px;
}

.stage-marker {
  display: grid;
  place-items: center;
}

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

.stage.running .stage-dot {
  animation: stagePulse 1.7s ease-in-out infinite;
}

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

.stage.standby .stage-name {
  color: var(--ch-text-muted);
}

@keyframes stagePulse {
  0%, 100% { opacity: .35; }
  50% { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .stage.running .stage-dot { animation: none; }
}
</style>
