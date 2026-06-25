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
  const maxH = 180
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
      <div class="input-footer">
        <span class="input-spacer"></span>
        <button
          class="send-btn"
          :disabled="streaming || !inputText.trim()"
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
  padding: 40px 22px 20px 16px;
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
    rgba(246, 248, 253, 0) 0%,
    rgba(246, 248, 253, 0.85) 50%,
    rgba(246, 248, 253, 1) 100%
  );
  mask-image: linear-gradient(to bottom, transparent 0%, #000 50%);
  -webkit-mask-image: linear-gradient(to bottom, transparent 0%, #000 50%);
  z-index: -1;
}

.input-inner {
  position: relative;
  max-width: 768px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px 10px 14px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  box-shadow: 0 8px 28px rgba(99, 102, 241, 0.10), 0 2px 6px rgba(99, 102, 241, 0.06),
    0 1px 0 rgba(255, 255, 255, 0.7) inset;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

.input-inner:focus-within {
  border-color: rgba(129, 140, 248, 0.7);
  background: #ffffff;
  box-shadow: 0 10px 30px rgba(99, 102, 241, 0.22),
    0 0 0 4px rgba(129, 140, 248, 0.14),
    0 1px 0 rgba(255, 255, 255, 0.7) inset;
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
  min-height: 44px;
  max-height: 180px;
  overflow-y: auto;
  scrollbar-width: none;
  padding: 2px 2px;
}

.input-field:disabled {
  cursor: not-allowed;
}

.input-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.send-btn {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #818cf8);
  color: #fff;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.32), 0 1px 2px rgba(99, 102, 241, 0.2);
  transition: box-shadow 0.2s, transform 0.15s, filter 0.2s;
}

.send-btn:hover:not(:disabled) {
  filter: brightness(1.06);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.4), 0 1px 2px rgba(99, 102, 241, 0.24);
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
