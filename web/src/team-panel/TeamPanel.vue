<script setup>
import { computed } from 'vue'

import IntentStateCard from './IntentStateCard.vue'
import PipelineTimeline from './PipelineTimeline.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  intentState: { type: Object, default: null },
})

const tasks = computed(() => props.graph?.tasks || [])
</script>

<template>
  <aside class="team-panel" aria-label="意图与团队">
    <div class="team-body">
      <div class="team-surface">
        <header class="board-header">
          <h1>工作展板</h1>
        </header>
        <div class="section-divider" aria-hidden="true"></div>
        <IntentStateCard :state="intentState" />
        <div class="section-divider" aria-hidden="true"></div>
        <PipelineTimeline
          :tasks="tasks"
          :intent-state="intentState"
        />
      </div>
    </div>
  </aside>
</template>

<style scoped>
.team-panel {
  width: var(--ch-right-rail);
  height: 100%;
  display: flex;
  flex: 0 0 var(--ch-right-rail);
  flex-direction: column;
  overflow: visible;
  border-left: 0;
  background: transparent;
}

.team-body {
  width: 100%;
  min-height: 0;
  flex: 1;
  overflow: visible;
  padding: var(--ch-space-2) var(--ch-space-2) var(--ch-space-5);
}

.team-surface {
  height: calc(100dvh - 48px);
  min-height: calc(100dvh - 48px);
  overflow-x: hidden;
  overflow-y: auto;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-panel);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-md);
  scrollbar-color: var(--ch-border-strong) transparent;
  scrollbar-width: thin;
}

.board-header {
  padding: var(--ch-space-4) var(--ch-space-4) var(--ch-space-3);
  font-family: var(--ch-font-sans);
}

.board-header h1 {
  margin: 0;
  color: var(--ch-text);
  font-size: 24px;
  font-weight: 600;
  line-height: 32px;
}

.section-divider {
  height: 1px;
  margin: 0 var(--ch-space-4);
  background: var(--ch-border);
}
</style>
