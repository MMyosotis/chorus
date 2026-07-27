<script setup>
import { computed } from 'vue'

import AgentAvatar from './AgentAvatar.vue'
import { ROLE_ORDER } from './roleMeta.js'

const props = defineProps({
  tasks: { type: Array, default: () => [] },
})

const members = computed(() => {
  return ROLE_ORDER.map((agentType) => {
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
        <AgentAvatar
          v-for="member in members"
          :key="member.id"
          :agent-type="member.agent_type"
          :status="member.status"
          :inactive="member.inactive"
          :size="32"
        />
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
  gap: 8px;
}
</style>
