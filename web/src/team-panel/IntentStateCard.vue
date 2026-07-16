<script setup>
import { computed, ref } from 'vue'

const props = defineProps({ state: { type: Object, default: null } })
const expanded = ref(false)

const status = computed(() => props.state?.intent_status || 'empty')
const goal = computed(() => props.state?.goal || '')
const title = computed(() => props.state?.confirmation_summary?.title || goal.value || '正在理解你的需求')
const knownEntries = computed(() => Object.entries(props.state?.known_slots || {})
  .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== ''))
const missing = computed(() => props.state?.missing_slots || [])
const stageLabel = computed(() => ({
  empty: '识别中', capturing: '识别中', needs_clarification: '待补充',
  ready_to_confirm: '待确认', confirmed: '已确认', dispatched: '执行中',
}[status.value] || '识别中'))
const isLive = computed(() => ['empty', 'capturing', 'needs_clarification', 'dispatched'].includes(status.value))
const slotText = (value) => Array.isArray(value) ? value.join('、') : String(value)
</script>

<template>
  <section class="brief">
    <header class="rail-head">
      <span>题旨 · BRIEF</span>
      <span class="stage" :class="{ live: isLive }"><i></i><Transition name="stage-swap" mode="out-in"><span :key="stageLabel">{{ stageLabel }}</span></Transition></span>
    </header>
    <p class="goal">{{ title }}</p>

    <div class="sec-title brief-known-head">
      <span>已知</span>
      <button v-if="knownEntries.length > 4" type="button" :aria-expanded="expanded" @click="expanded = !expanded">
        {{ knownEntries.length }} 项 · {{ expanded ? '收起' : '展开全部' }}<i></i>
      </button>
      <small v-else>{{ knownEntries.length }} 项</small>
    </div>
    <div class="slots" :class="{ expanded }">
      <template v-for="([key, value], idx) in knownEntries" :key="key">
        <span class="key" :style="{ '--delay': `${idx * 22}ms` }">{{ key }}</span>
        <span class="value" :style="{ '--delay': `${idx * 22}ms` }" :title="slotText(value)">{{ slotText(value) }}</span>
      </template>
      <span v-if="!knownEntries.length" class="placeholder">待识别</span>
    </div>

    <template v-if="missing.length || ['empty', 'capturing', 'needs_clarification', 'ready_to_confirm'].includes(status)">
      <div class="sec-title missing-head"><span>待问</span></div>
      <p class="missing">{{ missing.length ? missing.join(' · ') : '待补充' }}</p>
    </template>
  </section>
</template>

<style scoped>
.brief { margin: 0; padding: 0; color: var(--ch-body); }
.rail-head {
  height: var(--ch-rail-head-height);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 9px;
  padding: 1px 2px 10px;
  border-bottom: 1px solid var(--ch-rail-rule);
  color: var(--ch-warm);
  font: var(--ch-rail-head-weight) var(--ch-rail-head-size)/var(--ch-rail-head-line) var(--ch-serif);
  letter-spacing: var(--ch-rail-head-tracking);
}
.stage { display: inline-flex; align-items: center; gap: 5px; color: var(--ch-primary); font: 500 var(--ch-rail-meta-size)/1 var(--ch-serif); letter-spacing: .05em; white-space: nowrap; }
.stage i { width: 5px; height: 5px; border-radius: 50%; background: currentColor; opacity: .7; }
.stage.live i { animation: breathe 1.7s ease-in-out infinite; }
@keyframes breathe { 0%,100% { opacity: .28; } 50% { opacity: 1; } }
.stage-swap-enter-active { transition: opacity .22s ease-out, transform .22s ease-out; }
.stage-swap-leave-active { transition: opacity .14s ease-in, transform .14s ease-in; }
.stage-swap-enter-from { opacity: 0; transform: translateY(3px); }
.stage-swap-leave-to { opacity: 0; transform: translateY(-2px); }
.goal { margin: 0 2px 12px; color: var(--ch-text); font: 600 var(--ch-rail-head-size)/1.7 var(--ch-serif); letter-spacing: .015em; }
.sec-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin: 0 2px 9px;
  padding-bottom: 7px;
  border-bottom: 1px dashed var(--ch-rail-dash);
  color: var(--ch-warm);
  font: 600 var(--ch-rail-section-size)/1.4 var(--ch-serif);
  letter-spacing: .05em;
}
.sec-title small { color: var(--ch-meta); font: 500 var(--ch-rail-meta-size)/1 var(--ch-serif); letter-spacing: .03em; }
.sec-title button { position: relative; min-height: 20px; display: inline-flex; align-items: center; gap: 6px; padding: 0; border: 0; background: transparent; color: var(--ch-warm); font: 500 var(--ch-rail-meta-size)/1.2 var(--ch-serif); cursor: pointer; }
.brief-known-head { align-items: center; }
.sec-title button i { width: 0; height: 0; border-top: 3px solid transparent; border-bottom: 3px solid transparent; border-left: 5px solid currentColor; transform-origin: 45% 50%; transition: transform .28s ease; }
.sec-title button[aria-expanded="true"] i { transform: rotate(90deg); }
.slots { display: grid; grid-template-columns: 40px minmax(0, 1fr); gap: 3px 12px; max-height: 93px; margin: 0 2px; overflow: hidden; font: 500 var(--ch-rail-body-size)/1.6 var(--ch-serif); transition: max-height .32s cubic-bezier(.22,.61,.36,1); }
.slots.expanded { max-height: 480px; }
.slots .key { color: var(--ch-meta); }
.slots .value { min-width: 0; overflow: hidden; color: var(--ch-body); text-overflow: ellipsis; white-space: nowrap; }
.slots > :nth-child(n + 9) { transition: opacity .22s ease, transform .3s cubic-bezier(.22,.61,.36,1); transition-delay: var(--delay); }
.slots:not(.expanded) > :nth-child(n + 9) { opacity: 0; transform: translateY(-5px); pointer-events: none; }
.slots.expanded > :nth-child(n + 9) { opacity: 1; transform: translateY(0); }
.placeholder { grid-column: 1/-1; color: var(--ch-meta); }
.missing-head { margin-top: 14px; }
.missing { margin: 0 2px; color: var(--ch-body); font: 500 var(--ch-rail-body-size)/1.55 var(--ch-serif); }
</style>
