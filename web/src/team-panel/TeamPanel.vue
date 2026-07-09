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
    <template v-if="hasIntent">
      <div class="team-head">
        <div class="h">意图识别</div>
      </div>
      <IntentStateCard
        :state="intentState"
        :has-active-task="hasActiveTask"
        @stop-and-revise="$emit('stop-and-revise')"
      />
    </template>
    <div v-if="!tasks.length && !hasIntent" class="team-empty">暂无创作任务</div>
    <template v-if="tasks.length">
      <div class="team-head">
        <div class="h">目录</div>
      </div>
      <section class="toc-wrap">
        <TocCard
          :tasks="tasks"
          :focused-task-id="focusedTaskId"
          @focus="onFocus"
        />
      </section>
    </template>
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

/* 意图卡紧跟标题，左右对齐角色列表 */
.team-panel > :deep(.intent-card) {
  flex-shrink: 0;
  margin: 0 14px;
}

.team-head {
  flex-shrink: 0;
  padding: 18px 18px 12px;
}

.team-head .h {
  font-family: var(--ch-serif);
  font-weight: 600;
  font-size: 16px;
  color: var(--ch-text);
  letter-spacing: 0.02em;
}

.team-head .sub {
  font-size: 11.5px;
  color: var(--ch-faint);
  margin-top: 2px;
}

.toc-wrap {
  flex: 1;
  overflow-y: auto;
  padding: 4px 18px 18px;
  scrollbar-width: thin;
}

.team-empty {
  color: var(--ch-faint);
  font-size: 13px;
  text-align: center;
  padding: 40px 0 0;
}
</style>
