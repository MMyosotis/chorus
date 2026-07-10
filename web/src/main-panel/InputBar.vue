<script setup>
import { ref, nextTick, computed } from 'vue'

const props = defineProps({
  streaming: { type: Boolean, default: false },
  hasActiveTask: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])

const inputText = ref('')
const textarea = ref(null)

const disabled = computed(() => props.streaming || props.hasActiveTask)
const placeholder = computed(() =>
  props.hasActiveTask ? '执行中，暂时不能输入；确认节点或完成后恢复。' : '写一句想法……'
)

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
  <div class="input-bar" :class="{ locked: hasActiveTask }">
    <div class="input-inner">
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
      <button
        class="send-btn"
        :disabled="disabled || !inputText.trim()"
        @click="send"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="19" x2="12" y2="5"></line>
          <polyline points="5 12 12 5 19 12"></polyline>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-bar {
  flex-shrink: 0;
  padding: 28px 16px 22px;
  background: transparent;
  position: relative;
  z-index: 10;
}

.input-bar::before {
  content: none;
}

.input-inner {
  max-width: var(--ch-runtime-width);
  margin: 0 auto;
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 4px 0 8px;
  border-bottom: 1px solid var(--ch-border-2);
  background: transparent;
  transition: border-color 0.2s;
}

.input-inner:focus-within {
  border-color: var(--ch-primary);
}

.input-bar.locked .input-inner {
  border-color: var(--ch-border-2);
}

.input-field {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  font-family: inherit;
  min-height: 24px;
  max-height: 180px;
  overflow-y: auto;
  scrollbar-width: none;
  padding: 2px 2px;
}

.input-bar.locked .input-field {
  min-height: 24px;
  font-size: 12px;
  color: var(--ch-muted);
}

.input-field:disabled {
  cursor: not-allowed;
}

/* 创作中 placeholder：灰阶 + 省略号呼吸流动 */
.input-field:disabled::placeholder {
  color: var(--ch-faint);
  animation: busyDots 1.4s steps(4, end) infinite;
}

@keyframes busyDots {
  0% { opacity: 0.5; }
  50% { opacity: 1; }
  100% { opacity: 0.5; }
}

.input-bar.locked .send-btn {
  display: none;
}

.send-btn {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--ch-border-2);
  border-radius: 8px;
  background: transparent;
  color: var(--ch-primary);
  cursor: pointer;
  transition: border-color 0.18s, background 0.18s, transform 0.15s;
}

.send-btn:hover:not(:disabled) {
  border-color: var(--ch-primary);
  background: var(--ch-primary-soft);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.94);
}

.send-btn:disabled {
  background: transparent;
  border-color: var(--ch-border);
  color: var(--ch-faint);
  cursor: not-allowed;
}
</style>
