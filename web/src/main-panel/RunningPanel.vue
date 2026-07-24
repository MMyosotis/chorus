<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
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
  <section class="running">
    <header class="running-head">
      <span>{{ roleLabel }}</span>
      <span class="running-status">进行中</span>
    </header>
    <div class="running-copy">
      <h2>{{ aside }}</h2>
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
</template>

<style scoped>
.running { display: block; padding: var(--ch-space-4); border: 1px solid var(--ch-border); border-radius: var(--ch-radius-card); background: var(--ch-surface); box-shadow: var(--ch-shadow-sm); font-family: var(--ch-font-sans); }
.running-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; color: var(--ch-text-secondary); font-size: 12px; font-weight: 600; line-height: 1.5; }
.running-status { display: inline-flex; align-items: center; min-height: 32px; padding: 0 8px; border-radius: var(--ch-radius-pill); background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); font: 600 12px/1 var(--ch-font-sans); white-space: nowrap; }
.running-copy { min-width: 0; padding: 0; }
.running-copy h2 {
  max-width: 560px;
  margin: 24px 0 0;
  font-size: 18px;
  line-height: 1.3;
  color: var(--ch-text);
  font-weight: 600;
  letter-spacing: 0;
}
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
  .running-meta { align-items: flex-start; flex-direction: column; }
  .record { justify-content: flex-start; text-align: left; }
}
</style>
