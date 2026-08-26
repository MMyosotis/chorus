<script setup>
import { computed } from 'vue'
import AgentAvatar from '../team-panel/AgentAvatar.vue'
import { ROLE_FULL } from '../team-panel/roleMeta.js'
import HilCard from './HilCard.vue'

const props = defineProps({ task: { type: Object, required: true } })
const emit = defineEmits(['preview-task'])

const agentType = computed(() => props.task.agent_type)
const roleLabel = computed(() => ROLE_FULL[agentType.value] || agentType.value)
</script>

<template>
  <section class="confirmed-card">
    <header class="turn-head">
      <AgentAvatar :agent-type="agentType" status="finished" :size="40" />
      <span class="role">{{ roleLabel }}</span>
    </header>
    <HilCard :task="task" confirmed @preview-task="emit('preview-task', $event)" />
  </section>
</template>

<style scoped>
.confirmed-card {
  width: 100%;
}

.turn-head {
  display: flex;
  min-height: 32px;
  align-items: center;
  gap: var(--ch-space-2);
  margin-bottom: var(--ch-space-3);
}

.turn-head :deep(.agent-avatar) {
  box-shadow: var(--ch-shadow-bubble);
}

.turn-head .role {
  color: var(--ch-text);
  font: 500 16px/1 var(--ch-font-sans);
  letter-spacing: 0;
}

.confirmed-card :deep(.hil-card) {
  margin: 0;
}
</style>
