<script setup>
import { ref, watch } from 'vue'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const FINISH_WRAP_MS = 1200
const FINISH_HOLD_MS = 1500

const props = defineProps({
  task: { type: Object, required: true },
})
const emit = defineEmits(['done'])

const phase = ref('idle')

watch(() => props.task?.status, (s) => {
  // 仅 finalize finished 触发；cancelled/failed 不触发
  if (s === 'finished' && props.task.agent_type === 'finalize' && phase.value === 'idle') {
    phase.value = 'wrapping'
    setTimeout(() => {
      phase.value = 'done'
      emit('done', props.task.id)
      // "创作完成"短暂停留后退场，不常驻占位
      setTimeout(() => { phase.value = 'idle' }, FINISH_HOLD_MS)
    }, FINISH_WRAP_MS)
  }
}, { immediate: true })
</script>

<template>
  <div v-if="phase !== 'idle'" class="finish-wrap" :class="phase">
    <div class="fw-icon">✓</div>
    <div class="fw-text">{{ phase === 'wrapping' ? '正在汇总成品…' : '创作完成' }}</div>
  </div>
</template>

<style scoped>
.finish-wrap { display: flex; align-items: center; gap: 12px; justify-content: center;
  padding: 20px 24px; background: var(--ch-green-soft);
  border: 1px solid color-mix(in srgb, var(--ch-green) 30%, var(--ch-border)); margin: 0; }
.fw-icon { width: 36px; height: 36px; border-radius: 50%; background: var(--ch-green); color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 20px; }
.fw-text { font-size: var(--t-body); color: var(--ch-green); font-family: var(--ch-serif); font-weight: 600; }
.finish-wrap.wrapping .fw-icon { animation: pop 0.4s ease; }
@keyframes pop { 0% { transform: scale(0.5); opacity: 0; } 100% { transform: scale(1); opacity: 1; } }
</style>
