<script setup>
import { ref } from 'vue'
import { ROLE_LABELS, stepOf } from '../team-panel/roleMeta.js'
import ScriptProof from './ScriptProof.vue'

defineProps({ tasks: { type: Array, default: () => [] } })
const openProofs = ref(new Set())
const labelOf = (task) => ({ idea: '选题', script: '写稿', image: '配图' }[task.agent_type] || ROLE_LABELS[task.agent_type])
const noteOf = (task) => {
  const a = task.artifacts || {}
  if (task.agent_type === 'idea') return `${(a.candidates || []).length} 个候选 · 已选定方向`
  if (task.agent_type === 'script') return `${(a.blocks || []).length} 个内容单元 · 完整定稿`
  if (task.agent_type === 'image') return `${(a.images || []).length} 张配图 · 视觉定稿`
  return '完整定稿'
}
const isProofOpen = (id) => openProofs.value.has(id)
function toggleProof(id) {
  const next = new Set(openProofs.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  openProofs.value = next
}
</script>

<template>
  <section class="proof-register">
    <header class="register-head"><span>已确认校样 · PROOF REGISTER</span><small>{{ tasks.length }} 件 · 按签认顺序</small></header>
    <TransitionGroup name="proof-insert" tag="div" class="proof-list">
      <details v-for="task in tasks" :key="task.id" class="proof" open :class="{ 'is-open': isProofOpen(task.id) }">
        <summary :aria-expanded="isProofOpen(task.id)" @click.prevent="toggleProof(task.id)">
          <span class="proof-no">{{ String(stepOf(task.agent_type)).padStart(2, '0') }}</span>
          <span class="proof-main"><strong>{{ labelOf(task) }} · {{ task.title || ROLE_LABELS[task.agent_type] }}</strong><small>{{ noteOf(task) }}</small></span>
          <span class="proof-mark"><b>已签认</b><em><span class="closed">展开</span><span class="opened">收起</span></em></span>
        </summary>
        <div class="proof-body-fold" :class="{ show: isProofOpen(task.id) }">
          <div class="proof-body">
            <template v-if="task.agent_type === 'idea'">
              <div class="candidates" aria-label="已确认选题候选">
                <article v-for="(c, i) in task.artifacts?.candidates || []" :key="c.index" class="candidate" :class="{ selected: task.artifacts?.selected === c.index }">
                  <span class="cand-no">PITCH {{ String(i + 1).padStart(2, '0') }}</span>
                  <h4>{{ c.title }}</h4>
                  <small>{{ c.angle }}</small>
                  <p>{{ c.reason }}</p>
                  <span v-if="task.artifacts?.selected === c.index" class="choice">拟采用 · EDITOR'S PICK</span>
                </article>
              </div>
            </template>
            <ScriptProof v-else-if="task.agent_type === 'script'" :blocks="task.artifacts?.blocks || []" compact />
            <div v-else-if="task.agent_type === 'image'" class="images">
              <figure v-for="(img, i) in task.artifacts?.images || []" :key="i"><img :src="img.url" :alt="img.caption || ''"><figcaption><b>FIG. {{ String(i + 1).padStart(2, '0') }}</b><span>{{ img.caption }}</span></figcaption></figure>
            </div>
          </div>
        </div>
      </details>
    </TransitionGroup>
  </section>
</template>

<style scoped>
.proof-register { margin: 40px 0 0; }
.register-head { display: flex; align-items: center; gap: 10px; margin-bottom: 13px; color: var(--ch-warm); font: 600 var(--ch-chat-label-size)/1 var(--ch-serif); letter-spacing: .08em; }.register-head::before { content: ""; width: 7px; height: 7px; border: 1.5px solid rgba(141, 51, 37, .82); transform: rotate(45deg); }.register-head small { margin-left: auto; color: var(--ch-muted); font: 500 var(--ch-chat-meta-size)/1.2 var(--ch-serif); letter-spacing: .02em; }
.proof-list { border-top: 1px solid rgba(27, 25, 22, .58); border-bottom: 1px solid rgba(27, 25, 22, .58); }.proof { background: rgba(255, 253, 248, .34); border-bottom: 1px dotted rgba(110, 103, 93, .52); }.proof:last-child { border-bottom: 0; }.proof summary { min-height: 62px; display: grid; grid-template-columns: 44px minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 0; list-style: none; cursor: pointer; }.proof summary::-webkit-details-marker { display: none; }
.proof-insert-enter-active { transition: opacity .28s ease-out, transform .28s cubic-bezier(.2,.72,.25,1); }
.proof-insert-enter-from { opacity: 0; transform: translateY(9px); }
.proof-insert-move { transition: transform .28s cubic-bezier(.2,.72,.25,1); }
.proof-body-fold { display: grid; grid-template-rows: minmax(0, 0fr); min-height: 0; overflow: hidden; transition: grid-template-rows .3s cubic-bezier(.22,.61,.36,1); }
.proof-body-fold.show { grid-template-rows: minmax(0, 1fr); }
.proof summary:hover { background: rgba(239, 227, 219, .32); }
.proof-no { color: var(--ch-warm); font: 500 23px/1 var(--ch-serif); }
.proof-main strong { display: block; font: 600 14px/1.5 var(--ch-serif); }
.proof-main small { display: block; margin-top: 3px; color: var(--ch-muted); font: 500 var(--ch-chat-meta-size)/1.4 var(--ch-serif); letter-spacing: .015em; }
.proof-mark { display: inline-flex; align-items: center; gap: 8px; color: var(--ch-body); font: 500 var(--ch-chat-meta-size)/1.2 var(--ch-serif); letter-spacing: .02em; white-space: nowrap; }
.proof-mark b { color: var(--ch-green); font: 600 var(--ch-chat-meta-size)/1.2 var(--ch-serif); }
.proof-mark em { color: var(--ch-muted); font-style: normal; font-weight: 500; }
.proof-mark::after { content: ""; width: 0; height: 0; border-top: 3px solid transparent; border-bottom: 3px solid transparent; border-left: 5px solid currentColor; transform-origin: 45% 50%; transition: transform .24s ease; }
.proof.is-open .proof-mark::after { transform: rotate(90deg); }
.opened { display: none; }.proof.is-open .closed { display: none; }.proof.is-open .opened { display: inline; }
.proof-body { min-height: 0; position: relative; overflow: hidden; padding: 22px 24px; border-top: 1px solid var(--ch-border); }
.candidates { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0; border: 1px solid var(--ch-border); }
.candidate { min-width: 0; min-height: 180px; display: block; padding: 18px; border-right: 1px solid var(--ch-border); background: rgba(255, 253, 248, .45); }
.candidate:last-child { border-right: 0; }
.candidate.selected { background: var(--ch-selection-soft); box-shadow: inset 0 -3px var(--ch-warm); }
.cand-no { display: block; color: var(--ch-meta); font: 600 10px/1.2 var(--ch-serif); font-variant-numeric: tabular-nums; letter-spacing: .16em; }
.candidate.selected .cand-no { color: var(--ch-warm); }
.candidate h4 { margin: 16px 0 8px; font: 600 17px/1.5 var(--ch-serif); }
.candidate small { display: block; color: var(--ch-body); font: 500 12px/1.7 var(--ch-sans); }
.candidate p { margin: 12px 0 0; color: var(--ch-muted); font: 500 12px/1.7 var(--ch-serif); }
.choice { display: block; margin-top: 12px; color: var(--ch-warm); font: 600 9px/1.3 var(--ch-sans); }
.images { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }.images figure { margin: 0; }.images img { width: 100%; aspect-ratio: 1/1; display: block; object-fit: cover; }.images figcaption { display: flex; align-items: baseline; justify-content: center; gap: 6px; margin-top: 7px; color: var(--ch-body); font: 500 10px/1.5 var(--ch-serif); text-align: center; }.images figcaption b { color: var(--ch-warm); white-space: nowrap; }
@media (max-width: 700px) { .proof summary { grid-template-columns: 36px 1fr; }.proof-mark { grid-column: 2; text-align: left; }.images { grid-template-columns: 1fr; } }
</style>
