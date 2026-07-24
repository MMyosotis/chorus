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
  if (props.hasActiveTask) return '执行中，暂时不能输入；确认节点或完成后恢复。'
  if (props.streaming) return '助手正在回复，请稍候……'
  return '输入你的想法或任务……'
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
  const maxH = 180
  el.style.height = Math.min(el.scrollHeight, maxH) + 'px'
}

function focus() {
  textarea.value?.focus()
}

defineExpose({ focus })
</script>

<template>
  <div class="input-bar" :class="{ locked: hasActiveTask || awaitingConfirm, archived }">
    <div class="input-inner">
      <button class="attach-btn" type="button" aria-label="添加附件" :disabled="disabled">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m20.5 11.5-8.9 8.9a6 6 0 0 1-8.5-8.5l9.6-9.6a4 4 0 0 1 5.7 5.7l-9.6 9.6a2 2 0 1 1-2.8-2.8l8.9-8.9"/></svg>
      </button>
      <div class="field-shell">
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
      </div>
      <button
        class="send-btn"
        :disabled="disabled || !inputText.trim()"
        @click="send"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 19V5m0 0-6 6m6-6 6 6"/></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-bar {
  flex-shrink: 0;
  position: absolute;
  z-index: 40;
  left: 50%;
  bottom: 24px;
  width: min(calc(100% - 64px), 768px);
  padding: 8px;
  transform: translateX(-50%);
  background: var(--ch-surface);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  box-shadow: var(--ch-shadow-md);
}

.input-inner {
  width: 100%;
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr) 48px;
  align-items: center;
  gap: 0;
  min-height: 56px;
  padding: 0;
  border: 0;
}

.attach-btn {
  width: 48px;
  height: 48px;
  min-height: 48px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: var(--ch-radius-btn);
  background: transparent;
  color: var(--ch-text-muted);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease);
}
.attach-btn:hover:not(:disabled) { background: var(--ch-surface-3); color: var(--ch-text); }
.attach-btn svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }

.field-shell { min-height: 56px; display: flex; align-items: center; min-width: 0; border: 0; background: transparent; }

.input-field {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  min-height: 56px;
  padding: 16px 8px;
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-sm);
  line-height: 24px;
  resize: none;
  max-height: 180px;
  overflow-y: auto;
  scrollbar-width: none;
  color: var(--ch-text);
}

.input-bar.locked .input-field {
  min-height: 56px;
  font-size: var(--ch-text-xs);
  color: var(--ch-text-muted);
}

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

.send-btn {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: 50%;
  background: var(--ch-accent-gradient);
  color: var(--ch-on-accent);
  cursor: pointer;
  transition: box-shadow var(--ch-duration-fast) var(--ch-ease), opacity var(--ch-duration-fast) var(--ch-ease);
}
.send-btn svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }

.send-btn:hover:not(:disabled) { box-shadow: 0 6px 16px rgba(99, 102, 241, .32); }

.send-btn:active:not(:disabled) { transform: scale(0.94); }

.send-btn:disabled {
  background: var(--ch-surface-3);
  color: var(--ch-text-faint);
  cursor: not-allowed;
}

@media (max-width: 780px) {
  .input-bar { left: 50%; bottom: 16px; width: calc(100% - 32px); padding: 8px; }
  .input-inner { grid-template-columns: 40px minmax(0, 1fr) 48px; }
  .attach-btn { width: 40px; }
  .input-field { font-size: var(--ch-text-base); }
}
</style>
