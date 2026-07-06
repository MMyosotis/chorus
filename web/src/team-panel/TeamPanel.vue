<script setup>
import { computed } from 'vue'

import IntentStateCard from './IntentStateCard.vue'
import RoleCard from './RoleCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  intentState: { type: Object, default: null },
  hasActiveTask: { type: Boolean, default: false },
})
const emit = defineEmits(['focus', 'intent-confirm', 'intent-revise', 'intent-stop-and-revise'])

const tasks = computed(() => props.graph?.tasks || [])

function onFocus(id) {
  emit('focus', id)
}
</script>

<template>
  <aside class="team-panel">
    <IntentStateCard
      :state="intentState"
      :has-active-task="hasActiveTask"
      @confirm="$emit('intent-confirm')"
      @revise="$emit('intent-revise')"
      @stop-and-revise="$emit('intent-stop-and-revise')"
    />
    <div v-if="!tasks.length" class="team-empty">任务团队将在确认意图后启动</div>
    <section v-else class="role-section">
      <div class="section-title">执行团队</div>
      <RoleCard
        v-for="t in tasks"
        :key="t.id"
        :task="t"
        :focused="t.id === focusedTaskId"
        @focus="onFocus(t.id)"
      />
    </section>
  </aside>
</template>

<style scoped>
.team-panel {
  width: clamp(320px, 24vw, 380px);
  flex-shrink: 0;
  border: none;
  border-left: 1px solid var(--ch-border);
  border-radius: 0;
  background: var(--ch-team-surface);
  box-shadow: none;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: 100%;
}
.role-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-title {
  color: var(--ch-muted);
  font-size: 12px;
  font-weight: 760;
}
.team-empty {
  color: var(--ch-faint);
  font-size: 13px;
  text-align: left;
  padding: 8px 2px;
}
</style>
