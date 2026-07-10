<script setup>
defineProps({
  state: { type: Object, default: null },
})

defineEmits(['confirm', 'revise'])
</script>

<template>
  <section class="intent-confirm">
    <div class="confirm-title">
      {{ state?.confirmation_summary?.title || state?.goal || '请确认这次创作方向' }}
    </div>
    <div v-if="(state?.confirmation_summary?.items || []).length" class="confirm-items">
      <template v-for="(item, idx) in state.confirmation_summary.items" :key="idx">
        <span class="label">{{ item.label }}</span>
        <span class="value">{{ item.value }}</span>
      </template>
    </div>
    <div class="confirm-actions">
      <button class="primary" @click="$emit('confirm')">确认并开始</button>
      <span class="gap">·</span>
      <button class="secondary" @click="$emit('revise')">继续调整</button>
    </div>
  </section>
</template>

<style scoped>
.intent-confirm {
  width: 100%;
  border: none;
  background: transparent;
  padding: 0;
}

.confirm-title {
  font-family: var(--ch-serif);
  font-size: 16px;
  font-weight: 600;
  color: var(--ch-text);
  line-height: 1.5;
  margin-bottom: 14px;
}

.confirm-items {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 12px;
  row-gap: 9px;
  font-size: 13px;
  margin-bottom: 18px;
}

.confirm-items .label {
  color: var(--ch-faint);
  font-size: 11px;
  letter-spacing: 0.5px;
  align-self: center;
}

.confirm-items .value {
  color: var(--ch-body);
  font-family: var(--ch-serif);
}

.confirm-actions {
  display: flex;
  align-items: center;
  font-family: var(--ch-serif);
  font-size: 13.5px;
}

.confirm-actions button {
  background: transparent;
  border: none;
  border-bottom: 1px solid transparent;
  cursor: pointer;
  padding: 4px 2px;
  font-family: inherit;
  font-size: inherit;
}

.confirm-actions .primary {
  color: var(--ch-primary-2);
  font-weight: 600;
}

.confirm-actions .primary:hover {
  border-bottom-color: var(--ch-primary);
}

.confirm-actions .secondary {
  color: var(--ch-muted);
}

.confirm-actions .secondary:hover {
  border-bottom-color: var(--ch-border-2);
}

.confirm-actions .gap {
  color: var(--ch-border-2);
  margin: 0 6px;
}
</style>
