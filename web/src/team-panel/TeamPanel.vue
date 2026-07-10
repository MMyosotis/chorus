<script setup>
import { computed } from 'vue'

import TocCard from './TocCard.vue'
import IntentStateCard from './IntentStateCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  intentState: { type: Object, default: null },
  hasActiveTask: { type: Boolean, default: false },
})
const emit = defineEmits(['focus', 'stop-and-revise'])

const tasks = computed(() => props.graph?.tasks || [])
const hasIntent = computed(() => !!props.intentState)

function onFocus(id) {
  emit('focus', id)
}
</script>

<template>
  <aside class="team-panel">
    <div class="team-body">
      <template v-if="hasIntent">
        <IntentStateCard
          :state="intentState"
          :has-active-task="hasActiveTask"
          @stop-and-revise="$emit('stop-and-revise')"
        />
      </template>
      <div v-if="!tasks.length && !hasIntent" class="team-empty">暂无创作任务</div>
      <template v-if="tasks.length">
        <TocCard
          :tasks="tasks"
          :focused-task-id="focusedTaskId"
          @focus="onFocus"
        />
      </template>
    </div>
  </aside>
</template>

<style scoped>
.team-panel {
  width: 280px;
  flex-shrink: 0;
  border-left: 1px solid var(--ch-border);
  background: var(--ch-team-surface);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.team-body {
  flex: 1;
  overflow-y: auto;
  padding: 22px 18px 18px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  scrollbar-width: thin;
}

.team-empty {
  color: var(--ch-faint);
  font-size: 13px;
  text-align: center;
  padding: 40px 0 0;
}
</style>
