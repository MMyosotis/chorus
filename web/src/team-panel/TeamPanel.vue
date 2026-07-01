<script setup>
import { computed } from 'vue'

import RoleCard from './RoleCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
})
const emit = defineEmits(['focus'])

const tasks = computed(() => props.graph?.tasks || [])

function onFocus(id) {
  emit('focus', id)
}
</script>

<template>
  <aside class="team-panel">
    <div v-if="!tasks.length" class="team-empty">暂无创作任务</div>
    <template v-else>
      <RoleCard
        v-for="t in tasks"
        :key="t.id"
        :task="t"
        :focused="t.id === focusedTaskId"
        @focus="onFocus(t.id)"
      />
    </template>
  </aside>
</template>

<style scoped>
.team-panel {
  width: clamp(290px, 22vw, 340px);
  flex-shrink: 0;
  border: none;
  border-left: 1px solid var(--ch-border);
  border-radius: 0;
  background: var(--ch-team-surface);
  box-shadow: none;
  overflow-y: auto;
  padding: 30px 32px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}
.team-empty {
  color: var(--ch-faint);
  font-size: 13px;
  text-align: center;
  padding: 24px 0;
}
</style>
