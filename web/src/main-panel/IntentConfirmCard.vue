<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  state: { type: Object, default: null },
  archived: { type: Boolean, default: false },
})
const emit = defineEmits(['confirm', 'revise'])
const locking = ref(false)
const decision = ref('')

const entries = computed(() => Object.entries(props.state?.known_slots || {})
  .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== ''))
const valueText = (value) => Array.isArray(value) ? value.join('、') : String(value)
function findSlot(words, fallback = '待确认') {
  const item = entries.value.find(([key]) => words.some((word) => key.includes(word)))
  return item ? valueText(item[1]) : fallback
}
const specs = computed(() => [
  ['PLATFORM / 平台', findSlot(['平台'])],
  ['FORMAT / 体裁', findSlot(['体裁', '形式'])],
  ['STYLE / 风格', findSlot(['风格', '语气'])],
  ['IMAGES / 配图', findSlot(['配图', '图片', '图像'])],
])
const specKeys = ['平台', '体裁', '形式', '风格', '语气', '配图', '图片', '图像', '主题']
const notes = computed(() => {
  const rest = entries.value
    .filter(([key]) => !specKeys.some((word) => key.includes(word)))
  return rest.length ? rest : [['补充', '自由发挥']]
})
const title = computed(() => props.state?.confirmation_summary?.title || '请确认这次创作方向')
const deck = computed(() => props.state?.goal || '签发后，编辑部将按此建立完整创作计划。')

function submitDecision() {
  if (locking.value || !decision.value) return
  locking.value = true
  emit(decision.value === 'confirm' ? 'confirm' : 'revise')
}
</script>

<template>
  <section class="intent-confirm">
    <header class="commission-mast">
      <div class="confirm-kicker">选题签发 <small>STORY COMMISSION</small></div>
      <div class="commission-no">VOL. 07 · NO. 001</div>
      <div class="commission-status" :class="{ archived }"><i></i>{{ archived ? '已签发' : '待签发' }}</div>
    </header>

    <h2 class="confirm-title">{{ title }}</h2>
    <p class="commission-deck">{{ deck }}</p>

    <div class="commission-index">
      <span v-for="([label, value]) in specs" :key="label"><small>{{ label }}</small><b :title="value">{{ value }}</b></span>
    </div>

    <div class="notes-head"><span>编辑批注 · NOTES</span><small>{{ notes.length }} 项 · {{ archived ? '已确认' : '待确认' }}</small></div>
    <div class="notes-grid">
      <span v-for="([label, value]) in notes" :key="label"><b>{{ label }}</b><em :title="valueText(value)">{{ valueText(value) }}</em></span>
    </div>

    <footer class="actions">
      <span class="signoff" :class="{ archived }">{{ archived ? '用户已确认 · 创作计划已建立' : '签发后建立创作计划' }}</span>
      <template v-if="!archived">
        <fieldset class="choices" aria-label="选题签发决定">
          <label><input v-model="decision" type="radio" value="confirm" :disabled="locking"><span class="box" aria-hidden="true"></span><span>确认签发</span></label>
          <label><input v-model="decision" type="radio" value="revise" :disabled="locking"><span class="box" aria-hidden="true"></span><span>退回补充</span></label>
        </fieldset>
        <button class="submit" :disabled="locking || !decision" @click="submitDecision">确认决定</button>
      </template>
    </footer>
  </section>
</template>

<style scoped>
.intent-confirm {
  position: relative;
  width: 100%;
  padding: 0 16px 18px;
  border-top: 1px solid rgba(110, 103, 93, .62);
  border-right: 0;
  border-bottom: 1px solid rgba(110, 103, 93, .62);
  border-left: 0;
  background: var(--ch-slip-soft);
  box-shadow: none;
}
.commission-mast { min-height: 44px; display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 14px; border-bottom: 3px double rgba(27, 25, 22, .82); color: var(--ch-body); }
.confirm-kicker { display: flex; align-items: baseline; gap: 8px; color: var(--ch-warm); font: 600 13px/1.25 var(--ch-serif); letter-spacing: .05em; }
.confirm-kicker small, .commission-no { color: var(--ch-body); font: 500 10px/1.2 var(--ch-sans); letter-spacing: .07em; }
.commission-status { display: inline-flex; align-items: center; gap: 6px; color: var(--ch-warm); font: 600 11px/1 var(--ch-serif); letter-spacing: .03em; }
.commission-status i { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.commission-status.archived, .signoff.archived { color: var(--ch-green); }
.confirm-title { max-width: calc(100% - 76px); margin: 18px 0 6px; color: var(--ch-text); font: 600 21px/1.48 var(--ch-serif); letter-spacing: .015em; }
.commission-deck { max-width: calc(100% - 76px); margin: 0 0 17px; color: var(--ch-body); font: 500 13px/1.8 var(--ch-serif); letter-spacing: .015em; }
.commission-index { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); border-top: 1px solid var(--ch-border-2); border-bottom: 1px solid var(--ch-border-2); }
.commission-index > span { min-width: 0; padding: 11px 10px; }
.commission-index > span + span { border-left: 1px solid var(--ch-border-2); }
.commission-index small, .commission-index b { display: block; }
.commission-index small { margin-bottom: 6px; color: var(--ch-muted); font: 500 9px/1.25 var(--ch-sans); letter-spacing: .055em; }
.commission-index b { overflow: hidden; color: var(--ch-text); font: 600 12px/1.4 var(--ch-serif); text-overflow: ellipsis; white-space: nowrap; }
.notes-head { min-height: 42px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 0 2px; border-bottom: 1px solid var(--ch-border-2); color: var(--ch-body); font: 600 11px/1 var(--ch-serif); letter-spacing: .06em; }
.notes-head small { color: var(--ch-muted); font: 500 10px/1 var(--ch-serif); letter-spacing: .04em; }
.notes-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border-bottom: 1px solid var(--ch-border-2); }
.notes-grid > span { min-width: 0; display: grid; grid-template-columns: 38px minmax(0, 1fr); align-items: center; gap: 8px; padding: 10px 12px; }
.notes-grid > span:nth-child(even) { border-left: 1px dotted rgba(110, 103, 93, .42); }
.notes-grid > span:nth-child(n + 3) { border-top: 1px dotted rgba(110, 103, 93, .42); }
.notes-grid b { color: var(--ch-warm); font: 600 12px/1.4 var(--ch-serif); letter-spacing: .04em; }
.notes-grid em { min-width: 0; overflow: hidden; color: var(--ch-body); font: 500 13px/1.4 var(--ch-serif); font-style: normal; letter-spacing: .01em; text-overflow: ellipsis; white-space: nowrap; }
.actions { display: flex; align-items: center; gap: 12px; margin-top: 15px; }
.signoff { margin-right: auto; color: var(--ch-body); font: 500 11px/1.55 var(--ch-serif); }
.choices, .choices label { display: flex; align-items: center; }
.choices { gap: 14px; margin: 0; padding: 0; border: 0; }
.choices label { position: relative; min-height: 40px; gap: 7px; color: var(--ch-text); font: 500 13px/1 var(--ch-serif); white-space: nowrap; cursor: pointer; }
.choices input { position: absolute; width: 1px; height: 1px; margin: 0; opacity: 0; pointer-events: none; }
.box { position: relative; width: 16px; height: 16px; flex: 0 0 16px; border: 1px solid rgba(27, 25, 22, .68); background: rgba(255, 253, 248, .32); }
.choices input:checked + .box { border-color: var(--ch-warm); }
.choices input:checked + .box::after { content: ""; position: absolute; inset: 4px; background: var(--ch-warm); }
.choices label:has(input:checked) { color: var(--ch-warm); font-weight: 600; }
.choices input:focus-visible + .box { outline: 2px solid var(--ch-primary); outline-offset: 3px; }
.choices label:has(input:disabled) { cursor: default; }
.submit { height: 40px; min-height: 40px; padding: 0 3px; border: 0; background: transparent; color: var(--ch-warm); font: 600 13px/1 var(--ch-serif); text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 5px; cursor: pointer; }
.submit:hover:not(:disabled) { color: var(--ch-text); }
.submit:disabled { color: var(--ch-faint); text-decoration-color: transparent; cursor: default; }
@media (max-width: 700px) {
  .commission-mast { grid-template-columns: 1fr auto; }
  .commission-no { display: none; }
  .commission-index { grid-template-columns: repeat(2, 1fr); }
  .commission-index > span:nth-child(3) { border-left: 0; }
  .commission-index > span:nth-child(n+3) { border-top: 1px solid var(--ch-border-2); }
  .actions { align-items: flex-start; flex-wrap: wrap; }
  .signoff { flex-basis: 100%; }
  .choices { flex-basis: 100%; }
}
</style>
