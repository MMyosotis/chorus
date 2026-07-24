<script setup>
import { computed } from 'vue'

import IntentStateCard from './IntentStateCard.vue'
import PipelineTimeline from './PipelineTimeline.vue'
import ArtifactsCard from './ArtifactsCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  intentState: { type: Object, default: null },
})
defineEmits(['view-logs', 'preview-task'])

const tasks = computed(() => props.graph?.tasks || [])
</script>

<template>
  <aside class="team-panel" aria-label="意图与团队">
    <div class="team-body">
      <div class="team-surface">
        <IntentStateCard :state="intentState" />
        <div class="section-divider" aria-hidden="true"></div>
        <PipelineTimeline :tasks="tasks" @view-logs="$emit('view-logs')" />
        <div class="section-divider" aria-hidden="true"></div>
        <ArtifactsCard :tasks="tasks" @preview-task="$emit('preview-task')" />
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
  border-radius: var(--ch-radius-xl);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-md);
  scrollbar-color: var(--ch-border-strong) transparent;
  scrollbar-width: thin;
}

.section-divider {
  height: 1px;
  margin: 0 var(--ch-space-4);
  background: var(--ch-border);
}
</style>
