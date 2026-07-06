<script setup>
import { computed } from 'vue'

const props = defineProps({
  state: { type: Object, default: null },
  hasActiveTask: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'revise', 'stop-and-revise'])

const status = computed(() => props.state?.intent_status || 'empty')
const knownEntries = computed(() => {
  const slots = props.state?.known_slots || {}
  return Object.entries(slots)
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
    .slice(0, 8)
})
const missing = computed(() => props.state?.missing_slots || [])
const questions = computed(() => props.state?.open_questions || [])
const summaryItems = computed(() => props.state?.confirmation_summary?.items || [])
const title = computed(() => props.state?.confirmation_summary?.title || props.state?.goal || '等待识别意图')
const progress = computed(() => {
  if (status.value === 'empty') return 0
  if (status.value === 'capturing') return 28
  if (status.value === 'needs_clarification') return 56
  if (status.value === 'ready_to_confirm') return 86
  return 100
})
const statusLabel = computed(() => ({
  empty: '待开始',
  capturing: '识别中',
  needs_clarification: '待补充',
  ready_to_confirm: '待确认',
  confirmed: '已确认',
  dispatched: '执行中',
}[status.value] || '识别中'))
const nextLabel = computed(() => ({
  reply_only: '主 Agent 回复用户',
  ask_user: '主 Agent 继续澄清',
  wait_user_confirm: '等待用户确认',
  create_plan_after_confirm: '准备创建任务',
  dispatching: '任务执行中',
  blocked: '等待处理',
}[props.state?.next_action] || '等待用户输入'))
</script>

<template>
  <section class="intent-card" :class="status">
    <div class="intent-top">
      <div>
        <p class="eyebrow">Intent</p>
        <h2>{{ title }}</h2>
      </div>
      <span class="status-pill">{{ statusLabel }}</span>
    </div>

    <div class="progress-track">
      <span :style="{ width: `${progress}%` }"></span>
    </div>

    <div class="next-line">
      <span class="dot"></span>
      <span>{{ nextLabel }}</span>
    </div>

    <div v-if="knownEntries.length" class="section">
      <div class="section-title">已识别</div>
      <div class="slot-grid">
        <div v-for="[key, value] in knownEntries" :key="key" class="slot-item">
          <span>{{ key }}</span>
          <strong>{{ Array.isArray(value) ? value.join('、') : value }}</strong>
        </div>
      </div>
    </div>

    <div v-if="summaryItems.length" class="section">
      <div class="section-title">确认摘要</div>
      <div class="summary-list">
        <div v-for="item in summaryItems" :key="item.label" class="summary-row">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
    </div>

    <div v-if="missing.length || questions.length" class="section">
      <div class="section-title">待补充</div>
      <div class="missing-list">
        <span v-for="item in missing" :key="item">{{ item }}</span>
      </div>
      <p v-for="q in questions" :key="q" class="question">{{ q }}</p>
    </div>

    <div v-if="status === 'ready_to_confirm'" class="actions">
      <button class="primary" @click="$emit('confirm')">确认意图</button>
      <button class="secondary" @click="$emit('revise')">继续调整</button>
    </div>

    <div v-else-if="hasActiveTask" class="actions">
      <button class="secondary danger" @click="$emit('stop-and-revise')">停止并修改</button>
    </div>
  </section>
</template>

<style scoped>
.intent-card {
  background: #ffffff;
  border: 1px solid #dde5ee;
  border-radius: 8px;
  padding: 18px;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
  color: #172033;
}

.intent-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.eyebrow {
  margin-bottom: 6px;
  color: #667085;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0;
}

h2 {
  font-size: 17px;
  line-height: 1.35;
  font-weight: 760;
  color: #172033;
}

.status-pill {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 5px 10px;
  background: #eef2ff;
  color: #4338ca;
  font-size: 12px;
  font-weight: 700;
}

.needs_clarification .status-pill,
.capturing .status-pill {
  background: #fffbeb;
  color: #b45309;
}

.dispatched .status-pill,
.confirmed .status-pill {
  background: #ecfdf5;
  color: #047857;
}

.progress-track {
  height: 7px;
  margin: 18px 0 14px;
  border-radius: 999px;
  background: #e8edf3;
  overflow: hidden;
}

.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #4338ca;
  transition: width 0.24s ease;
}

.next-line {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #667085;
  font-size: 13px;
}

.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #4338ca;
}

.section {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid #e8edf3;
}

.section-title {
  margin-bottom: 10px;
  color: #667085;
  font-size: 12px;
  font-weight: 750;
}

.slot-grid,
.summary-list {
  display: grid;
  gap: 8px;
}

.slot-item,
.summary-row {
  display: grid;
  grid-template-columns: minmax(64px, 0.42fr) 1fr;
  gap: 10px;
  align-items: start;
  font-size: 13px;
}

.slot-item span,
.summary-row span {
  color: #667085;
  overflow-wrap: anywhere;
}

.slot-item strong,
.summary-row strong {
  color: #172033;
  font-weight: 650;
  overflow-wrap: anywhere;
}

.missing-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}

.missing-list span {
  border: 1px solid #fcd34d;
  border-radius: 999px;
  padding: 4px 9px;
  color: #92400e;
  background: #fffbeb;
  font-size: 12px;
  font-weight: 650;
}

.question {
  color: #475467;
  font-size: 13px;
  line-height: 1.55;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 18px;
}

button {
  height: 36px;
  border-radius: 8px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 750;
  cursor: pointer;
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

.danger {
  color: #b42318;
}
</style>
