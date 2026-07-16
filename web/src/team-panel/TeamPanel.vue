<script setup>
import { computed } from 'vue'

import TocCard from './TocCard.vue'
import IntentStateCard from './IntentStateCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  intentState: { type: Object, default: null },
})
const emit = defineEmits(['focus'])

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
    <div class="editorial-mark" aria-label="稿搭编辑部，第七期">
      <div class="editorial-mark-inner">
        <div class="editorial-mark-dept">
          <strong>稿搭编辑部</strong>
          <span>EDITORIAL DEPT.</span>
        </div>
        <div class="editorial-mark-issue">
          <strong>VOL. 07</strong>
          <span>ISSUE</span>
        </div>
        <div class="editorial-mark-seal" aria-hidden="true"><span>稿</span></div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.team-panel {
  width: var(--ch-rail);
  flex: 0 0 var(--ch-rail);
  border-left: 1px solid rgba(116, 107, 94, 0.34);
  background: var(--ch-team-surface);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.team-body {
  flex: 1;
  width: 100%;
  overflow-y: auto;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  scrollbar-width: thin;
}

.editorial-mark {
  flex: 0 0 68px;
  width: calc(100% - 48px);
  height: 68px;
  margin: 18px 24px 30px;
  padding: 3px;
  border: 2px solid var(--ch-warm);
  color: var(--ch-warm);
}

.editorial-mark-inner {
  height: 58px;
  display: grid;
  grid-template-columns: minmax(88px, 1.7fr) minmax(44px, .82fr) minmax(38px, .72fr);
  border: 1px solid rgba(141, 51, 37, .82);
}

.editorial-mark-dept,
.editorial-mark-issue,
.editorial-mark-seal {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.editorial-mark-dept {
  padding: 7px 4px;
}

.editorial-mark-dept strong {
  white-space: nowrap;
  font: 600 12px/1.3 var(--ch-serif);
  letter-spacing: .08em;
}

.editorial-mark-dept span {
  margin-top: 5px;
  white-space: nowrap;
  font: 500 9px/1.15 var(--ch-serif);
  letter-spacing: .025em;
}

.editorial-mark-issue {
  padding: 7px 4px;
  border-left: 1px solid rgba(141, 51, 37, .72);
}

.editorial-mark-issue strong {
  white-space: nowrap;
  font: 500 9px/1.2 var(--ch-serif);
  letter-spacing: .02em;
}

.editorial-mark-issue span {
  margin-top: 5px;
  font: 500 9px/1.15 var(--ch-serif);
  letter-spacing: .04em;
}

.editorial-mark-seal span {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid var(--ch-warm);
  border-radius: 50%;
  font: 600 19px/1 var(--ch-serif);
}

.team-body :deep(.brief) {
  flex: 0 0 auto;
  margin: 0 0 40px;
  padding: 30px 24px 0;
}

.team-body :deep(.toc-slip) {
  flex: 0 0 auto;
  padding: 30px 24px 24px;
}

.team-body :deep(.brief + .toc-slip) {
  padding-top: 0;
}

.team-empty {
  color: var(--ch-meta);
  font-size: var(--t-meta);
  text-align: center;
  padding: 40px 0 0;
}
</style>
