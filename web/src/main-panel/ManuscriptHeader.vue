<script setup>
defineProps({
  kicker: { type: String, required: true },
  title: { type: String, required: true },
})
</script>

<template>
  <header class="workspace-header">
    <div class="workspace-identity">
      <h1>{{ title }}</h1>
    </div>
    <div v-if="kicker" class="workspace-state">
      <span class="state-dot"></span>
      <span class="state-text">{{ kicker }}</span>
    </div>
  </header>
</template>

<style scoped>
.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  min-height: 56px;
  flex-shrink: 0;
  margin: 0 0 40px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ch-text);
}
.workspace-identity {
  min-width: 0;
}
.workspace-identity h1 {
  max-width: 560px;
  margin: 0;
  overflow: hidden;
  color: var(--ch-text);
  font: 600 var(--ch-text-xl)/1.3 var(--ch-font-sans);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace-state {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 35px;
  padding: 0 15px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-pill);
  background: var(--ch-surface);
  color: var(--ch-text-secondary);
  font: 500 13px/1 var(--ch-font-sans);
  box-shadow: var(--ch-shadow-xs);
}
.state-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ch-accent);
  box-shadow: 0 0 0 5px var(--ch-accent-soft);
}
.state-text {
  letter-spacing: 0.01em;
}
@media (max-width: 780px) {
  .workspace-header { min-height: 52px; padding-inline: 16px; margin-bottom: 24px; }
  .workspace-state { display: none; }
}
</style>
