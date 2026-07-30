<script setup>
import { computed } from 'vue'

import AgentAvatar from './AgentAvatar.vue'
import { ROLE_LABELS, ROLE_ORDER } from './roleMeta.js'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
  chiefWorking: { type: Boolean, default: false },
})

const members = computed(() => {
  return ['chief', ...ROLE_ORDER].map((agentType) => {
    if (agentType === 'chief') {
      return {
        id: 'chief',
        agent_type: agentType,
        status: props.chiefWorking ? 'running' : 'finished',
        inactive: false,
      }
    }
    const assigned = props.tasks.filter((task) => task.agent_type === agentType)
    const task = assigned.find((item) => item.status === 'running') || assigned.at(-1)
    return {
      id: task?.id || `inactive-${agentType}`,
      agent_type: agentType,
      status: task?.status || 'pending',
      inactive: !task,
    }
  })
})
</script>

<template>
  <section class="pipeline-card" aria-labelledby="pipeline-title">
    <header class="pipeline-head">
      <h2 id="pipeline-title">团队成员</h2>
    </header>

    <div class="team-compact">
      <div class="avatar-group">
        <div v-for="member in members" :key="member.id" class="team-member">
          <AgentAvatar
            :agent-type="member.agent_type"
            :status="member.status"
            :inactive="member.inactive"
            :size="40"
          />
          <span>{{ ROLE_LABELS[member.agent_type] }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.pipeline-card {
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
  color: var(--ch-ink);
  font-size: 18px;
  font-weight: 600;
  line-height: 24px;
  white-space: nowrap;
}

.team-compact {
  margin-top: var(--ch-space-3);
}

.avatar-group {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.team-member {
  display: grid;
  min-width: 40px;
  justify-items: center;
  gap: 8px;
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 16px;
  white-space: nowrap;
}

</style>
