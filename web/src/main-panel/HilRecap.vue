<script setup>
import { computed } from 'vue'

const props = defineProps({
  intentState: { type: Object, default: null },
  optionPrompt: { type: Object, default: null },
})

const isOption = computed(() => !!props.optionPrompt)
const optionAnswers = computed(() => {
  const prompt = props.optionPrompt
  return prompt?.answers || []
})
const optionLabel = computed(() => {
  const labels = optionAnswers.value.map((answer) => answer.custom_text || answer.label).filter(Boolean)
  return labels.length ? labels.join('、') : '已补充选择'
})
const intentTitle = computed(() => props.intentState?.topic || '已确认创作意图')
</script>

<template>
  <span class="hil-recap">
    <span class="recap-check" aria-hidden="true">✓</span>
    <span class="recap-label">{{ isOption ? '已选择' : '已确认' }}</span>
    <span class="recap-value">{{ isOption ? optionLabel : intentTitle }}</span>
  </span>
</template>

<style scoped>
.hil-recap {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  max-width: 100%;
  min-height: 26px;
  padding: 4px 9px;
  border: 1px solid color-mix(in srgb, var(--ch-accent) 18%, var(--ch-border));
  border-radius: 999px;
  background: color-mix(in srgb, var(--ch-accent) 5%, var(--ch-surface));
  color: var(--ch-text-muted);
  font-family: var(--ch-font-sans);
  font-size: 12px;
  line-height: 1.25;
}

.recap-check {
  width: 14px;
  height: 14px;
  display: grid;
  flex: 0 0 14px;
  place-items: center;
  border-radius: 50%;
  background: color-mix(in srgb, var(--ch-accent) 18%, transparent);
  color: var(--ch-accent);
  font-size: 10px;
  font-weight: 700;
}

.recap-label { flex: 0 0 auto; }
.recap-value { min-width: 0; overflow: hidden; color: var(--ch-text-secondary); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
</style>
