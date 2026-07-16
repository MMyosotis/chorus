<script setup>
import { ref, nextTick, computed } from 'vue'

const props = defineProps({
  streaming: { type: Boolean, default: false },
  hasActiveTask: { type: Boolean, default: false },
  awaitingConfirm: { type: Boolean, default: false },
})

const emit = defineEmits(['send'])

const inputText = ref('')
const textarea = ref(null)

const disabled = computed(() => props.streaming || props.hasActiveTask || props.awaitingConfirm)
const placeholder = computed(() => {
  if (props.awaitingConfirm) return '请先确认或调整上方意图卡片'
  if (props.hasActiveTask) return '执行中，暂时不能输入；确认节点或完成后恢复。'
  if (props.streaming) return '助手正在回复，请稍候……'
  return '写下你的修改意见……'
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
  <div class="input-bar" :class="{ locked: hasActiveTask || awaitingConfirm }">
    <div class="input-inner">
      <div class="composer-label">修改<br>意见</div>
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
        发送
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
  bottom: 18px;
  width: min(calc(100% - 52px), 828px);
  padding: 10px 10px 10px 0;
  transform: translateX(-50%);
  background: rgba(251, 250, 245, .97);
  border: 1px solid rgba(27, 25, 22, .72);
  box-shadow: 0 -5px 16px rgba(58, 48, 36, .06);
}

.input-bar::before {
  content: none;
}

.input-inner {
  width: 100%;
  display: grid;
  grid-template-columns: 64px 54px minmax(0, 1fr) 74px;
  align-items: center;
  gap: 0;
  min-height: 54px;
  padding: 0;
  border: 0;
}

.composer-label { height: 54px; display: flex; align-items: center; justify-content: center; color: var(--ch-warm); font: 600 13px/1.5 var(--ch-serif); letter-spacing: .12em; text-align: center; }
.attach-btn { width: 54px; height: 54px; min-height: 54px; display: grid; place-items: center; padding: 0; border: 1px solid rgba(183, 177, 167, .92); border-right: 0; background: var(--ch-input-surface); box-shadow: inset 0 1px rgba(255,255,255,.34); color: var(--ch-body); cursor: pointer; }
.attach-btn svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.field-shell { height: 54px; display: flex; align-items: center; min-width: 0; border: 1px solid rgba(183, 177, 167, .92); background: var(--ch-input-surface); box-shadow: inset 0 1px rgba(255,255,255,.34); }
.field-shell:focus-within { border-color: var(--ch-primary); }

.input-bar.locked .input-inner {
  border-color: var(--ch-border-2);
}

.input-field {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  height: 52px;
  min-height: 52px;
  padding: 14px 16px;
  font-family: var(--ch-serif);
  font-size: 14px;
  line-height: 24px;
  resize: none;
  max-height: 180px;
  overflow-y: auto;
  scrollbar-width: none;
  color: var(--ch-text);
}

.input-bar.locked .input-field {
  min-height: 52px;
  font-size: 12px;
  color: var(--ch-muted);
}

.input-field:disabled {
  cursor: not-allowed;
}

/* 创作中 placeholder：灰阶 + 省略号呼吸流动 */
.input-field:disabled::placeholder {
  color: var(--ch-meta);
  animation: busyDots 1.4s steps(4, end) infinite;
}

@keyframes busyDots {
  0% { opacity: 0.5; }
  50% { opacity: 1; }
  100% { opacity: 0.5; }
}

.send-btn {
  flex-shrink: 0;
  width: 64px;
  height: 54px;
  min-height: 54px;
  margin-left: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: var(--ch-warm);
  color: var(--ch-on-accent);
  cursor: pointer;
  font: 600 13px/1 var(--ch-serif);
  letter-spacing: .08em;
  transition: background .18s, opacity .18s;
}

.send-btn:hover:not(:disabled) {
  background: var(--ch-warm-hover);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.94);
}

.send-btn:disabled {
  background: var(--ch-muted);
  color: var(--ch-paper);
  opacity: .35;
  cursor: not-allowed;
}

@media (max-width: 780px) {
  .input-bar { left: 50%; bottom: 10px; width: calc(100% - 28px); padding: 8px 8px 8px 0; }
  .input-inner { grid-template-columns: 42px 42px minmax(0, 1fr) 62px; }
  .composer-label { font-size: 11px; }
  .attach-btn { width: 42px; height: 50px; min-height: 50px; }
  .field-shell { height: 50px; }
  .input-field { height: 48px; min-height: 48px; padding: 12px 10px; font-size: 16px; }
  .send-btn { width: 54px; height: 50px; min-height: 50px; margin-left: 8px; }
}

</style>
