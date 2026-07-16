<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { ROLE_FULL, stepOf } from '../team-panel/roleMeta.js'
import StageHeader from './StageHeader.vue'

const props = defineProps({ task: { type: Object, required: true } })

const CN_NUM = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
function toCN(n) {
  if (n <= 10) return CN_NUM[n]
  if (n < 20) return '十' + (n % 10 ? CN_NUM[n % 10] : '')
  return String(n)
}

const agentType = computed(() => props.task.agent_type)
const roleLabel = computed(() => ROLE_FULL[agentType.value] || agentType.value)
const stepNo = computed(() => String(stepOf(agentType.value)).padStart(2, '0'))
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
const hasOutput = computed(() => chars.value > 0 || units.value > 0)
const unitText = computed(() => (units.value ? toCN(units.value) + unitLabel.value : ''))
const charsText = computed(() => (chars.value ? toCN(chars.value) : ''))
const verb = computed(() => (agentType.value === 'image' ? '画了' : '写下'))
const recordLeft = computed(() => {
  if (!hasOutput.value) return ''
  return unitText.value ? `${verb.value}${unitText.value}` : verb.value
})
</script>

<template>
  <section class="running">
    <StageHeader :number="stepNo" :title="roleLabel" english="PRODUCTION DESK" status="制作中" status-tone="primary" />
    <div class="running-body">
      <div class="running-caption">CURRENT<br>ASSIGNMENT</div>
      <div class="running-copy">
        <div class="aside">{{ aside }}</div>
        <div class="running-meta">
          <div v-if="activityPrefix" class="activity">
            <span class="dot-wrap"><span class="halo"></span><span class="core"></span></span>
            <span class="act-slot">
              <Transition name="label-swap">
                <span :key="activityKind" class="act-prefix">{{ activityPrefix }}</span>
              </Transition>
              <span v-if="activitySuffix" class="act-suffix">{{ activitySuffix }}</span>
            </span>
          </div>
          <div class="record">
            <template v-if="hasOutput">{{ recordLeft }}<span v-if="chars"> · <span class="num">{{ charsText }}</span>字</span></template>
            <span v-else class="record-empty">尚无落笔</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.running { display: block; border: 0; background: rgba(255, 253, 248, .38); }
.running-body { display: grid; grid-template-columns: 118px minmax(0, 1fr); border-top: 2px solid rgba(27, 25, 22, .9); border-bottom: 1px solid rgba(27, 25, 22, .62); }
.running-caption { display: flex; align-items: center; justify-content: center; padding: 18px 12px; border-right: 1px dotted rgba(110, 103, 93, .48); color: var(--ch-warm); font: 600 var(--ch-chat-label-size)/1.45 var(--ch-serif); letter-spacing: .08em; text-align: center; }
.running-copy { min-width: 0; padding: 18px 0 14px 24px; }
.aside {
  font-family: var(--ch-serif);
  max-width: 560px;
  font-size: var(--ch-chat-title-size);
  line-height: 1.72;
  color: var(--ch-text);
  font-weight: 600;
  letter-spacing: .015em;
  padding: 0;
}
.running-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px dotted rgba(110, 103, 93, .46);
  font: 500 11px/1.4 var(--ch-serif);
}
.activity {
  min-width: 0;
  color: var(--ch-body);
  font: inherit;
  letter-spacing: inherit;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 9px;
  min-height: 1.8em;
}
.dot-wrap {
  position: relative;
  width: 5px;
  height: 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.halo {
  position: absolute;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ch-primary);
  animation: breath 1.4s ease-in-out infinite;
}
.core {
  position: absolute;
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--ch-primary-2);
  opacity: .9;
}
@keyframes breath {
  0%, 100% { opacity: .28; }
  50% { opacity: 1; }
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
  font-family: var(--ch-serif);
  font-size: 11px;
  color: var(--ch-muted);
  letter-spacing: .18em;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.record::before { content: none; }
.record .num {
  color: var(--ch-warm);
  font-weight: 600;
}
.record-empty {
  color: var(--ch-faint);
  opacity: .5;
  letter-spacing: .25em;
}

@media (max-width: 700px) {
  .running-body { grid-template-columns: 1fr; }
  .running-caption { border-right: 0; border-bottom: 1px dotted rgba(110, 103, 93, .48); }
}
</style>
