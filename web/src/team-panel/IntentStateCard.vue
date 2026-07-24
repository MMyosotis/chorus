<script setup>
import { computed } from 'vue'

const props = defineProps({ state: { type: Object, default: null } })

const status = computed(() => props.state?.intent_status || 'empty')
const topic = computed(() => props.state?.topic?.trim() || '正在理解你的需求')

const STATUS_META = {
  empty: { label: '等待需求', tone: 'muted' },
  capturing: { label: '理解中', tone: 'live' },
  needs_clarification: { label: '待补充', tone: 'attention' },
  ready_to_confirm: { label: '信息齐备', tone: 'ready' },
  confirmed: { label: '已确认', tone: 'ready' },
  dispatched: { label: '执行中', tone: 'live' },
}

const statusMeta = computed(() => STATUS_META[status.value] || STATUS_META.empty)

const baseEntries = computed(() => [
  ['发布平台', props.state?.platform],
  ['内容形式', props.state?.format],
  ['表达风格', props.state?.style],
  ['配图需求', props.state?.topic && props.state?.image_count != null
    ? `${props.state.image_count} 张`
    : null],
])

const extraEntries = computed(() => Object.entries(props.state?.extra || {}))

const entries = computed(() => [...baseEntries.value, ...extraEntries.value]
  .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
  .slice(0, 6))

const progress = computed(() => {
  const value = Number(props.state?.progress_percent)
  if (!Number.isFinite(value)) return 0
  return Math.min(100, Math.max(0, Math.round(value)))
})

function displayValue(value) {
  if (Array.isArray(value)) return value.join('、')
  if (value && typeof value === 'object') return Object.values(value).join('、')
  return String(value)
}
</script>

<template>
  <section class="intent-card" aria-labelledby="intent-card-title">
    <header class="intent-head">
      <div class="intent-heading">
        <h2 id="intent-card-title">意图理解</h2>
      </div>
      <span class="intent-status" :class="statusMeta.tone">
        <i aria-hidden="true"></i>{{ statusMeta.label }}
      </span>
    </header>

    <div class="intent-summary">
      <p class="intent-topic">{{ topic }}</p>
      <p v-if="status === 'empty'" class="intent-helper">你的创作方向将在这里自动整理</p>
    </div>

    <dl v-if="entries.length" class="intent-fields">
      <template v-for="([label, value]) in entries" :key="label">
        <dt>{{ label }}</dt>
        <dd :title="displayValue(value)">{{ displayValue(value) }}</dd>
      </template>
    </dl>

    <div class="intent-progress">
      <div class="progress-copy">
        <p>意图已完成 <strong>{{ progress }}%</strong></p>
      </div>
      <div class="progress-row">
        <div
          class="progress-track"
          role="progressbar"
          aria-label="意图完整度"
          aria-valuemin="0"
          aria-valuemax="100"
          :aria-valuenow="progress"
        >
          <i :style="{ width: `${progress}%` }"></i>
        </div>
        <span>{{ progress }}/100</span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.intent-card {
  padding: var(--ch-space-4);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.intent-head,
.intent-heading,
.intent-status {
  display: flex;
  align-items: center;
}

.intent-head {
  justify-content: space-between;
  gap: var(--ch-space-2);
}

.intent-heading {
  min-width: 0;
  gap: var(--ch-space-2);
}

.intent-heading h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 24px;
  white-space: nowrap;
}

.intent-status {
  min-height: 24px;
  flex: 0 0 auto;
  gap: 8px;
  padding: 0 8px;
  border-radius: var(--ch-radius-pill);
  background: var(--ch-surface-3);
  color: var(--ch-text-muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  white-space: nowrap;
}

.intent-status i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.intent-status.live {
  background: var(--ch-accent-soft);
  color: var(--ch-accent-soft-text);
}

.intent-status.live i {
  animation: intentPulse 1.8s ease-in-out infinite;
}

.intent-status.attention {
  background: var(--ch-warning-soft);
  color: var(--ch-warning-text);
}

.intent-status.ready {
  background: var(--ch-success-soft);
  color: var(--ch-success-text);
}

.intent-summary {
  margin-top: var(--ch-space-4);
}

.intent-topic {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--ch-text);
  font-size: 16px;
  font-weight: 600;
  line-height: 24px;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.intent-helper {
  margin: 8px 0 0;
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 18px;
}

.intent-fields {
  display: grid;
  grid-template-columns: 64px minmax(0, 1fr);
  align-items: center;
  gap: 8px var(--ch-space-2);
  margin: var(--ch-space-3) 0 0;
}

.intent-fields dt,
.intent-fields dd {
  margin: 0;
}

.intent-fields dt {
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 18px;
  white-space: nowrap;
}

.intent-fields dd {
  min-width: 0;
  display: -webkit-box;
  overflow: hidden;
  color: var(--ch-text-secondary);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.intent-progress {
  margin-top: var(--ch-space-3);
  padding: var(--ch-space-3);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface-3);
}

.progress-copy {
  display: flex;
  align-items: center;
}

.progress-copy p {
  margin: 0;
  color: var(--ch-text-secondary);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
}

.progress-copy strong {
  color: var(--ch-text);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.progress-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--ch-space-2);
  margin-top: var(--ch-space-3);
}

.progress-track {
  height: 16px;
  overflow: hidden;
  border-radius: var(--ch-radius-btn);
  background: var(--ch-border);
}

.progress-track i {
  display: block;
  width: 0;
  height: 100%;
  border-radius: inherit;
  background: var(--ch-accent-gradient);
  transition: width .32s ease-out;
}

.progress-row span {
  color: var(--ch-text-muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

@keyframes intentPulse {
  0%, 100% { opacity: .35; }
  50% { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .intent-status.live i { animation: none; }
  .progress-track i { transition: none; }
}
</style>
