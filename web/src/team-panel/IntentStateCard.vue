<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'

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

const stageLabel = computed(() => ({
  empty: '识别中',
  capturing: '识别中',
  needs_clarification: '待补充',
  ready_to_confirm: '待确认',
  confirmed: '已确认',
  dispatched: '已派发',
}[status.value] || ''))

const stageClass = computed(() => ({
  empty: 's-identify',
  capturing: 's-identify',
  needs_clarification: 's-clarify',
  ready_to_confirm: 's-confirm',
  confirmed: 's-confirmed',
  dispatched: 's-dispatch',
}[status.value] || ''))

const scaffold = computed(() =>
  status.value === 'capturing' || status.value === 'needs_clarification'
)
const brief = computed(() =>
  status.value === 'confirmed' || status.value === 'dispatched'
)
const awaiting = computed(() => status.value === 'ready_to_confirm')
const showStop = computed(() => props.hasActiveTask && status.value === 'dispatched')

const slotText = (value) => (Array.isArray(value) ? value.join('、') : value)

const floating = ref(null)
let hideTimer = null

const showTip = (event) => {
  const trunc = event.currentTarget.querySelector('.trunc')
  if (!trunc || trunc.scrollWidth <= trunc.clientWidth) return
  clearTimeout(hideTimer)
  const rect = trunc.getBoundingClientRect()
  floating.value = {
    text: trunc.textContent,
    left: rect.left,
    top: rect.top - 6,
  }
}
const hideTip = () => {
  hideTimer = setTimeout(() => { floating.value = null }, 120)
}
onBeforeUnmount(() => {
  clearTimeout(hideTimer)
  floating.value = null
})
</script>

<template>
  <!-- 脚手架态：意图识别中 / 待补充 -->
  <section v-if="scaffold" class="slip intent-scaffold">
    <div class="knob"></div>
    <div class="r-eyebrow">
      <span>题旨</span>
      <span class="stage" :class="stageClass"><i class="stage-dot"></i>{{ stageLabel }}</span>
    </div>
    <div class="intent-goal tip" @mouseenter="showTip" @mouseleave="hideTip"><span class="trunc">{{ summaryTitle }}</span></div>

    <div v-if="knownEntries.length" class="sec-title">已知</div>
    <div v-if="knownEntries.length" class="slots">
      <template v-for="[key, value] in knownEntries" :key="key">
        <span class="sk">{{ key }}</span>
        <span class="sv tip" @mouseenter="showTip" @mouseleave="hideTip"><span class="trunc">{{ slotText(value) }}</span></span>
      </template>
    </div>

    <div v-if="missing.length" class="sec-title">待问</div>
    <p v-if="missing.length" class="missing tip" @mouseenter="showTip" @mouseleave="hideTip"><span class="trunc">{{ missing.join(' · ') }}</span></p>
  </section>

  <!-- 题旨态：已确认 / 执行中 -->
  <section v-else-if="brief" class="slip intent-brief">
    <div class="knob"></div>
    <div class="r-eyebrow">
      <span>题旨</span>
      <span class="stage" :class="stageClass"><i class="stage-dot"></i>{{ stageLabel }}</span>
    </div>
    <div class="intent-goal tip" @mouseenter="showTip" @mouseleave="hideTip"><span class="trunc">{{ summaryTitle }}</span></div>

    <div v-if="knownEntries.length" class="sec-title">已知</div>
    <div v-if="knownEntries.length" class="slots">
      <template v-for="[key, value] in knownEntries" :key="key">
        <span class="sk">{{ key }}</span>
        <span class="sv tip" @mouseenter="showTip" @mouseleave="hideTip"><span class="trunc">{{ slotText(value) }}</span></span>
      </template>
    </div>

    <button v-if="showStop" class="intent-stop" @click="$emit('stop-and-revise')">停止并修改</button>
  </section>

  <!-- 待确认态：中间已出确认单，右栏只作等待提示 -->
  <section v-else-if="awaiting" class="slip intent-awaiting">
    <div class="knob"></div>
    <div class="r-eyebrow">
      <span>题旨</span>
      <span class="stage" :class="stageClass"><i class="stage-dot"></i>{{ stageLabel }}</span>
    </div>
    <div class="intent-goal tip" @mouseenter="showTip" @mouseleave="hideTip"><span class="trunc">{{ summaryTitle }}</span></div>

    <div class="sec-title">已知</div>
    <div class="slots" v-if="knownEntries.length">
      <template v-for="[key, value] in knownEntries" :key="key">
        <span class="sk">{{ key }}</span>
        <span class="sv tip" @mouseenter="showTip" @mouseleave="hideTip"><span class="trunc">{{ slotText(value) }}</span></span>
      </template>
    </div>
    <div class="slots-placeholder" v-else>待识别</div>

    <div class="sec-title">待问</div>
    <div class="missing tip" v-if="missing.length" @mouseenter="showTip" @mouseleave="hideTip"><span class="trunc">{{ missing.join(' · ') }}</span></div>
    <div class="missing-placeholder" v-else>待补充</div>
  </section>

  <!-- 极简态：尚无意图 -->
  <section v-else class="slip intent-minimal">
    <div class="knob"></div>
    <div class="r-eyebrow">
      <span>题旨</span>
      <span class="stage" :class="stageClass"><i class="stage-dot"></i>{{ stageLabel }}</span>
    </div>
    <div class="intent-goal muted tip" @mouseenter="showTip" @mouseleave="hideTip"><span class="trunc">{{ goal || '正在理解你的需求' }}</span></div>

    <div class="sec-title">已知</div>
    <div class="slots-placeholder">待识别</div>

    <div class="sec-title">待问</div>
    <div class="missing-placeholder">待补充</div>
  </section>

  <Teleport to="body">
    <div v-if="floating" class="intent-tip" :style="{ left: floating.left + 'px', top: floating.top + 'px' }">
      {{ floating.text }}
    </div>
  </Teleport>
</template>

<style scoped>
.slip {
  position: relative;
  background: var(--ch-bg-warm);
  border: 1px solid var(--ch-border);
  padding: 22px 14px 14px;
  min-height: 120px;
  box-shadow:
    0 6px 16px -6px rgba(0, 0, 0, 0.05),
    0 2px 4px -1px rgba(0, 0, 0, 0.02);
}

.knob {
  position: absolute;
  top: -7px;
  left: 50%;
  transform: translateX(-50%);
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: var(--ch-primary);
  box-shadow:
    inset 0 1px 1.5px rgba(255, 255, 255, 0.55),
    inset 0 -1px 1.5px rgba(0, 0, 0, 0.18),
    0 2px 3px rgba(0, 0, 0, 0.25);
  z-index: 2;
}

/* 栏眉题：左标题 + 右阶段标记 */
.r-eyebrow {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-family: var(--ch-serif);
  font-size: 13px;
  font-weight: 600;
  color: var(--ch-body);
  letter-spacing: 0.1em;
  margin-bottom: 14px;
}
.stage {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  font-weight: 400;
  letter-spacing: 0.04em;
}
.s-identify { color: var(--ch-faint); }
.s-clarify { color: var(--ch-orange); }
.s-confirm { color: var(--ch-primary); }
.s-confirmed { color: var(--ch-muted); }
.s-dispatch { color: var(--ch-primary-2); }
.stage-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.6;
}
.s-clarify .stage-dot,
.s-confirm .stage-dot,
.s-dispatch .stage-dot {
  animation: dotPulse 1.4s ease-in-out infinite;
}
@keyframes dotPulse {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.35); }
}

.intent-goal {
  font-family: var(--ch-serif);
  font-size: 14.5px;
  font-weight: 600;
  color: var(--ch-text);
  line-height: 1.55;
  margin-bottom: 14px;
  position: relative;
}
.intent-goal.muted {
  color: var(--ch-muted);
  font-weight: 500;
}

/* 小节眉 + 引导虚线 */
.sec-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--ch-serif);
  font-size: 12px;
  font-weight: 500;
  color: var(--ch-muted);
  letter-spacing: 0.08em;
  margin-bottom: 9px;
}
.sec-title::after {
  content: "";
  flex: 1;
  height: 1px;
  background-image: linear-gradient(to right, var(--ch-border-2) 50%, transparent 0%);
  background-size: 5px 1px;
  background-repeat: repeat-x;
  background-position: left center;
}

/* 已知槽位：缩进挂靠在小节眉下 */
.slots {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 10px;
  row-gap: 7px;
  font-size: 12.5px;
  margin: 0 0 16px 14px;
  font-family: var(--ch-serif);
}
.slots .sk { color: var(--ch-muted); white-space: nowrap; }
.slots .sv {
  color: var(--ch-text);
  position: relative;
  min-width: 0;
}

/* 空 slot / 空 missing：淡省略号占位，保持框架不塌 */
.slots-placeholder,
.missing-placeholder {
  font-family: var(--ch-serif);
  font-size: 12.5px;
  color: var(--ch-faint);
  margin: 0 0 16px 14px;
  opacity: 0.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.missing-placeholder { margin-bottom: 0; }

.missing {
  font-size: 12.5px;
  color: var(--ch-orange-2);
  font-family: var(--ch-serif);
  line-height: 1.7;
  margin: 0 0 0 14px;
  position: relative;
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

/* 截断层：内层单行省略 */
.trunc {
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>

<style>
.intent-tip {
  position: fixed;
  transform: translate(0, -100%);
  max-width: 280px;
  padding: 6px 9px;
  background: var(--ch-text);
  color: var(--ch-surface);
  font-family: var(--ch-serif);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5;
  word-break: break-word;
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.18);
  pointer-events: none;
  z-index: 9999;
}
</style>