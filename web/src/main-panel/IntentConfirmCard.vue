<script setup>
const props = defineProps({
  state: { type: Object, default: null },
  busy: { type: Boolean, default: false },
})

defineEmits(['confirm', 'revise'])
</script>

<template>
  <section class="intent-confirm">
    <div class="confirm-head">
      <div>
        <p>意图待确认</p>
        <h3>{{ state?.confirmation_summary?.title || state?.goal || '请确认这次创作方向' }}</h3>
      </div>
      <span>{{ Math.round((state?.confidence || 0) * 100) }}%</span>
    </div>

    <div class="confirm-grid">
      <div
        v-for="item in (state?.confirmation_summary?.items || [])"
        :key="item.label"
        class="confirm-item"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </div>
    </div>

    <div class="confirm-actions">
      <button class="primary" :disabled="busy" @click="$emit('confirm')">
        {{ busy ? '准备中' : '确认并开始' }}
      </button>
      <button class="secondary" :disabled="busy" @click="$emit('revise')">继续调整</button>
    </div>
  </section>
</template>

<style scoped>
.intent-confirm {
  width: min(100%, 640px);
  border: 1px solid #dde5ee;
  border-radius: 8px;
  background: #ffffff;
  padding: 18px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.07);
}

.confirm-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.confirm-head p {
  color: #667085;
  font-size: 12px;
  font-weight: 750;
  margin-bottom: 5px;
}

.confirm-head h3 {
  color: #172033;
  font-size: 18px;
  line-height: 1.35;
  font-weight: 760;
}

.confirm-head > span {
  border-radius: 999px;
  padding: 5px 10px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
  font-weight: 800;
}

.confirm-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-top: 16px;
}

.confirm-item {
  border: 1px solid #e8edf3;
  border-radius: 8px;
  background: #fafbfc;
  padding: 12px;
}

.confirm-item span {
  display: block;
  color: #667085;
  font-size: 12px;
  margin-bottom: 5px;
}

.confirm-item strong {
  color: #172033;
  font-size: 14px;
  line-height: 1.45;
  font-weight: 680;
  overflow-wrap: anywhere;
}

.confirm-actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}

button {
  height: 38px;
  border-radius: 8px;
  padding: 0 16px;
  font-size: 14px;
  font-weight: 760;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.primary {
  border: 1px solid #4338ca;
  background: #4338ca;
  color: #ffffff;
}

.secondary {
  border: 1px solid #dde5ee;
  background: #ffffff;
  color: #344054;
}

@media (max-width: 720px) {
  .confirm-grid {
    grid-template-columns: 1fr;
  }
}
</style>
