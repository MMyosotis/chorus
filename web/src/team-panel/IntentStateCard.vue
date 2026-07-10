<script setup>
import { computed } from 'vue'

const props = defineProps({
  state: { type: Object, default: null },
  hasActiveTask: { type: Boolean, default: false },
})

defineEmits(['stop-and-revise'])

const status = computed(() => props.state?.intent_status || 'empty')
const goal = computed(() => props.state?.goal || '')

const knownEntries = computed(() => {
  const slots = props.state?.known_slots || {}
  return Object.entries(slots)
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
    .slice(0, 8)
})
const missing = computed(() => props.state?.missing_slots || [])
const summaryTitle = computed(() => props.state?.confirmation_summary?.title || goal.value || '正在理解你的需求')

const progress = computed(() => ({
  empty: 0,
  capturing: 28,
  needs_clarification: 56,
  ready_to_confirm: 86,
}[status.value] ?? 100))

// 脚手架态：识别中 / 待补充
const scaffold = computed(() =>
  status.value === 'capturing' || status.value === 'needs_clarification'
)
// 题旨态：已确认 / 执行中（详情在此展示）
const brief = computed(() =>
  status.value === 'confirmed' || status.value === 'dispatched'
)
// 待确认：中间已有确认单，右栏只作等待提示
const awaiting = computed(() => status.value === 'ready_to_confirm')
const showStop = computed(() => props.hasActiveTask && status.value === 'dispatched')
</script>

<template>
  <!-- 脚手架态：意图识别中 / 待补充 -->
  <section v-if="scaffold" class="intent-scaffold">
    <div class="r-eyebrow">意 图</div>
    <div class="intent-goal">{{ summaryTitle }}</div>
    <div class="progress-track"><i :style="{ width: `${progress}%` }"></i></div>

    <div v-if="knownEntries.length" class="sec-title">已识别</div>
    <div v-if="knownEntries.length" class="slots">
      <template v-for="[key, value] in knownEntries" :key="key">
        <span class="sk">{{ key }}</span>
        <span class="sv">{{ Array.isArray(value) ? value.join('、') : value }}</span>
      </template>
    </div>

    <div v-if="missing.length" class="sec-title">还想了解</div>
    <p v-if="missing.length" class="missing">{{ missing.join(' · ') }}</p>
  </section>

  <!-- 题旨态：待确认 / 已确认 / 执行中 -->
  <section v-else-if="brief" class="intent-brief">
    <div class="r-eyebrow">题 旨</div>
    <div class="intent-goal">{{ summaryTitle }}</div>
    <div v-if="knownEntries.length" class="intent-items">
      <template v-for="[key, value] in knownEntries" :key="key">
        <span class="label">{{ key }}</span>
        <span class="value">{{ Array.isArray(value) ? value.join('、') : value }}</span>
      </template>
    </div>
    <button v-if="showStop" class="intent-stop" @click="$emit('stop-and-revise')">停止并修改</button>
  </section>

  <!-- 待确认态：中间已出确认单，右栏只作等待提示 -->
  <section v-else-if="awaiting" class="intent-awaiting">
    <div class="r-eyebrow">题 旨</div>
    <div class="awaiting-text">
      <span class="dot pulse"></span>
      <span>等待你确认</span>
    </div>
  </section>

  <!-- 极简态：尚无意图 -->
  <section v-else class="intent-minimal">
    <div class="r-eyebrow">意 图</div>
    <div class="intent-goal muted">{{ goal || '正在理解你的需求' }}</div>
  </section>
</template>

<style scoped>
/* 眉题：serif 小字，宽字距 */
.r-eyebrow {
  font-family: var(--ch-serif);
  font-size: 11px;
  font-weight: 600;
  color: var(--ch-faint);
  letter-spacing: 1.4px;
  margin-bottom: 12px;
}

/* 题旨 / 目标行 */
.intent-goal {
  font-family: var(--ch-serif);
  font-size: 14.5px;
  font-weight: 600;
  color: var(--ch-text);
  line-height: 1.5;
  margin-bottom: 12px;
}
.intent-goal.muted {
  color: var(--ch-muted);
  font-weight: 500;
}

/* 脚手架态：2px 细进度条 */
.progress-track {
  height: 2px;
  border-radius: 1px;
  background: var(--ch-hair);
  overflow: hidden;
  margin-bottom: 16px;
}
.progress-track i {
  display: block;
  height: 100%;
  background: var(--ch-primary);
  transition: width 0.24s ease;
}

.sec-title {
  font-family: var(--ch-serif);
  font-size: 11px;
  color: var(--ch-faint);
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

/* 已识别槽位：auto 1fr 两列 */
.slots {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 10px;
  row-gap: 7px;
  font-size: 12px;
  margin-bottom: 14px;
}
.slots .sk { color: var(--ch-muted); }
.slots .sv { color: var(--ch-text); font-family: var(--ch-serif); }

.missing {
  font-size: 12px;
  color: var(--ch-orange-2);
  line-height: 1.6;
  margin: 0;
}

/* 题旨态：label / value 两列 */
.intent-items {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 12px;
  row-gap: 9px;
  font-size: 12.5px;
}
.intent-items .label {
  color: var(--ch-faint);
  font-size: 11px;
  letter-spacing: 0.5px;
  align-self: center;
}
.intent-items .value {
  color: var(--ch-body);
  font-family: var(--ch-serif);
}

.intent-stop {
  margin-top: 12px;
  border: none;
  border-bottom: 1px solid transparent;
  background: transparent;
  font-family: var(--ch-serif);
  font-size: 11.5px;
  color: var(--ch-red);
  cursor: pointer;
  padding: 0;
  align-self: flex-start;
}
.intent-stop:hover { border-bottom-color: var(--ch-red); }

/* 待确认态：脉冲点 + 文字 */
.awaiting-text {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--ch-serif);
  font-size: 13px;
  color: var(--ch-primary-2);
}

.awaiting-text .dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--ch-orange);
  flex-shrink: 0;
  animation: awaitingPulse 1.4s ease-in-out infinite;
}

@keyframes awaitingPulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
</style>
