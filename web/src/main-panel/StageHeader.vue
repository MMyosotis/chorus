<script setup>
defineProps({
  number: { type: String, required: true },
  title: { type: String, required: true },
  english: { type: String, required: true },
  status: { type: String, default: '' },
  statusTone: { type: String, default: 'warm' },
})
</script>

<template>
  <header class="stage-header">
    <span class="stage-number">{{ number }}</span>
    <span class="stage-title">
      <strong>{{ title }}</strong>
      <small>{{ english }}</small>
    </span>
    <span v-if="status" class="stage-status" :data-tone="statusTone">{{ status }}</span>
  </header>
</template>

<style scoped>
.stage-header {
  height: auto;
  min-height: var(--ch-stage-head-height);
  box-sizing: border-box;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 5px 0 14px;
  border: 0;
}

.stage-number {
  align-self: center;
  color: var(--ch-warm);
  font: 600 23px/1 var(--ch-serif);
  font-variant-numeric: lining-nums tabular-nums;
}

.stage-title {
  min-width: 0;
  height: var(--ch-stage-title-height);
  display: grid;
  grid-template-rows: var(--ch-stage-title-cn-line) var(--ch-stage-title-en-line);
  gap: 2px;
  align-content: start;
}

.stage-title strong {
  overflow: hidden;
  color: var(--ch-text);
  font: 600 var(--ch-chat-title-size)/var(--ch-stage-title-cn-line) var(--ch-serif);
  letter-spacing: .025em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-title small {
  overflow: hidden;
  color: var(--ch-muted);
  font: 600 var(--ch-chat-meta-size)/var(--ch-stage-title-en-line) var(--ch-sans);
  letter-spacing: .13em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.stage-status {
  align-self: end;
  color: var(--ch-warm);
  font: 600 var(--ch-chat-label-size)/1 var(--ch-serif);
  letter-spacing: .04em;
  white-space: nowrap;
}

.stage-status[data-tone="primary"] { color: var(--ch-primary); }
.stage-status[data-tone="danger"] { color: var(--ch-red); }

</style>
