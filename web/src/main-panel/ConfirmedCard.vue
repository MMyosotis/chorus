<script setup>
import { computed } from 'vue'
import AgentAvatar from '../team-panel/AgentAvatar.vue'
import { ROLE_FULL } from '../team-panel/roleMeta.js'
import HilCard from './HilCard.vue'

const props = defineProps({ task: { type: Object, required: true } })

const agentType = computed(() => props.task.agent_type)
const roleLabel = computed(() => ROLE_FULL[agentType.value] || agentType.value)
</script>

<template>
  <section class="confirmed-card">
    <header class="turn-head">
      <AgentAvatar :agent-type="agentType" status="finished" :size="34" />
      <span class="role">{{ roleLabel }} AI</span>
    </header>
    <HilCard :task="task" confirmed />
  </section>
</template>

<style scoped>
.confirmed-card {
  width: 100%;
}

.turn-head {
  display: flex;
  min-height: 34px;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.turn-head :deep(.agent-avatar) {
  border-color: var(--ch-ink);
  background: var(--ch-ink);
  box-shadow: var(--ch-shadow-bubble);
  color: var(--ch-on-ink);
}

.turn-head .role {
  color: var(--ch-text);
  font: 500 14px/1 var(--ch-font-sans);
  letter-spacing: 0;
}

.confirmed-card :deep(.hil-card) {
  margin: 0;
}
</style>
