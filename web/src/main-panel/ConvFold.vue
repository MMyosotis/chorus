<script setup>
import { ref, computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  messages: { type: Array, default: () => [] },
})

const open = ref(false)

marked.setOptions({ breaks: true, gfm: true })

// 仅渲染普通对话消息，跳过注入的虚拟卡
const turns = computed(() =>
  props.messages
    .filter((msg) => msg.role && !msg.kind)
    .map((msg) => ({
      speaker: msg.role === 'user' ? '我' : '助手',
      cls: msg.role === 'user' ? 'user' : 'asst',
      html: msg.role === 'user' ? escapeText(msg.content) : renderMarkdown(msg.content),
    }))
)

const rounds = computed(() => turns.value.filter((t) => t.cls === 'user').length)

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
    <button class="conv-fold" :class="{ open }" @click="open = !open">
      <span class="chev">›</span>
      <span>与助手的讨论</span>
      <span class="round">{{ rounds }} 轮</span>
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
          <div class="text" v-html="turn.html"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.conv-fold-wrap {
  margin: 4px 0 0;
}

.conv-fold {
  border: none;
  background: none;
  font-family: var(--ch-serif);
  font-size: 13.5px;
  color: var(--ch-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  letter-spacing: 0.3px;
}

.conv-fold .chev {
  font-size: 10px;
  color: var(--ch-faint);
  display: inline-block;
  transition: transform 0.2s ease;
}

.conv-fold.open .chev {
  transform: rotate(90deg);
}

.conv-fold .round {
  color: var(--ch-faint);
  font-size: 12px;
}

.conv-body {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s ease, margin-top 0.3s ease;
}

.conv-body.show {
  max-height: 700px;
  margin-top: 18px;
}

.conv-body-inner {
  padding-left: 14px;
  border-left: 2px solid var(--ch-hair);
}

.conv-turn {
  margin-bottom: 22px;
}

.conv-turn:last-child {
  margin-bottom: 0;
}

.conv-turn .speaker {
  font-family: var(--ch-serif);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.4px;
  margin-bottom: 7px;
}

.conv-turn.user .speaker {
  color: var(--ch-muted);
}

.conv-turn.asst .speaker {
  color: var(--ch-primary-2);
}

.conv-turn .text {
  font-size: 14px;
  line-height: 1.75;
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
  font-family: var(--ch-serif);
  font-weight: 600;
  line-height: 1.4;
}
.conv-turn.asst .text :deep(h1) { font-size: 17px; }
.conv-turn.asst .text :deep(h2) { font-size: 15px; }
.conv-turn.asst .text :deep(h3) { font-size: 14px; }
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
