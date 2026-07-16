<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import IntentConfirmCard from './IntentConfirmCard.vue'

const props = defineProps({
  messages: { type: Array, default: () => [] },
  intentState: { type: Object, default: null },
})

const open = ref(false)

marked.setOptions({ breaks: true, gfm: true })

// 仅渲染普通对话消息，跳过注入的虚拟卡与无正文轮
const turns = computed(() =>
  props.messages
    .filter((msg) => msg.role && !msg.kind && (msg.content || '').trim())
    .map((msg) => ({
      speaker: msg.role === 'user' ? '我' : '助手',
      cls: msg.role === 'user' ? 'user' : 'asst',
      html: msg.role === 'user' ? escapeText(msg.content) : renderMarkdown(msg.content),
    }))
)

const rounds = computed(() => turns.value.filter((t) => t.cls === 'user').length)
const intentTurnIndex = computed(() => {
  if (!props.intentState) return -1
  for (let i = turns.value.length - 1; i >= 0; i -= 1) {
    if (turns.value[i].cls === 'asst') return i
  }
  return -1
})

function escapeText(text) {
  return (text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
}

function renderMarkdown(text) {
  return DOMPurify.sanitize(marked.parse(text || ''))
}
</script>

<template>
  <div class="conv-fold-wrap">
    <button type="button" class="conv-fold" :class="{ open }" :aria-expanded="open" @click="open = !open">
      <span class="proof-no">00</span>
      <span class="proof-main"><strong>与助手的前期讨论</strong><small>{{ rounds }} 轮往来 · 含已签发题旨</small></span>
      <span class="proof-mark"><b>已归档</b><em>{{ open ? '收起' : '展开' }}</em></span>
    </button>
    <div class="conv-body" :class="{ show: open }">
      <div class="conv-body-inner">
        <div
          v-for="(turn, idx) in turns"
          :key="idx"
          class="conv-turn"
          :class="turn.cls"
        >
          <div class="speaker">{{ turn.speaker }}</div>
          <template v-if="turn.cls === 'asst'">
            <div class="assistant-card">
              <div class="text" v-html="turn.html"></div>
              <IntentConfirmCard
                v-if="idx === intentTurnIndex"
                :state="intentState"
                archived
              />
            </div>
          </template>
          <div v-else class="text" v-html="turn.html"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.conv-fold-wrap {
  margin: 0;
  border-top: 1px solid rgba(27, 25, 22, .58);
  border-bottom: 1px solid rgba(27, 25, 22, .58);
}

.conv-fold {
  width: 100%;
  min-height: 62px;
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) auto;
  gap: 12px;
  align-items: center;
  padding: 0;
  border: none;
  background: rgba(255, 253, 248, .34);
  color: var(--ch-text);
  cursor: pointer;
  text-align: left;
}
.conv-fold:hover { background: rgba(239, 227, 219, .32); }

.proof-no { color: var(--ch-warm); font: 500 23px/1 var(--ch-serif); }
.proof-main strong { display: block; font: 600 14px/1.5 var(--ch-serif); }
.proof-main small { display: block; margin-top: 3px; color: var(--ch-muted); font: 500 var(--ch-chat-meta-size)/1.4 var(--ch-serif); letter-spacing: .015em; }
.proof-mark { display: inline-flex; align-items: center; gap: 8px; color: var(--ch-body); font: 500 var(--ch-chat-meta-size)/1.2 var(--ch-serif); letter-spacing: .02em; white-space: nowrap; }
.proof-mark b { color: var(--ch-green); font: 600 var(--ch-chat-meta-size)/1.2 var(--ch-serif); }
.proof-mark em { color: var(--ch-muted); font-style: normal; font-weight: 500; }
.proof-mark::after { content: ""; width: 0; height: 0; border-top: 3px solid transparent; border-bottom: 3px solid transparent; border-left: 5px solid currentColor; transform-origin: 45% 50%; transition: transform .24s ease; }
.conv-fold.open .proof-mark::after { transform: rotate(90deg); }

.conv-body {
  display: grid;
  grid-template-rows: minmax(0, 0fr);
  min-height: 0;
  overflow: hidden;
  transition: grid-template-rows .3s cubic-bezier(.22,.61,.36,1);
}

.conv-body.show {
  grid-template-rows: minmax(0, 1fr);
}

.conv-body-inner {
  min-height: 0;
  overflow: hidden;
  padding: 22px 24px;
  border-top: 1px solid var(--ch-border);
}
.conv-turn.asst .assistant-card > :deep(.intent-confirm) { margin: 18px 0 0; }

.conv-turn {
  margin-bottom: 22px;
}

.conv-turn:last-child {
  margin-bottom: 0;
}

.conv-turn .speaker {
  font-family: var(--ch-sans);
  font-size: var(--t-eyebrow);
  font-weight: 600;
  letter-spacing: 0.2em;
  margin-bottom: 7px;
}

.conv-turn.user .speaker {
  color: var(--ch-muted);
}

.conv-turn.asst .speaker {
  color: var(--ch-primary-2);
}

.conv-turn .text {
  font-family: var(--ch-serif);
  font-size: var(--t-body);
  line-height: 1.78;
  color: var(--ch-body);
}

.conv-turn.asst .text :deep(p) {
  margin: 0 0 12px;
}
.conv-turn.asst .text :deep(p:last-child) {
  margin-bottom: 0;
}
.conv-turn.asst .text :deep(strong) {
  font-weight: 600;
  color: var(--ch-text);
}
.conv-turn.asst .text :deep(ul),
.conv-turn.asst .text :deep(ol) {
  margin: 0 0 12px;
  padding-left: 22px;
}
.conv-turn.asst .text :deep(li) {
  margin: 3px 0;
}
.conv-turn.asst .text :deep(h1),
.conv-turn.asst .text :deep(h2),
.conv-turn.asst .text :deep(h3) {
  margin: 16px 0 10px;
  font-family: var(--ch-display);
  font-weight: 600;
  line-height: 1.4;
}
.conv-turn.asst .text :deep(h1) { font-size: var(--t-title); }
.conv-turn.asst .text :deep(h2) { font-size: var(--t-body); }
.conv-turn.asst .text :deep(h3) { font-size: var(--t-body); }
.conv-turn.asst .text :deep(blockquote) {
  margin: 8px 0;
  padding: 2px 12px;
  border-left: 3px solid var(--ch-border-2);
  color: var(--ch-muted);
}
.conv-turn.asst .text :deep(code) {
  background: var(--ch-bg-cool);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12.5px;
}
.conv-turn.asst .text :deep(a) {
  color: var(--ch-primary);
  text-decoration: underline;
}
</style>
