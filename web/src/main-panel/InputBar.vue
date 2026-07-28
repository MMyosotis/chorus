<script setup>
import { ref, nextTick, computed } from 'vue'

const props = defineProps({
  streaming: { type: Boolean, default: false },
  hasActiveTask: { type: Boolean, default: false },
  awaitingConfirm: { type: Boolean, default: false },
  archived: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])

const inputText = ref('')
const textarea = ref(null)

const disabled = computed(() => props.streaming || props.hasActiveTask || props.awaitingConfirm || props.archived)
const placeholder = computed(() => {
  if (props.archived) return '本篇已定稿存档，请新建会话开始下一篇'
  if (props.awaitingConfirm) return '请先确认或调整上方意图卡片'
  if (props.hasActiveTask) return '执行中，暂时不能输入；确认节点或完成后恢复'
  if (props.streaming) return '助手正在回复，请稍候…'
  return '输入你的想法或任务…'
})

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function send() {
  const text = inputText.value.trim()
  if (!text || disabled.value) return
  emit('send', text)
  inputText.value = ''
  nextTick(() => adjustHeight())
}

function adjustHeight() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  const maxH = 160
  el.style.height = Math.min(el.scrollHeight, maxH) + 'px'
}

function focus() {
  textarea.value?.focus()
}

defineExpose({ focus })
</script>

<template>
  <div class="input-bar" :class="{ locked: hasActiveTask || awaitingConfirm, archived }">
    <textarea
      ref="textarea"
      v-model="inputText"
      class="input-field"
      :placeholder="placeholder"
      rows="1"
      :disabled="disabled"
      @keydown="handleKeydown"
      @input="adjustHeight"
    ></textarea>
    <div class="input-toolbar">
      <div class="tool-group">
        <button class="tool-btn" type="button" aria-label="附件" :disabled="disabled">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m20.5 11.5-8.9 8.9a6 6 0 0 1-8.5-8.5l9.6-9.6a4 4 0 0 1 5.7 5.7l-9.6 9.6a2 2 0 1 1-2.8-2.8l8.9-8.9"/></svg>
          <span>附件</span>
        </button>
        <button class="tool-btn" type="button" aria-label="联网搜索" :disabled="disabled">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
          <span>联网搜索</span>
        </button>
        <button class="tool-btn" type="button" aria-label="智能推荐" :disabled="disabled">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M12 2a7 7 0 0 0-4 12.7c.6.5 1 1.3 1 2.1V17h6v-.2c0-.8.4-1.6 1-2.1A7 7 0 0 0 12 2z"/></svg>
          <span>智能推荐</span>
        </button>
      </div>
      <div class="tool-group right">
        <button class="icon-btn" type="button" aria-label="语音输入" :disabled="disabled">
          <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10a7 7 0 0 0 14 0"/><line x1="12" y1="19" x2="12" y2="22"/></svg>
        </button>
        <button
          class="send-btn"
          :disabled="disabled || !inputText.trim()"
          @click="send"
          aria-label="发送"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5m0 0-6 6m6-6 6 6"/></svg>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.input-bar {
  flex-shrink: 0;
  position: relative;
  width: calc(100% - 32px);
  margin: 0 auto;
  padding: 24px 24px 16px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: var(--ch-surface);
  border: 1px solid var(--ch-border);
  border-radius: 24px;
  box-shadow: var(--ch-shadow-soft);
}

@media (min-width: 781px) {
  .input-bar {
    width: 100%;
    margin: 0;
  }
}

.input-field {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  min-height: 44px;
  padding: 0;
  font-family: var(--ch-font-sans);
  font-size: 15px;
  line-height: 1.6;
  resize: none;
  max-height: 160px;
  overflow-y: auto;
  scrollbar-width: none;
  color: var(--ch-text);
}
.input-field::-webkit-scrollbar { display: none; }
.input-field::placeholder { color: var(--ch-text-faint); }
.input-field:disabled { cursor: not-allowed; }
.input-field:disabled::placeholder {
  color: var(--ch-text-faint);
  animation: busyDots 1.4s steps(4, end) infinite;
}
.input-bar.archived .input-field:disabled::placeholder { animation: none; }

@keyframes busyDots {
  0% { opacity: 0.5; }
  50% { opacity: 1; }
  100% { opacity: 0.5; }
}

.input-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0;
}

.tool-group {
  display: flex;
  align-items: center;
  gap: var(--ch-space-3);
}
.tool-group.right {
  gap: 6px;
}

.tool-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--ch-text-faint);
  font: 400 13px/1 var(--ch-font-sans);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease);
}
.tool-btn:hover:not(:disabled) {
  background: var(--ch-accent-subtle);
  color: var(--ch-text-secondary);
}
.tool-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.tool-btn svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.icon-btn {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--ch-text-faint);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease);
}
.icon-btn:hover:not(:disabled) {
  background: var(--ch-accent-subtle);
  color: var(--ch-text-secondary);
}
.icon-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.icon-btn svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.send-btn {
  flex-shrink: 0;
  width: 38px;
  height: 38px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 50%;
  background: var(--ch-ink);
  color: var(--ch-on-ink);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease),
    transform var(--ch-duration-fast) var(--ch-ease);
}
.send-btn svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.send-btn:hover:not(:disabled) { background: var(--ch-ink-hover); }
.send-btn:active:not(:disabled) { transform: scale(0.95); }
.send-btn:disabled {
  background: var(--ch-ink);
  color: var(--ch-on-ink);
  cursor: not-allowed;
}

@media (max-width: 780px) {
  .input-bar { padding: 24px 24px 16px; }
  .input-field { font-size: var(--ch-text-sm); }
  .tool-btn span { display: none; }
}
</style>
