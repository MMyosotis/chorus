<script setup>
import { computed } from 'vue'

import IntentStateCard from './IntentStateCard.vue'
import PipelineTimeline from './PipelineTimeline.vue'
import ArtifactsCard from './ArtifactsCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  chiefWorking: { type: Boolean, default: false },
  focusedTaskId: { type: String, default: null },
  intentState: { type: Object, default: null },
})
defineEmits(['focus-task'])

const tasks = computed(() => props.graph?.tasks || [])
</script>

<template>
  <aside class="team-panel" aria-label="意图与团队">
    <div class="team-body">
      <div class="team-surface">
        <div class="right-title">工作展板</div>
        <div class="section-divider" aria-hidden="true"></div>
        <IntentStateCard :state="intentState" />
        <div class="section-divider" aria-hidden="true"></div>
        <PipelineTimeline :tasks="tasks" :chief-working="chiefWorking" />
        <div class="section-divider" aria-hidden="true"></div>
        <ArtifactsCard :tasks="tasks" @focus-task="$emit('focus-task', $event)" />
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
  display: flex;
  flex-direction: column;
  overflow: visible;
  padding: 24px var(--ch-space-3) 24px 0;
}

.team-surface {
  flex: 1;
  min-height: 0;
  padding: var(--ch-panel-padding);
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: none;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-xl);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-team);
}

.team-surface::-webkit-scrollbar {
  display: none;
}

.right-title {
  color: var(--ch-ink);
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-lg);
  font-weight: var(--ch-font-semibold);
  line-height: 1.4;
}

.section-divider {
  height: 1px;
  margin: 24px 0;
  background: var(--ch-border);
}
</style>
