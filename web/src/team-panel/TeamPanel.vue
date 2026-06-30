<script setup>
import { computed } from 'vue'

import RoleCard from './RoleCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
})
const emit = defineEmits(['focus'])

const tasks = computed(() => {
  const ts = props.graph?.tasks || []
  return [...ts].sort((a, b) => a.seq - b.seq)
})

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
  width: 260px;
  flex-shrink: 0;
  border-left: 1px solid rgba(226, 232, 240, 0.55);
  background: rgba(255, 255, 255, 0.5);
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.team-empty {
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
  padding: 24px 0;
}
</style>
