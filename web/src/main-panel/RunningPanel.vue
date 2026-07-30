<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import AgentAvatar from '../team-panel/AgentAvatar.vue'
import { ROLE_FULL } from '../team-panel/roleMeta.js'

const props = defineProps({ task: { type: Object, required: true } })

const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
function toCN(n) {
  if (n <= 10) return CN_NUM[n]
  if (n < 20) return '十' + (n % 10 ? CN_NUM[n % 10] : '')
  return String(n)
}

const agentType = computed(() => props.task.agent_type)
const roleLabel = computed(() => ROLE_FULL[agentType.value] || agentType.value)
const prog = computed(() => props.task.progress || {})
const aside = computed(() => prog.value.aside || '正在创作')

const activityKind = computed(() => prog.value.activity_kind || '')
const activityDetail = computed(() => prog.value.activity_detail || '')
const startedAt = computed(() => prog.value.activity_started_at || 0)
const activityPrefix = computed(() => prog.value.activity_line || '')

// 思考态秒数:本地每秒滴答,用后端起始时间算经过秒
const now = ref(Date.now())
let timer = null
watch(
  activityKind,
  (kind) => {
    if (timer) { clearInterval(timer); timer = null }
    if (kind === 'thinking' && startedAt.value) {
      timer = setInterval(() => { now.value = Date.now() }, 1000)
    }
  },
  { immediate: true },
)
onUnmounted(() => { if (timer) clearInterval(timer) })

const elapsedSec = computed(() => {
  if (activityKind.value !== 'thinking' || !startedAt.value) return null
  return Math.max(0, Math.floor(now.value / 1000 - startedAt.value))
})

function truncate(text, n) {
  const s = String(text || '').trim().replace(/\n/g, ' ')
  return s.length > n ? s.slice(0, n) + '…' : s
}

const activitySuffix = computed(() => {
  if (activityKind.value === 'thinking') {
    return elapsedSec.value != null ? ` · ${elapsedSec.value}″` : ''
  }
  if (activityKind.value === 'drawing' || activityKind.value === 'searching') {
    const detail = truncate(activityDetail.value, 20)
    return detail ? ` · ${detail}` : ''
  }
  return ''
})

const chars = computed(() => prog.value.composing_chars || 0)
const units = computed(() => prog.value.composing_units || 0)
const unitLabel = computed(() => prog.value.composing_label || '')
const total = computed(() => props.task.progress_total || 0)
const hasOutput = computed(() => chars.value > 0 || units.value > 0)
const unitText = computed(() => (units.value ? toCN(units.value) + unitLabel.value : ''))
const charsText = computed(() => (chars.value ? toCN(chars.value) : ''))
const verb = computed(() => (agentType.value === 'image' ? '画了' : '写下'))
const recordLeft = computed(() => {
  if (!hasOutput.value) return ''
  if (total.value > 0) return `已 ${units.value} / 共 ${total.value} ${unitLabel.value}`
  return unitText.value ? `${verb.value}${unitText.value}` : verb.value
})
</script>

<template>
  <div class="running-panel">
    <header class="turn-head">
      <AgentAvatar :agent-type="agentType" status="finished" :size="40" />
      <span class="role">{{ roleLabel }}</span>
    </header>
    <section class="running">
      <header class="running-head">
        <span class="running-sparkle" aria-hidden="true">
          <svg viewBox="0 0 18 18">
            <defs>
              <linearGradient id="runningSparkleGrad" x1="2.5" y1="1.5" x2="16.3" y2="16.5" gradientUnits="userSpaceOnUse">
                <stop offset="0" stop-color="var(--ch-accent)" />
                <stop offset="1" stop-color="var(--ch-accent-soft-text)" />
              </linearGradient>
            </defs>
            <path
              class="sparkle-main"
              d="M8 1.5C8 5.25 10.75 9 13.5 9C10.75 9 8 12.75 8 16.5C8 12.75 5.25 9 2.5 9C5.25 9 8 5.25 8 1.5Z"
              fill="url(#runningSparkleGrad)"
            />
            <path
              class="sparkle-small"
              d="M14.5 11.5C14.5 12.75 15.4 14 16.3 14C15.4 14 14.5 15.25 14.5 16.5C14.5 15.25 13.6 14 12.7 14C13.6 14 14.5 12.75 14.5 11.5Z"
              fill="url(#runningSparkleGrad)"
            />
          </svg>
        </span>
        <h2>{{ aside }}</h2>
        <span class="running-status ch-status-pill is-running"><i aria-hidden="true"></i>进行中</span>
      </header>
      <div class="running-copy">
        <div class="running-meta">
          <div v-if="activityPrefix" class="activity">
            <span class="act-slot">
              <Transition name="label-swap">
                <span :key="activityKind" class="act-prefix">{{ activityPrefix }}</span>
              </Transition>
              <span v-if="activitySuffix" class="act-suffix">{{ activitySuffix }}</span>
            </span>
          </div>
          <div class="record">
            <template v-if="hasOutput">{{ recordLeft }}<span v-if="chars"> · <span class="num">{{ charsText }}</span>字</span></template>
            <span v-else class="record-empty">正在准备内容</span>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.running-panel { width: 100%; }
.turn-head { display: flex; align-items: center; gap: var(--ch-space-2); min-height: 32px; margin-bottom: var(--ch-space-3); }
.turn-head :deep(.agent-avatar) {
  box-shadow: var(--ch-shadow-bubble);
}
.turn-head .role { color: var(--ch-text); font: 500 16px/1 var(--ch-font-sans); letter-spacing: 0; }
.running { display: block; padding: var(--ch-space-4); border: 1px solid var(--ch-border); border-radius: var(--ch-radius-card); background: var(--ch-surface); box-shadow: var(--ch-shadow-soft); font-family: var(--ch-font-sans); }
.running-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: var(--ch-space-2) 0;
  color: var(--ch-text-secondary);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
}
.running-head h2 {
  min-width: 0;
  max-width: 560px;
  margin: 0;
  color: var(--ch-text);
  font-size: 18px;
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: 0;
}
.running-sparkle {
  position: relative;
  display: inline-flex;
  width: 28px;
  height: 28px;
  flex: 0 0 28px;
  align-items: center;
  justify-content: center;
  color: var(--ch-accent);
}
.running-sparkle::before {
  position: absolute;
  inset: 4px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--ch-accent) 20%, transparent);
  content: "";
  filter: blur(6px);
  opacity: .35;
  animation: sparkle-glow 1.8s ease-in-out infinite;
}
.running-sparkle svg {
  position: relative;
  width: 26px;
  height: 26px;
  overflow: visible;
}
.sparkle-main {
  transform-box: fill-box;
  transform-origin: center;
  animation: sparkle-main 1.6s cubic-bezier(.4, .2, .6, .8) infinite;
  will-change: transform, opacity;
}
.sparkle-small {
  transform-box: fill-box;
  transform-origin: center;
  animation: sparkle-small 1.6s cubic-bezier(.4, .2, .6, .8) .2s infinite;
  will-change: transform, opacity;
}
@keyframes sparkle-main {
  0%, 100% { transform: scale(.76, .86); opacity: .58; }
  50% { transform: scale(1.18, 1.06); opacity: 1; }
}
@keyframes sparkle-small {
  0%, 100% { transform: scale(.3); opacity: .12; }
  50% { transform: scale(1.18); opacity: 1; }
}
@keyframes sparkle-glow {
  0%, 100% { transform: scale(.72); opacity: .18; }
  45% { transform: scale(1.18); opacity: .42; }
}
.running-status {
  flex: 0 0 auto;
  margin-left: auto;
}
.running-copy { min-width: 0; padding: 0; }
.running-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--ch-border);
  font: 500 12px/1.5 var(--ch-font-sans);
}
.activity {
  min-width: 0;
  color: var(--ch-text-secondary);
  font: inherit;
  letter-spacing: inherit;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  min-height: 1.8em;
}
.act-slot {
  position: relative;
  display: inline-flex;
  align-items: center;
  min-height: 1em;
}
.act-prefix {
  display: inline-block;
}
.label-swap-enter-from { transform: translateY(8px); opacity: 0; }
.label-swap-enter-active { transition: transform .2s ease, opacity .18s ease; }
.label-swap-leave-active {
  position: absolute;
  left: 0;
  top: 0;
  transition: transform .2s ease, opacity .18s ease;
}
.label-swap-leave-to { transform: translateY(-8px); opacity: 0; }
.act-suffix { white-space: nowrap; }
.record {
  flex: 0 0 auto;
  min-height: 1.8em;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  font-family: var(--ch-font-sans);
  font-size: 12px;
  color: var(--ch-text-muted);
  letter-spacing: 0;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.record::before { content: none; }
.record .num {
  color: var(--ch-accent);
  font-weight: 600;
}
.record-empty {
  color: var(--ch-text-faint);
  opacity: .72;
}

@media (max-width: 700px) {
  .running { padding: 16px; }
  .running-head { align-items: flex-start; }
  .running-head h2 { flex: 1; }
  .running-sparkle { width: 24px; height: 24px; flex-basis: 24px; }
  .running-sparkle svg { width: 22px; height: 22px; }
  .running-meta { align-items: flex-start; flex-direction: column; }
  .record { justify-content: flex-start; text-align: left; }
}

@media (prefers-reduced-motion: reduce) {
  .sparkle-main,
  .sparkle-small,
  .running-sparkle::before {
    animation: none;
  }
  .sparkle-main,
  .sparkle-small {
    opacity: 1;
    transform: none;
  }
}
</style>
