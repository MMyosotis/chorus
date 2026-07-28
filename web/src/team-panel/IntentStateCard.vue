<script setup>
import { computed } from 'vue'
import { splitStyleTags } from './styleTags.js'

const props = defineProps({ state: { type: Object, default: null } })

const status = computed(() => props.state?.intent_status || 'empty')
const topic = computed(() => props.state?.topic?.trim() || '正在理解你的需求')

const STATUS_META = {
  empty: { label: '等待需求', tone: 'muted' },
  capturing: { label: '理解中', tone: 'live' },
  needs_clarification: { label: '待补充', tone: 'attention' },
  ready_to_confirm: { label: '确认中', tone: 'ready' },
  confirmed: { label: '已确认', tone: 'ready' },
  dispatched: { label: '执行中', tone: 'executing' },
}

const statusMeta = computed(() => STATUS_META[status.value] || STATUS_META.empty)

const specEntries = computed(() => [
  { key: 'platform', value: props.state?.platform },
  { key: 'format', value: props.state?.format },
  {
    key: 'image-count',
    value: props.state?.topic && props.state?.image_count != null
      ? `${props.state.image_count} 张`
      : null,
  },
].filter(({ value }) => value !== null && value !== undefined && String(value).trim() !== ''))

const styleTags = computed(() => splitStyleTags(props.state?.style))

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

    <div v-if="specEntries.length || styleTags.length" class="tags">
      <div v-if="specEntries.length" class="spec-tags">
        <span
          v-for="entry in specEntries"
          :key="entry.key"
          class="tag spec-tag"
          :class="{ 'tag-count': entry.key === 'image-count' }"
          :title="displayValue(entry.value)"
        >{{ displayValue(entry.value) }}</span>
      </div>
      <div v-if="styleTags.length" class="style-tags">
        <span
          v-for="tag in styleTags"
          :key="tag"
          class="tag style-tag"
          :title="tag"
        >{{ tag }}</span>
      </div>
    </div>

    <div class="intent-progress">
      <div class="progress-line">
        <strong>意图进度</strong>
        <span>{{ progress }}%</span>
      </div>
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
    </div>
  </section>
</template>

<style scoped>
.intent-card {
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
  color: var(--ch-ink);
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
  background: var(--ch-muted-gradient);
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

.intent-status.muted {
  background: var(--ch-muted-gradient);
  color: var(--ch-text-muted);
}

.intent-status.live {
  background: var(--ch-ink);
  color: var(--ch-on-ink);
}

.intent-status.live i {
  background: var(--ch-on-ink);
  animation: intentPulse 1.8s ease-in-out infinite;
}

.intent-status.executing {
  background: var(--ch-ink);
  color: var(--ch-on-ink);
}

.intent-status.executing i {
  background: var(--ch-on-ink);
  animation: intentStatusPulse 1.8s ease-in-out infinite;
}

.intent-status.attention {
  background: var(--ch-ink);
  color: var(--ch-on-ink);
}

.intent-status.attention i {
  background: var(--ch-on-ink);
}

.intent-status.ready {
  background: var(--ch-ink);
  color: var(--ch-on-ink);
}

.intent-status.ready i {
  background: var(--ch-on-ink);
}

.intent-summary {
  margin-top: var(--ch-space-4);
}

.intent-topic {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: var(--ch-ink);
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

.tags {
  margin-top: 13px;
}

.spec-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag {
  display: block;
  min-width: 0;
  padding: 2px var(--ch-space-2);
  overflow: hidden;
  border-radius: var(--ch-radius-pill);
  background: var(--ch-muted-gradient);
  color: var(--ch-text-secondary);
  font-size: var(--ch-text-xs);
  font-weight: var(--ch-font-medium);
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.spec-tag:not(.tag-count) {
  max-width: 112px;
}

.tag-count {
  flex: 0 0 auto;
}

.style-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.style-tag {
  max-width: 100%;
}

.intent-progress {
  margin-top: var(--ch-space-3);
  padding: 18px;
  border-radius: 14px;
  background: var(--ch-muted-gradient);
}

.progress-line {
  display: flex;
  align-items: center;
  margin-bottom: 13px;
  color: var(--ch-text-muted);
  font-size: var(--ch-text-xs);
}

.progress-line strong {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.progress-line span {
  margin-left: auto;
  color: var(--ch-ink);
  font-weight: var(--ch-font-semibold);
  font-variant-numeric: tabular-nums;
}

.progress-track {
  height: 9px;
  overflow: hidden;
  border-radius: 9px;
  background: var(--ch-border);
}

.progress-track i {
  display: block;
  width: 0;
  height: 100%;
  border-radius: 9px;
  background: var(--ch-accent);
  transition: width .32s ease-out;
}

@keyframes intentPulse {
  0%, 100% { opacity: .35; }
  50% { opacity: 1; }
}

@keyframes intentStatusPulse {
  0%, 100% {
    box-shadow: 0 0 0 0 color-mix(in srgb, var(--ch-on-ink) 34%, transparent);
  }
  50% {
    box-shadow: 0 0 0 4px transparent;
  }
}

@media (prefers-reduced-motion: reduce) {
  .intent-status.live i,
  .intent-status.executing i { animation: none; }
  .progress-track i { transition: none; }
}
</style>
