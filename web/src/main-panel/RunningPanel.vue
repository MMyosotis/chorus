<script setup>
import { computed } from 'vue'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({ task: { type: Object, required: true } })

const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
function toCN(n) {
  if (n <= 10) return CN_NUM[n]
  if (n < 20) return '十' + (n % 10 ? CN_NUM[n % 10] : '')
  return String(n)
}
const role = computed(() => ROLE_LABELS[props.task.agent_type] || props.task.agent_type)
const prog = computed(() => props.task.progress || {})
const aside = computed(() => prog.value.aside || '')
const chars = computed(() => prog.value.composing_chars || 0)
const units = computed(() => prog.value.composing_units || 0)
const label = computed(() => prog.value.composing_label || '')
const signal = computed(() => prog.value.last_signal || '')
</script>

<template>
  <div class="running">
    <div class="scene-mark">{{ role }}</div>
    <div v-if="signal" class="signal"><span class="dot"></span>{{ signal }}</div>
    <div class="prog-main">{{ aside || '正在创作' }}</div>
    <div v-if="chars || units" class="prog-units">
      <span v-if="units">已{{ toCN(units) }}{{ label }}</span>
      <span v-if="units && chars" class="sep">·</span>
      <span v-if="chars">写下 {{ toCN(chars) }} 字</span>
    </div>
  </div>
</template>

<style scoped>
.running { font-family: var(--ch-serif); }
.scene-mark { font-size: 12px; color: var(--ch-faint); letter-spacing: 1px; margin-bottom: 16px; }
.signal { font-size: 13px; color: var(--ch-orange-2); margin-bottom: 12px; display: flex; align-items: center; gap: 8px; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: var(--ch-orange); animation: pulse 1.4s ease-in-out infinite; }
.prog-main { font-size: 15px; line-height: 1.8; color: var(--ch-text); margin-bottom: 10px; }
.prog-units { font-size: 12px; color: var(--ch-faint); display: flex; gap: 10px; }
.sep { color: var(--ch-border-2); }
@keyframes pulse {
  0%, 100% { opacity: .55; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.15); }
}
</style>
