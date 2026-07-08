<script setup>
import { computed } from 'vue'

const props = defineProps({
  state: { type: Object, default: null },
  hasActiveTask: { type: Boolean, default: false },
})

defineEmits(['stop-and-revise'])

const status = computed(() => props.state?.intent_status || 'empty')
const goal = computed(() => props.state?.goal || '')

// 已识别槽位：过滤空值，最多 8 条
const knownEntries = computed(() => {
  const slots = props.state?.known_slots || {}
  return Object.entries(slots)
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
    .slice(0, 8)
})
const missing = computed(() => props.state?.missing_slots || [])
const title = computed(() => props.state?.confirmation_summary?.title || goal.value || '等待识别意图')

const progress = computed(() => ({
  empty: 0,
  capturing: 28,
  needs_clarification: 56,
  ready_to_confirm: 86,
}[status.value] ?? 100))

const statusLabel = computed(() => ({
  empty: '待开始',
  capturing: '识别中',
  needs_clarification: '待补充',
  ready_to_confirm: '待你确认',
  confirmed: '已确认',
  dispatched: '执行中',
}[status.value] || '识别中'))

// capturing / needs_clarification 才展开脚手架卡
const expanded = computed(() =>
  status.value === 'capturing' || status.value === 'needs_clarification'
)
</script>

<template>
  <!-- 折叠态：已确认 / 执行中，一行带停止入口 -->
  <section v-if="status === 'confirmed' || status === 'dispatched'" class="intent-card collapsed">
    <span class="dot done"></span>
    <span class="collapse-text">已确认：{{ goal || '开始执行' }}</span>
    <button v-if="hasActiveTask" class="link-danger" @click="$emit('stop-and-revise')">停止并修改</button>
  </section>

  <!-- ready_to_confirm：锚点提示，确认单在对话区 -->
  <section v-else-if="status === 'ready_to_confirm'" class="intent-card anchor">
    <span class="dot pulse"></span>
    <span>待你确认</span>
    <span class="anchor-hint">请在对话区查看确认单</span>
  </section>

  <!-- empty：极简占位 -->
  <section v-else-if="status === 'empty'" class="intent-card minimal">
    <span class="dot"></span>
    <span>{{ goal || '正在理解你的需求' }}</span>
  </section>

  <!-- capturing / needs_clarification：脚手架卡 -->
  <section v-else class="intent-card" :class="status">
    <div class="intent-top">
      <div>
        <p class="eyebrow">意图</p>
        <h2>{{ title }}</h2>
      </div>
      <span class="status-pill">{{ statusLabel }}</span>
    </div>

    <div class="progress-track">
      <span :style="{ width: `${progress}%` }"></span>
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

    <div v-if="missing.length" class="section">
      <div class="section-title">还想了解</div>
      <p class="missing-line">{{ missing.join('、') }}</p>
    </div>
  </section>
</template>

<style scoped>
.intent-card {
  background: var(--ch-surface);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-md);
  padding: 18px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.04);
  color: var(--ch-text);
}

/* 折叠 / 锚点 / 极简 三态：单行布局 */
.collapsed,
.anchor,
.minimal {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  font-size: 13px;
}

.collapse-text {
  flex: 1;
  overflow-wrap: anywhere;
}

.link-danger {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--ch-red);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  padding: 0;
}

.link-danger:hover { text-decoration: underline; }

.anchor-hint {
  margin-left: auto;
  color: var(--ch-faint);
  font-size: 12px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--ch-faint);
}

.minimal .dot { background: var(--ch-primary); }
.anchor .dot { background: var(--ch-orange); }
.done { background: var(--ch-green); }

.pulse {
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

/* 脚手架卡：原丰富布局 */
.intent-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.eyebrow {
  margin-bottom: 6px;
  color: var(--ch-muted);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
}

h2 {
  font-size: 17px;
  line-height: 1.35;
  font-family: var(--ch-serif);
  font-weight: 600;
  color: var(--ch-text);
}

.status-pill {
  flex-shrink: 0;
  border-radius: 999px;
  padding: 5px 10px;
  background: var(--ch-primary-soft);
  color: var(--ch-primary);
  font-size: 12px;
  font-weight: 600;
}

.needs_clarification .status-pill,
.capturing .status-pill {
  background: var(--ch-orange-soft);
  color: var(--ch-orange-2);
}

.progress-track {
  height: 7px;
  margin: 18px 0 14px;
  border-radius: 999px;
  background: var(--ch-border);
  overflow: hidden;
}

.progress-track span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--ch-primary);
  transition: width 0.24s ease;
}

.section {
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--ch-border);
}

.section-title {
  margin-bottom: 10px;
  color: var(--ch-muted);
  font-size: 12px;
  font-weight: 600;
}

.slot-grid {
  display: grid;
  gap: 8px;
}

.slot-item {
  display: grid;
  grid-template-columns: minmax(64px, 0.42fr) 1fr;
  gap: 10px;
  align-items: start;
  font-size: 13px;
}

.slot-item span {
  color: var(--ch-muted);
  overflow-wrap: anywhere;
}

.slot-item strong {
  color: var(--ch-text);
  font-weight: 600;
  overflow-wrap: anywhere;
}

.missing-line {
  color: var(--ch-body);
  font-size: 13px;
  line-height: 1.55;
  overflow-wrap: anywhere;
}
</style>
