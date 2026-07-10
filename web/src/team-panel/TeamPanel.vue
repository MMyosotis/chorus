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
        <div class="r-eyebrow">目 录</div>
        <section class="toc-wrap">
          <TocCard
            :tasks="tasks"
            :focused-task-id="focusedTaskId"
            @focus="onFocus"
          />
        </section>
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

.r-eyebrow {
  font-family: var(--ch-serif);
  font-size: 11px;
  font-weight: 600;
  color: var(--ch-faint);
  letter-spacing: 1.4px;
  margin-bottom: 12px;
}

.toc-wrap {
  flex: 0 0 auto;
}

.team-empty {
  color: var(--ch-faint);
  font-size: 13px;
  text-align: center;
  padding: 40px 0 0;
}
</style>
