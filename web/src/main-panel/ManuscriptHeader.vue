<script setup>
defineProps({
  date: { type: String, required: true },
  page: { type: String, required: true },
  kicker: { type: String, required: true },
  title: { type: String, required: true },
  deck: { type: String, required: true },
})
</script>

<template>
  <header class="workspace-header">
    <div class="workspace-identity">
      <span class="brand-mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z"/><path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14z"/></svg>
      </span>
      <div>
        <span class="workspace-label">AI 创作工作台</span>
        <h1>{{ title }}</h1>
      </div>
    </div>
    <div class="workspace-state">
      <span class="state-dot"></span>
      <span>{{ kicker }}</span>
      <span class="state-page">{{ page }}</span>
    </div>
  </header>
</template>

<style scoped>
.workspace-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  min-height: 80px;
  flex-shrink: 0;
  margin: -24px calc(-1 * var(--ch-paper-pad)) 0;
  padding: 16px 24px;
  border: 0;
  background: transparent;
  color: var(--ch-text);
}
.workspace-identity {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 16px;
}
.brand-mark {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--ch-accent-gradient);
  box-shadow: 0 8px 20px rgba(99, 102, 241, .22);
}
.brand-mark svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: var(--ch-on-accent);
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.workspace-label {
  display: block;
  margin-bottom: 4px;
  color: var(--ch-text-secondary);
  font: 500 var(--ch-text-xs)/1.5 var(--ch-font-sans);
  letter-spacing: 0.02em;
}
.workspace-identity h1 {
  max-width: 560px;
  margin: 0;
  overflow: hidden;
  color: var(--ch-text);
  font: 600 var(--ch-text-lg)/1.3 var(--ch-font-sans);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workspace-state {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 0 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-pill);
  background: var(--ch-surface-2);
  color: var(--ch-text-secondary);
  font: 500 var(--ch-text-xs)/1 var(--ch-font-sans);
}
.state-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ch-accent);
  box-shadow: 0 0 0 4px var(--ch-accent-soft);
}
.state-page {
  min-width: 24px;
  padding-left: 8px;
  border-left: 1px solid var(--ch-border);
  color: var(--ch-text);
  text-align: right;
  font-variant-numeric: tabular-nums;
}
@media (max-width: 780px) {
  .workspace-header { min-height: 64px; padding-inline: 16px; }
  .workspace-state { display: none; }
  .brand-mark { width: 32px; height: 32px; flex-basis: 32px; }
  .brand-mark svg { width: 16px; height: 16px; }
}
</style>
