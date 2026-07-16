<script setup>
import { computed, ref } from 'vue'
import { cancelPipeline, confirmTask, retryTask } from '../api.js'
import { stepOf } from '../team-panel/roleMeta.js'
import PostCard from './PostCard.vue'
import StageHeader from './StageHeader.vue'

const props = defineProps({ task: { type: Object, required: true }, sessionId: { type: String, required: true } })
const emit = defineEmits(['confirmed', 'retried', 'cancelled'])
const artifacts = computed(() => props.task.artifacts || {})
const candidates = computed(() => artifacts.value.candidates || [])
const selectedIdx = ref(props.task.artifacts?.selected ?? null)
const decision = ref('')
const feedback = ref('')
const busy = ref(false)
const error = ref('')
const needSelect = computed(() => props.task.agent_type === 'idea')
const selectedPitch = computed(() => {
  const position = (artifacts.value.candidates || []).findIndex((item) => item.index === selectedIdx.value)
  return position < 0 ? null : position + 1
})
const scriptChars = computed(() => {
  const explicit = props.task.progress?.composing_chars || props.task.artifacts?.char_count
  if (explicit) return explicit
  return (artifacts.value.blocks || []).reduce((sum, block) => sum + String(block.text || '').length, 0)
})

const meta = computed(() => ({
  idea: { cn: '选题会审 · 等你定案', en: 'EDITORIAL PITCH REVIEW', status: `${(artifacts.value.candidates || []).length || 3} 案 · 待定案`, folio: 'PITCH PROOF', approve: '准予采用', revise: '退回重提', target: selectedPitch.value == null ? 'PITCH · 待选择' : `PITCH ${String(selectedPitch.value).padStart(2, '0')}` },
  script: { cn: '文案编辑 · 等你过目', en: 'COPY EDITING REVIEW', status: '待确认', folio: `COPY PROOF${scriptChars.value ? ` · ${scriptChars.value} 字` : ''}`, approve: '确认定稿', revise: '退回重写', target: 'VERSION 01' },
  image: { cn: '视觉编辑 · 等你过目', en: 'VISUAL EDITING REVIEW', status: `${(artifacts.value.images || []).length || 3} 帧 · 待确认`, folio: 'IMAGE PROOF · 4:5', approve: '确认配图', revise: '退回重绘', target: 'FIG. 01—03' },
  finalize: { cn: '汇总编辑 · 等你过目', en: 'FINAL ASSEMBLY REVIEW', status: '待确认', folio: 'FINAL PROOF', approve: '确认成品', revise: '退回调整', target: 'FINAL COPY' },
}[props.task.agent_type] || { cn: '校样审阅', en: 'EDITORIAL REVIEW', folio: 'PROOF', approve: '确认', revise: '退回', target: '当前校样' }))
const stepNo = computed(() => String(stepOf(props.task.agent_type)).padStart(2, '0'))

async function submitDecision() {
  if (!decision.value) return
  if (decision.value === 'approve') return onConfirm()
  return onRetry()
}
async function onConfirm() {
  if (needSelect.value && selectedIdx.value == null) { error.value = '请先选择一个候选'; return }
  busy.value = true; error.value = ''
  try { await confirmTask(props.task.id, needSelect.value ? selectedIdx.value : null); emit('confirmed', props.task.id) }
  catch (e) { error.value = e.detail || e.message }
  finally { busy.value = false }
}
async function onRetry() {
  busy.value = true; error.value = ''
  try { await retryTask(props.task.id, feedback.value || ''); emit('retried', props.task.id) }
  catch (e) { error.value = e.detail || e.message }
  finally { busy.value = false }
}
async function onCancel() {
  if (!confirm('放弃整条创作？已确认的校样会保留。')) return
  busy.value = true; error.value = ''
  try { await cancelPipeline(props.sessionId); emit('cancelled', props.sessionId) }
  catch (e) { error.value = e.detail || e.message }
  finally { busy.value = false }
}
</script>

<template>
  <section class="hil-card" :class="`review-${task.agent_type}`">
    <StageHeader :number="stepNo" :title="meta.cn" :english="meta.en" :status="meta.status || '待确认'" />

    <div class="proof-sheet">
      <header class="proof-furniture"><span>{{ meta.folio }}</span><span>VOL. 07 · CURRENT DRAFT</span><span>P. {{ stepNo }}</span></header>
      <div class="proof-canvas">
        <div v-if="task.agent_type === 'idea'" class="candidates" :class="`count-${Math.min(candidates.length, 5)}`" role="radiogroup" aria-label="选题候选">
          <button v-for="(c, idx) in candidates" :key="c.index" type="button" class="cand" :class="{ selected: selectedIdx === c.index }" role="radio" :aria-checked="selectedIdx === c.index" @click="selectedIdx = c.index">
            <span class="cand-no">PITCH {{ String(idx + 1).padStart(2, '0') }}</span>
            <h4>{{ c.title }}</h4><small v-if="c.angle">{{ c.angle }}</small><p v-if="c.reason">{{ c.reason }}</p>
            <span class="choice">拟采用 · EDITOR'S PICK</span>
          </button>
        </div>

        <article v-else-if="task.agent_type === 'script'" class="script-proof">
          <div class="proof-kicker">COPY PROOF · VERSION 01</div>
          <template v-for="(b, i) in artifacts.blocks || []" :key="i">
            <h3 v-if="b.kind === 'title'">{{ b.text }}</h3>
            <h4 v-else-if="b.kind === 'heading'">{{ b.text }}</h4>
            <blockquote v-else-if="b.kind === 'quote'">{{ b.text }}</blockquote>
            <p v-else>{{ b.text }}</p>
          </template>
        </article>

        <div v-else-if="task.agent_type === 'image'" class="img-grid">
          <figure v-for="(img, i) in artifacts.images || []" :key="i" class="img-cell">
            <img :src="img.url" :alt="img.caption || ''" loading="lazy" />
            <figcaption><b>FIG. {{ String(i + 1).padStart(2, '0') }}</b><span>{{ img.caption }}</span></figcaption>
          </figure>
        </div>

        <PostCard v-else-if="task.agent_type === 'finalize'" :task="task" review />
      </div>
    </div>

    <footer class="review-decision" :data-decision="decision || 'none'">
      <div class="decision-main">
        <div class="decision-head"><span>校样批签 · SIGN-OFF</span><i></i><small>{{ meta.target }} · {{ decision ? (decision === 'approve' ? '准予采用' : '退改') : '待签' }}</small></div>
        <div class="actions">
          <fieldset class="choices">
            <label><input v-model="decision" type="radio" value="approve"><span class="box"></span><span>{{ meta.approve }}</span></label>
            <label><input v-model="decision" type="radio" value="revise"><span class="box"></span><span>{{ meta.revise }}</span></label>
          </fieldset>
          <button class="submit" :disabled="busy || !decision" @click="submitDecision">确认批签</button>
          <button class="cancel" :disabled="busy" @click="onCancel">放弃</button>
        </div>
      </div>
      <div v-if="decision === 'revise'" class="notes">
        <div><label for="review-feedback">退改批注</label><small>选择退回后填写</small></div>
        <textarea id="review-feedback" v-model="feedback" placeholder="写下希望本阶段重新处理的方向" rows="2"></textarea>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
    </footer>
  </section>
</template>

<style scoped>
.hil-card { margin: 0 0 24px; padding: 0 0 24px; border: 0; }
.proof-sheet { border-top: 2px solid rgba(27, 25, 22, .9); border-bottom: 1px solid rgba(27, 25, 22, .62); background: rgba(255, 253, 248, .2); }
.proof-furniture { height: 31px; display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 12px; padding: 0 2px; border-bottom: 1px solid rgba(27, 25, 22, .48); color: var(--ch-muted); font: 500 var(--ch-chat-meta-size)/1 var(--ch-serif); font-variant-numeric: lining-nums tabular-nums; letter-spacing: .12em; }
.proof-furniture span:nth-child(2) { text-align: center; }.proof-furniture span:last-child { text-align: right; }
.proof-canvas { padding: 22px 0 12px; }
.review-idea .proof-canvas { padding: 0; }
.review-image .proof-sheet { border-bottom: 0; }
.candidates { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); }
.cand { grid-column: span 2; min-height: 230px; display: flex; flex-direction: column; padding: 20px 18px 18px; border: 0; border-right: 1px solid var(--ch-border-2); background: rgba(255, 253, 248, .18); color: var(--ch-text); text-align: left; cursor: pointer; transition: background .2s; }
.candidates.count-1 .cand { grid-column: span 6; border-right: 0; }
.candidates.count-2 .cand, .candidates.count-4 .cand { grid-column: span 3; }
.candidates.count-2 .cand:nth-child(2n), .candidates.count-4 .cand:nth-child(2n) { border-right: 0; }
.candidates.count-4 .cand:nth-child(n + 3) { border-top: 1px solid var(--ch-border-2); }
.candidates.count-3 .cand:nth-child(3), .candidates.count-5 .cand:nth-child(3) { border-right: 0; }
.candidates.count-5 .cand:nth-child(n + 4) { grid-column: span 3; border-top: 1px solid var(--ch-border-2); }
.candidates.count-5 .cand:nth-child(5) { border-right: 0; }
.cand:focus-visible { position: relative; z-index: 1; outline: 2px solid var(--ch-primary); outline-offset: -3px; }
.cand:last-child { border-right: 0; }.cand:hover { background: rgba(221, 213, 200, .2); }.cand.selected { background: var(--ch-selection-soft); box-shadow: inset 0 -2px var(--ch-warm); }
.cand-no { color: var(--ch-muted); font: 600 var(--ch-chat-meta-size)/1.2 var(--ch-serif); font-variant-numeric: lining-nums tabular-nums; letter-spacing: .14em; }.cand.selected .cand-no { color: var(--ch-warm); }
.cand h4 { margin: 14px 0 7px; font: 600 var(--ch-chat-subtitle-size)/1.55 var(--ch-serif); }.cand small { color: var(--ch-body); font: 500 var(--ch-chat-label-size)/1.6 var(--ch-serif); }.cand p { margin: 11px 0 0; color: var(--ch-body); font: 500 var(--ch-chat-note-size)/1.8 var(--ch-serif); }
.choice { visibility: hidden; margin-top: auto; padding-top: 10px; color: var(--ch-warm); font: 600 var(--ch-chat-meta-size)/1.3 var(--ch-serif); }.cand.selected .choice { visibility: visible; }
.script-proof { padding: 0 4px; }.proof-kicker { color: var(--ch-warm); font: 600 9px/1.3 var(--ch-sans); letter-spacing: .14em; }.script-proof h3 { margin: 6px 0 22px; font: 700 28px/1.35 var(--ch-serif); }.script-proof h4 { margin: 22px 0 7px; font: 600 15px/1.55 var(--ch-serif); }.script-proof p { margin: 7px 0; color: var(--ch-body); font: 500 14px/1.95 var(--ch-serif); }.script-proof blockquote { margin: 20px 0; padding: 14px 18px; border-top: 1px solid var(--ch-border-2); border-bottom: 1px solid var(--ch-border-2); font: 600 16px/1.75 var(--ch-serif); text-align: center; }
.script-proof p:first-of-type::first-letter { float: left; margin: 6px 8px 0 0; color: var(--ch-warm); font: 700 42px/.86 var(--ch-serif); }
.img-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding: 0 2px; }.img-cell { margin: 0; }.img-cell img { width: 100%; aspect-ratio: 1/1; display: block; object-fit: cover; box-shadow: 0 0 0 1px rgba(27, 25, 22, .2); }.img-cell figcaption { display: flex; align-items: baseline; justify-content: center; gap: 7px; margin-top: 9px; padding: 8px 4px 0; border-top: 1px solid var(--ch-border-2); color: var(--ch-body); font: 500 10px/1.55 var(--ch-serif); text-align: center; }.img-cell figcaption b { color: var(--ch-warm); font-weight: 600; white-space: nowrap; }
@media (min-width: 781px) { .img-grid { gap: 14px; }.img-cell figcaption { font-size: 11px; } }
.review-decision { margin-top: 8px; }.decision-main { min-height: 44px; display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: center; gap: 16px; }.decision-head { min-width: 0; height: 44px; display: flex; align-items: center; gap: 9px; color: var(--ch-warm); font: 600 13px/1 var(--ch-serif); letter-spacing: .04em; }.decision-head i { min-width: 14px; flex: 1; border-top: 1px dotted rgba(110, 103, 93, .48); }.decision-head small { overflow: hidden; color: var(--ch-muted); font: 500 13px/1 var(--ch-serif); text-overflow: ellipsis; white-space: nowrap; }
.actions, .choices, .choices label { display: flex; align-items: center; }.actions { gap: 3px; }.choices { gap: 13px; margin: 0 14px 0 0; padding: 0; border: 0; }.choices label { position: relative; height: 44px; gap: 7px; font: 500 13px/1 var(--ch-serif); white-space: nowrap; cursor: pointer; }.choices input { position: absolute; opacity: 0; }.box { position: relative; width: 16px; height: 16px; border: 1px solid rgba(27, 25, 22, .68); }.choices input:checked + .box { border-color: var(--ch-warm); }.choices input:checked + .box::after { content: ""; position: absolute; inset: 4px; background: var(--ch-warm); }.choices label:has(input:checked) { color: var(--ch-warm); font-weight: 600; }
.choices input:focus-visible + .box { outline: 2px solid var(--ch-primary); outline-offset: 3px; }
.submit, .cancel { height: 44px; min-height: 44px; padding: 0 5px; border: 0; background: transparent; font: 500 13px/1 var(--ch-serif); cursor: pointer; }.submit { color: var(--ch-warm); text-decoration: underline; text-underline-offset: 5px; }.submit:disabled { color: var(--ch-faint); text-decoration: none; cursor: default; }.cancel { color: var(--ch-muted); }.notes { margin-top: 10px; }.notes > div { display: flex; justify-content: space-between; margin-bottom: 6px; }.notes label { font: 600 10px/1.3 var(--ch-serif); }.notes small { color: var(--ch-muted); font: 500 9px/1.3 var(--ch-serif); }.notes textarea { width: 100%; min-height: 72px; padding: 12px 14px; border: 1px solid var(--ch-border-2); border-radius: 0; background: rgba(255, 253, 248, .65); color: var(--ch-text); font: 500 13px/1.65 var(--ch-serif); resize: vertical; }.error { margin: 8px 0 0; color: var(--ch-red); font: 500 11px/1.5 var(--ch-serif); }
@media (max-width: 760px) { .candidates { grid-template-columns: 1fr; }.candidates .cand { grid-column: auto; min-height: 0; border-top: 0; border-right: 0; border-bottom: 1px solid var(--ch-border-2); }.candidates .cand:last-child { border-bottom: 0; }.decision-main { grid-template-columns: 1fr; }.actions { flex-wrap: wrap; }.choices { flex-basis: 100%; }.proof-furniture { grid-template-columns: 1fr auto; }.proof-furniture span:nth-child(2) { display: none; } }
</style>
