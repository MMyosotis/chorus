<script setup>
import { ref, nextTick } from 'vue'

const props = defineProps({
  streaming: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])

const inputText = ref('')
const textarea = ref(null)

function handleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function send() {
  const text = inputText.value.trim()
  if (!text || props.streaming) return
  emit('send', text)
  inputText.value = ''
  nextTick(() => adjustHeight())
}

function adjustHeight() {
  const el = textarea.value
  if (!el) return
  el.style.height = 'auto'
  const maxH = 5 * 24 // 约 5 行
  el.style.height = Math.min(el.scrollHeight, maxH) + 'px'
}
</script>

<template>
  <div class="input-bar">
    <div class="input-inner">
      <textarea
        ref="textarea"
        v-model="inputText"
        class="input-field"
        placeholder="输入消息..."
        rows="1"
        :disabled="streaming"
        @keydown="handleKeydown"
        @input="adjustHeight"
      ></textarea>
      <button
        class="send-btn"
        :disabled="streaming || !inputText.trim()"
        @click="send"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.input-bar {
  flex-shrink: 0;
  padding: 40px 16px 20px;
  background: transparent;
  position: relative;
  z-index: 10;
  margin-top: -50px;
}

.input-bar::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  backdrop-filter: blur(28px) saturate(180%);
  -webkit-backdrop-filter: blur(28px) saturate(180%);
  background: linear-gradient(
    to bottom,
    rgba(248, 250, 252, 0) 0%,
    rgba(248, 250, 252, 0.85) 50%,
    rgba(248, 250, 252, 1) 100%
  );
  mask-image: linear-gradient(to bottom, transparent 0%, #000 50%);
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, #000 50%);
  z-index: -1;
}

.input-inner {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 10px;
  max-width: 768px;
  margin: 0 auto;
}

.input-field {
  flex: 1;
  padding: 12px 16px;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  font-size: 15px;
  line-height: 1.5;
  resize: none;
  outline: none;
  font-family: inherit;
  background: #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06), 0 1px 2px rgba(15, 23, 42, 0.04);
  transition: border-color 0.2s, box-shadow 0.2s;
  max-height: 120px;
  overflow-y: auto;
  scrollbar-width: none;
}

.input-field::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}

.input-field:focus {
  border-color: #3b82f6;
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.12), 0 0 0 3px rgba(59, 130, 246, 0.08);
}

.input-field:disabled {
  background: #f8fafc;
  cursor: not-allowed;
}

.send-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
  transition: background 0.2s;
}

.send-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.send-btn:disabled {
  background: #93c5fd;
  cursor: not-allowed;
}
</style>
