<script setup>
import { ref, nextTick, computed, watch } from 'vue'
import { ArrowUp, Clock3, Lightbulb, Mic, Paperclip } from '@lucide/vue'
import IntentConfirmCard from './IntentConfirmCard.vue'
import OptionCard from './OptionCard.vue'

const props = defineProps({
  streaming: { type: Boolean, default: false },
  hasActiveTask: { type: Boolean, default: false },
  awaitingConfirm: { type: Boolean, default: false },
  awaitingOption: { type: Boolean, default: false },
  archived: { type: Boolean, default: false },
  intentConfirmation: { type: Object, default: null },
  optionPrompt: { type: Object, default: null },
})

const emit = defineEmits(['send', 'intent-confirm', 'intent-revise', 'option-choose'])

const inputText = ref('')
const textarea = ref(null)

const disabled = computed(() => props.streaming || props.hasActiveTask || props.awaitingConfirm || props.awaitingOption || props.archived)
const hasHil = computed(() => !!(props.intentConfirmation || props.optionPrompt))
const displayedOptionPrompt = ref(null)
const displayedIntentConfirmation = ref(null)
const optionCollapsed = ref(false)
let hilReleaseTimer = null
const isClosingHil = ref(false)
const hasHilStage = computed(() =>
  hasHil.value || isClosingHil.value,
)

watch(
  () => [props.optionPrompt, props.intentConfirmation],
  ([optionPrompt, intentConfirmation]) => {
    if (hilReleaseTimer) {
      clearTimeout(hilReleaseTimer)
      hilReleaseTimer = null
    }
    if (optionPrompt) {
      isClosingHil.value = false
      resetOptionCollapse()
      displayedOptionPrompt.value = optionPrompt
      displayedIntentConfirmation.value = null
      return
    }
    if (intentConfirmation) {
      isClosingHil.value = false
      resetOptionCollapse()
      displayedIntentConfirmation.value = intentConfirmation
      displayedOptionPrompt.value = null
      return
    }
    if (!displayedOptionPrompt.value && !displayedIntentConfirmation.value) {
      resetOptionCollapse()
      isClosingHil.value = false
      return
    }
    // 收起阶段只执行确认卡的退出动画，避免与输入区的进入动画重叠。
    resetOptionCollapse()
    isClosingHil.value = true
    hilReleaseTimer = setTimeout(() => {
      displayedOptionPrompt.value = null
      displayedIntentConfirmation.value = null
      isClosingHil.value = false
      hilReleaseTimer = null
    }, 360)
  },
  { immediate: true },
)

function resetOptionCollapse() {
  optionCollapsed.value = false
}

const placeholder = computed(() => {
  if (props.archived) return '本篇已定稿存档，请新建会话开始下一篇'
  if (props.awaitingOption) return '请先在上方选择一个选项'
  if (props.awaitingConfirm) return '请先确认或调整上方意图卡片'
  if (props.hasActiveTask) return '执行中，暂时不能输入；确认节点或完成后恢复'
  if (props.streaming) return '助手正在回复，请稍候…'
  return '说说你想创作的内容…'
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

function prefill(text) {
  inputText.value = text
  nextTick(() => {
    adjustHeight()
    focus()
  })
}

defineExpose({ focus, prefill })
</script>

<template>
  <div class="input-zone" :class="{ 'has-hil-stage': hasHilStage, 'is-closing-hil': isClosingHil, 'is-option-collapsed': optionCollapsed, 'is-waiting': disabled && !hasHilStage }">
    <div class="input-stage-shell" :class="{ 'has-hil': hasHil, 'is-closing-hil': isClosingHil }">
    <div class="input-stage" :class="{ 'has-hil': hasHil, 'is-closing-hil': isClosingHil }">
      <div class="stage-slot input-slot" :aria-hidden="hasHil">
        <div class="input-bar" :class="{ 'is-disabled': disabled, archived }">
          <div class="input-editor">
            <div class="input-editor-content">
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
                    <Paperclip aria-hidden="true" />
                    <span>附件</span>
                  </button>
                  <button class="tool-btn" type="button" aria-label="智能推荐" :disabled="disabled">
                    <Lightbulb aria-hidden="true" />
                    <span>智能推荐</span>
                  </button>
                </div>
                <div class="tool-group right">
                  <button class="icon-btn" type="button" aria-label="语音输入" :disabled="disabled">
                    <Mic aria-hidden="true" />
                  </button>
                  <button
                    class="send-btn"
                    :disabled="disabled || !inputText.trim()"
                    @click="send"
                    aria-label="发送"
                  >
                    <ArrowUp aria-hidden="true" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div class="input-wait" :aria-hidden="!disabled">
            <div class="input-wait-content">
              <p class="input-wait-message" role="status">{{ placeholder }}</p>
              <button class="send-btn is-waiting" type="button" disabled aria-label="正在等待">
                <Clock3 aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="stage-slot hil-slot" :aria-hidden="!hasHil">
        <section v-if="displayedOptionPrompt || displayedIntentConfirmation" class="input-hil-card" aria-label="补充创作信息">
        <OptionCard
          v-if="displayedOptionPrompt"
          compact
          :collapsed="optionCollapsed"
          :prompt="displayedOptionPrompt"
          @choose="emit('option-choose', $event)"
          @collapse-change="optionCollapsed = $event"
        />
        <IntentConfirmCard
          v-else
          compact
          :state="displayedIntentConfirmation"
          @confirm="emit('intent-confirm')"
          @revise="emit('intent-revise')"
        />
        </section>
      </div>
    </div>
    </div>
  </div>
</template>

<style scoped>
.input-zone {
  position: relative;
  isolation: isolate;
  flex-shrink: 0;
  width: calc(100% - 32px);
  z-index: 2;
  margin: calc(-1 * var(--ch-radius-xl)) auto 0;
  border-radius: var(--ch-radius-xl);
  box-shadow: var(--ch-shadow-soft);
}

.input-zone.is-waiting {
  border-radius: var(--ch-radius-pill);
  clip-path: inset(0 round var(--ch-radius-pill));
  box-shadow: 0 0 24px color-mix(in srgb, var(--ch-text) 6%, transparent);
}

/* HIL 从底部输入区向上展开；它覆盖对话末端，顶部圆角朝下方打开。 */
.input-zone.has-hil-stage {
  position: absolute;
  z-index: 3;
  right: 0;
  bottom: 0;
  left: 0;
  width: auto;
  margin: 0;
  overflow: hidden;
  clip-path: inset(0 round var(--ch-radius-card));
  border: 1px solid color-mix(in srgb, var(--ch-accent) 48%, var(--ch-border));
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-soft);
  transition: border-color 240ms cubic-bezier(.22, .8, .25, 1), border-radius 240ms cubic-bezier(.22, .8, .25, 1), clip-path 240ms cubic-bezier(.22, .8, .25, 1), box-shadow 240ms cubic-bezier(.22, .8, .25, 1);
}

/* 收起选择卡后沿用禁用输入栏的胶囊外壳。 */
.input-zone.has-hil-stage.is-option-collapsed {
  clip-path: inset(0 round 36px);
  border-radius: 36px;
  box-shadow: none;
  /* 收起时外壳延迟跟上，展开时立即 */
  transition-delay: 100ms;
}

.input-zone.is-closing-hil {
  border-color: transparent;
  box-shadow: none;
}

.input-bar {
  flex-shrink: 0;
  position: relative;
  width: 100%;
  margin: 0;
  padding: var(--ch-space-4) var(--ch-space-4) var(--ch-space-3);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  background: var(--ch-surface);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-xl);
  box-shadow: var(--ch-shadow-soft);
  overflow: hidden;
  transition: padding 360ms cubic-bezier(.22, .8, .25, 1),
    border-radius 360ms cubic-bezier(.22, .8, .25, 1),
    box-shadow 360ms cubic-bezier(.22, .8, .25, 1);
}

.input-bar.is-disabled {
  padding: 16px;
  border-radius: 999px;
  box-shadow: none;
}

.input-stage-shell {
  isolation: isolate;
  overflow: hidden;
  transform: translateZ(0);
  border-radius: var(--ch-radius-xl);
  background: transparent;
  transition: box-shadow 360ms cubic-bezier(.22, .8, .25, 1);
}

.input-stage-shell.has-hil {
  border-radius: var(--ch-radius-card);
  box-shadow: none;
}

.input-stage {
  display: grid;
  overflow: hidden;
  border-radius: var(--ch-radius-xl);
  clip-path: inset(0 round var(--ch-radius-xl));
  grid-template-rows: 1fr 0fr;
  transition: grid-template-rows 360ms cubic-bezier(.22, .8, .25, 1);
}

.input-stage.has-hil {
  border-radius: var(--ch-radius-card);
  clip-path: inset(0 round var(--ch-radius-card));
  grid-template-rows: 0fr 1fr;
}

.input-stage.is-closing-hil {
  grid-template-rows: 0fr 0fr;
}

.stage-slot {
  min-height: 0;
  overflow: hidden;
  border-radius: var(--ch-radius-xl);
  transition: opacity 180ms ease, transform 360ms cubic-bezier(.22, .8, .25, 1);
}

.input-slot { opacity: 1; transform: translateY(0); }
.hil-slot { opacity: 0; transform: translateY(12px); }
.input-stage.has-hil .input-slot { opacity: 0; transform: translateY(-8px); }
.input-stage.has-hil .hil-slot {
  border-radius: var(--ch-radius-card);
  opacity: 1;
  transform: translateY(0);
}

.input-stage.is-closing-hil .hil-slot {
  opacity: 0;
  transform: translateY(-8px);
}

.input-hil-card {
  width: 100%;
  overflow: hidden;
  border-radius: inherit;
}
.input-hil-card :deep(.option-card),
.input-hil-card :deep(.intent-confirm) {
  border: 0;
  border-radius: inherit;
  background: transparent;
  box-shadow: none;
}

.input-editor,
.input-wait {
  min-height: 0;
  display: grid;
  transition: grid-template-rows 360ms cubic-bezier(.22, .8, .25, 1),
    opacity 200ms ease,
    transform 360ms cubic-bezier(.22, .8, .25, 1);
}

.input-editor {
  grid-template-rows: 1fr;
  opacity: 1;
  transform: translateY(0);
}

.input-editor-content,
.input-wait-content {
  min-height: 0;
  overflow: hidden;
}

.input-editor-content {
  display: flex;
  flex-direction: column;
  gap: var(--ch-space-2);
}

.input-wait {
  grid-template-rows: 0fr;
  opacity: 0;
  transform: translateY(8px);
}

.input-wait-content {
  display: flex;
  align-items: center;
  gap: var(--ch-space-3);
}

.input-bar.is-disabled .input-editor {
  grid-template-rows: 0fr;
  opacity: 0;
  transform: translateY(-8px);
}

.input-bar.is-disabled .input-wait {
  grid-template-rows: 1fr;
  opacity: 1;
  transform: translateY(0);
}

.input-wait-message {
  min-width: 0;
  flex: 1;
  margin: 0;
  overflow: hidden;
  color: var(--ch-text-faint);
  font: 400 var(--ch-text-sm)/1.4 var(--ch-font-sans);
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (min-width: 781px) {
  .input-zone {
    width: 100%;
    margin: calc(-1 * var(--ch-radius-xl)) 0 0;
  }
}

.input-field {
  width: 100%;
  border: none;
  outline: none;
  background: transparent;
  min-height: 48px;
  padding: 0;
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-md);
  line-height: 1.6;
  resize: none;
  max-height: 160px;
  overflow-y: auto;
  scrollbar-width: none;
  color: var(--ch-text);
}
.input-field::-webkit-scrollbar { display: none; }
.input-field::placeholder { color: var(--ch-text-faint); }
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
  gap: var(--ch-space-2);
}

.tool-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--ch-space-2);
  height: 36px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--ch-text-faint);
  font: 400 var(--ch-text-sm)/1 var(--ch-font-sans);
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
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.icon-btn {
  width: 36px;
  height: 36px;
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
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.send-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
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
  width: 18px;
  height: 18px;
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

.send-btn.is-waiting {
  width: 36px;
  height: 36px;
  display: grid;
  place-items: center;
  line-height: 0;
  align-self: center;
}

.send-btn.is-waiting svg {
  display: block;
  width: 20px;
  height: 20px;
  stroke-width: 2.2;
}

@media (prefers-reduced-motion: reduce) {
  .input-bar,
  .input-editor,
  .input-wait,
  .input-stage-shell,
  .input-stage,
  .stage-slot { transition: none; }
}

@media (max-width: 780px) {
  .input-bar { padding: var(--ch-space-4) var(--ch-space-4) var(--ch-space-3); }
  .input-field { font-size: var(--ch-text-sm); }
  .tool-btn span { display: none; }
}
</style>
