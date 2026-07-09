<script setup>
defineProps({
  state: { type: Object, default: null },
})

defineEmits(['confirm', 'revise'])
</script>

<template>
  <section class="intent-confirm">
    <div class="confirm-head">
      <p>意图待确认</p>
      <h3>{{ state?.confirmation_summary?.title || state?.goal || '请确认这次创作方向' }}</h3>
    </div>

    <div v-if="(state?.confirmation_summary?.items || []).length" class="confirm-grid">
      <div
        v-for="item in state.confirmation_summary.items"
        :key="item.label"
        class="confirm-item"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>

    <div class="confirm-actions">
      <button class="primary" @click="$emit('confirm')">确认并开始</button>
      <button class="secondary" @click="$emit('revise')">继续调整</button>
    </div>
  </section>
</template>

<style scoped>
.intent-confirm {
  width: min(100%, 640px);
  border: none;
  border-radius: var(--ch-radius-md);
  background: transparent;
  padding: 18px;
  box-shadow: none;
}

.confirm-head {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.confirm-head p {
  color: var(--ch-muted);
  font-size: 12px;
  font-weight: 600;
}

.confirm-head h3 {
  color: var(--ch-text);
  font-size: 18px;
  line-height: 1.35;
  font-family: var(--ch-serif);
  font-weight: 600;
}

.confirm-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.confirm-item {
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-sm);
  background: var(--ch-bg-cool);
  padding: 12px;
}

.confirm-item span {
  display: block;
  color: var(--ch-muted);
  font-size: 12px;
  margin-bottom: 5px;
}

.confirm-item strong {
  color: var(--ch-text);
  font-size: 14px;
  line-height: 1.45;
  font-weight: 600;
  overflow-wrap: anywhere;
}

.confirm-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

button {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--ch-faint);
}

button:hover:not(:disabled) { text-decoration: underline; }

.primary { color: var(--ch-primary); }

.secondary { color: var(--ch-faint); }

@media (max-width: 720px) {
  .confirm-grid {
    grid-template-columns: 1fr;
  }
}
</style>
