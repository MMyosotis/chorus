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
  props.hasActiveTask ? '执行中，暂时不能输入；确认节点或完成后恢复。' : '输入消息...'
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
      <div class="input-footer">
        <span class="input-spacer"></span>
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
  </div>
</template>

<style scoped>
.input-bar {
  flex-shrink: 0;
  padding: 0 16px 20px;
  background: transparent;
  position: relative;
  z-index: 10;
}

.input-bar::before {
  content: none;
}

.input-inner {
  position: relative;
  max-width: var(--ch-runtime-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 10px 8px 20px;
  border: 1px solid var(--ch-border);
  border-radius: 12px;
  background: #fff;
  box-shadow: none;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

.input-inner:focus-within {
  border-color: var(--ch-primary);
  background: #ffffff;
  box-shadow: 0 0 0 4px rgba(67, 56, 202, 0.1);
}

.input-bar.locked .input-inner {
  min-height: 38px;
  background: #eef2f7;
  border-color: #dde5ee;
  justify-content: center;
  padding: 0 22px;
}

.input-field {
  display: block;
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  font-family: inherit;
  min-height: 38px;
  max-height: 180px;
  overflow-y: auto;
  scrollbar-width: none;
  padding: 2px 2px;
}

.input-bar.locked .input-field {
  min-height: 28px;
  height: 28px !important;
  font-size: 12px;
  color: var(--ch-muted);
}

.input-field:disabled {
  cursor: not-allowed;
}

/* 创作中 placeholder：灰阶 + 省略号呼吸流动 */
.input-field:disabled::placeholder {
  color: #94a3b8;
  animation: busyDots 1.4s steps(4, end) infinite;
}

@keyframes busyDots {
  0% { opacity: 0.5; }
  50% { opacity: 1; }
  100% { opacity: 0.5; }
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.input-bar.locked .input-footer {
  display: none;
}

.send-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: #1f2937;
  color: #fff;
  cursor: pointer;
  box-shadow: none;
  transition: box-shadow 0.2s, transform 0.15s, filter 0.2s;
}

.send-btn:hover:not(:disabled) {
  filter: brightness(1.05);
  box-shadow: none;
}

.send-btn:active:not(:disabled) {
  transform: scale(0.94);
}

.send-btn:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
  box-shadow: none;
}
</style>
