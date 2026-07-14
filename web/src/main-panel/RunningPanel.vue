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
const hasOutput = computed(() => chars.value > 0 || units.value > 0)
const unitText = computed(() => (units.value ? toCN(units.value) + unitLabel.value : ''))
const charsText = computed(() => (chars.value ? toCN(chars.value) : ''))
const recordPrefix = computed(() => {
  if (!hasOutput.value) return ''
  return unitText.value ? `写下 ${unitText.value} · ` : '写下 '
})
</script>

<template>
  <div class="sheet">
    <div class="rp-role">{{ roleLabel }}</div>
    <div class="sheet-body">
      <div class="aside">{{ aside }}</div>
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
        <template v-if="hasOutput">{{ recordPrefix }}<span class="num">{{ charsText }}</span>字</template>
        <span v-else class="record-empty">尚无落笔</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sheet {
  position: relative;
  padding: 26px 0;
}
.rp-role {
  position: absolute;
  top: 26px;
  left: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  height: 24px;
  padding: 0 4px;
  font-family: var(--ch-serif);
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  letter-spacing: .5px;
  background: var(--ch-primary-soft);
  color: var(--ch-primary-2);
  z-index: 1;
}
.sheet-body {
  text-align: center;
  margin-top: 40px;
}
.aside {
  font-size: 18px;
  line-height: 1.6;
  color: var(--ch-text);
  font-weight: 600;
  letter-spacing: .1em;
  padding: 2px 8px;
}
.activity {
  margin-top: 26px;
  font-size: 13.5px;
  line-height: 1.95;
  color: var(--ch-body);
  letter-spacing: .3px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 9px;
  min-height: 1.8em;
}
.dot-wrap {
  position: relative;
  width: 9px;
  height: 9px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.halo {
  position: absolute;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--ch-primary) 0%, rgba(59, 90, 114, .32) 55%, transparent 100%);
  animation: breath 1.4s ease-in-out infinite;
}
.core {
  position: absolute;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ch-primary-2);
  opacity: .9;
}
@keyframes breath {
  0%, 100% { transform: scale(.7); opacity: .55; }
  50% { transform: scale(1.9); opacity: .18; }
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
  position: relative;
  margin-top: 40px;
  padding-top: 22px;
  font-size: 12.5px;
  color: var(--ch-muted);
  letter-spacing: .18em;
  min-height: 1.6em;
  font-variant-numeric: tabular-nums;
}
.record::before {
  content: '';
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 120px;
  height: 1px;
  background: linear-gradient(to right, var(--ch-border-2) 50%, transparent 0);
  background-size: 5px 1px;
  background-repeat: repeat-x;
  opacity: .7;
}
.record .num {
  color: var(--ch-orange);
  font-weight: 600;
}
.record-empty {
  color: var(--ch-faint);
  opacity: .5;
  letter-spacing: .25em;
}
</style>
