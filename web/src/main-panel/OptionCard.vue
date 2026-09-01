<script setup>
import { computed, nextTick, ref } from 'vue'
import { Check, ChevronDown, ChevronRight, ChevronUp } from '@lucide/vue'

const props = defineProps({
  prompt: { type: Object, required: true },
  hideActions: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
  collapsed: { type: Boolean, default: false },
})
const emit = defineEmits(['choose', 'collapse-change'])
const locking = ref(false)
const currentIndex = ref(0)
const selections = ref([])
const customTexts = ref([])
const customInput = ref(null)
const error = ref('')
const archived = computed(() => props.prompt.status === 'answered')
const questions = computed(() => props.prompt.questions || [])
const currentQuestion = computed(() => questions.value[currentIndex.value] || null)
const currentSignal = computed(() => selections.value[currentIndex.value] || null)
const customSelected = computed(() => currentSignal.value === '__custom__')
const isLastQuestion = computed(() => currentIndex.value === questions.value.length - 1)

function selectOption(signal) {
  if (locking.value) return
  const next = [...selections.value]
  next[currentIndex.value] = signal
  selections.value = next
  error.value = ''

  if (signal === '__custom__') {
    nextTick(() => customInput.value?.focus())
  }
}

function validateCurrentQuestion() {
  const question = currentQuestion.value
  const signal = selections.value[currentIndex.value]
  if (signal == null) {
    error.value = '请先选择一个选项'
    return false
  }
  if (signal === '__custom__' && !customTexts.value[currentIndex.value]?.trim()) {
    error.value = '请补充你的想法'
    nextTick(() => customInput.value?.focus())
    return false
  }
  return true
}

function nextQuestion() {
  if (locking.value) return
  if (!validateCurrentQuestion()) return
  currentIndex.value += 1
  error.value = ''
}

function previousQuestion() {
  if (locking.value || currentIndex.value === 0) return
  currentIndex.value -= 1
  error.value = ''
}

function toggleCollapsed() {
  emit('collapse-change', !props.collapsed)
}

function confirmChoices() {
  if (locking.value || !validateCurrentQuestion()) return
  locking.value = true
  emit('choose', {
    answers: questions.value.map((question, index) => {
      const signal = selections.value[index]
      return {
        signal,
        ...(signal === '__custom__' ? { custom_text: customTexts.value[index].trim() } : {}),
      }
    }),
  })
}

defineExpose({ confirmChoices })
</script>

<template>
  <section v-if="!archived" class="option-card" :class="{ compact, collapsed: props.collapsed }">
    <div class="option-controls">
      <span class="status ch-status-pill is-awaiting">
        <i aria-hidden="true"></i>待确认
      </span>
      <button
        class="collapse-toggle"
        type="button"
        :aria-label="props.collapsed ? '向上展开选择工具' : '向下收起选择工具'"
        :title="props.collapsed ? '向上展开选择工具' : '向下收起选择工具'"
        :aria-expanded="!props.collapsed"
        @click="toggleCollapsed"
      >
        <ChevronUp v-if="props.collapsed" aria-hidden="true" />
        <ChevronDown v-else aria-hidden="true" />
      </button>
    </div>

    <div v-if="currentQuestion" class="collapsed-summary" :class="{ visible: props.collapsed }" :aria-hidden="!props.collapsed">
      <p class="question-progress">第 {{ currentIndex + 1 }} / {{ questions.length }} 题</p>
      <p class="collapsed-question-title">{{ currentQuestion.question }}</p>
    </div>

    <div class="option-body" :inert="props.collapsed">
      <div class="option-body-content">
        <div v-if="currentQuestion" class="options" role="radiogroup" :aria-label="currentQuestion.question">
          <p class="question-progress">第 {{ currentIndex + 1 }} / {{ questions.length }} 题</p>
          <h3 class="question-title">{{ currentQuestion.question }}</h3>
          <button
            v-for="opt in currentQuestion.options"
            :key="opt.signal"
            class="option-item"
            :class="{ selected: currentSignal === opt.signal }"
            type="button"
            role="radio"
            :aria-checked="currentSignal === opt.signal"
            :disabled="locking"
            @click="selectOption(opt.signal)"
          >
            <span class="option-copy">
              <strong>{{ opt.label }}</strong>
              <p>{{ opt.description }}</p>
            </span>
            <span class="option-selection" aria-hidden="true">
              <span class="selection-label" :class="{ visible: currentSignal === opt.signal }">已选择</span>
              <span class="option-check" :class="{ selected: currentSignal === opt.signal }">
                <Check v-if="currentSignal === opt.signal" />
              </span>
            </span>
          </button>

          <button
            v-if="currentQuestion.allow_custom && !customSelected"
            class="option-item custom-option"
            type="button"
            role="radio"
            :aria-checked="false"
            :disabled="locking"
            @click="selectOption('__custom__')"
          >
            <span class="option-copy">
              <strong>补充你的想法</strong>
              <p>写下你希望突出呈现的角度或内容。</p>
            </span>
            <span class="option-check" aria-hidden="true"></span>
          </button>

          <div
            v-else-if="currentQuestion.allow_custom"
            class="option-item custom-option selected"
            :class="{ disabled: locking }"
            role="radio"
            :aria-checked="true"
          >
            <div class="custom-option-editor">
              <span class="option-copy">
                <strong>补充你的想法</strong>
                <span class="custom-editor-value">
                  <input
                    ref="customInput"
                    v-model="customTexts[currentIndex]"
                    class="custom-input"
                    type="text"
                    placeholder="写下你希望突出呈现的角度或内容"
                    :disabled="locking"
                    @keydown.enter="isLastQuestion ? confirmChoices() : nextQuestion()"
                  />
                </span>
              </span>
              <!-- 预留与普通选项一致的选择位，保证两种状态的文字列精确对齐。 -->
              <span class="option-selection custom-selection-spacer" aria-hidden="true">
                <span>已选择</span>
                <span class="option-check selected"><Check /></span>
              </span>
            </div>
          </div>
        </div>

        <footer v-if="!hideActions" class="actions">
          <p v-if="error" class="action-error" role="alert">{{ error }}</p>
          <div>
            <button v-if="currentIndex > 0" class="secondary" type="button" :disabled="locking" @click="previousQuestion">
              上一题
            </button>
            <button
              class="primary"
              type="button"
              @click="isLastQuestion ? confirmChoices() : nextQuestion()"
            >
              {{ locking ? '正在确认' : (isLastQuestion ? '提交全部选择' : '下一题') }}
              <ChevronRight v-if="!locking" aria-hidden="true" />
            </button>
          </div>
        </footer>
      </div>
    </div>
  </section>
</template>

<style scoped>
.option-card {
  --collapsed-reserve: 176px;
  position: relative;
  width: 100%;
  padding: var(--ch-space-4);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-soft);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
  transition: padding 280ms cubic-bezier(.22, .8, .25, 1);
}

.option-controls {
  position: absolute;
  top: var(--ch-space-4);
  right: var(--ch-space-4);
  display: flex;
  align-items: center;
  gap: 8px;
  z-index: 1;
  transition: top 280ms cubic-bezier(.22, .8, .25, 1);
}

.collapse-toggle {
  width: 32px;
  height: 32px;
  display: inline-grid;
  flex: 0 0 auto;
  place-items: center;
  padding: 0;
  border: 1px solid var(--ch-accent-border);
  border-radius: 50%;
  background: var(--ch-surface);
  color: var(--ch-accent);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease),
    border-color var(--ch-duration-fast) var(--ch-ease),
    color var(--ch-duration-fast) var(--ch-ease);
}

.collapse-toggle:hover {
  border-color: var(--ch-accent);
  background: var(--ch-accent-subtle);
}

.collapse-toggle:focus-visible {
  outline: 2px solid var(--ch-accent);
  outline-offset: 2px;
}

.collapse-toggle svg {
  width: 17px;
  height: 17px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.question-progress {
  margin: 0;
  color: var(--ch-text-muted);
  font-size: var(--ch-text-xs);
  font-weight: 600;
}

.options {
  display: grid;
  gap: var(--ch-space-3);
}

.option-body {
  display: grid;
  grid-template-rows: 1fr;
  overflow: hidden;
  transition: grid-template-rows 280ms cubic-bezier(.22, .8, .25, 1);
}

.option-body-content {
  min-height: 0;
  opacity: 1;
  transform: translateY(0);
  transition: opacity 180ms ease, transform 280ms cubic-bezier(.22, .8, .25, 1);
}

.collapsed .option-body {
  grid-template-rows: 0fr;
}

.collapsed .option-body-content {
  opacity: 0;
  transform: translateY(8px);
}

.collapsed-summary {
  height: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  overflow: hidden;
  padding-right: var(--collapsed-reserve);
  opacity: 0;
  transform: translateY(-4px);
  transition: height 280ms cubic-bezier(.22, .8, .25, 1), opacity 180ms ease, transform 280ms cubic-bezier(.22, .8, .25, 1);
}

.collapsed-summary.visible {
  height: 32px;
  opacity: 1;
  transform: translateY(0);
}

.collapsed-question-title {
  margin: 0;
  min-width: 0;
  overflow: hidden;
  color: var(--ch-text);
  font-size: var(--ch-text-md);
  font-weight: 600;
  line-height: 1.4;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.question-title {
  margin: 0 0 8px;
  color: var(--ch-text);
  font-size: var(--ch-text-lg);
  font-weight: 600;
  line-height: 1.3;
}

.option-item {
  width: 100%;
  min-height: 80px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-list);
  background: var(--ch-surface);
  text-align: left;
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease),
    border-color var(--ch-duration-fast) var(--ch-ease),
    box-shadow var(--ch-duration-fast) var(--ch-ease),
    transform var(--ch-duration-fast) var(--ch-ease);
}

.option-item:hover:not(:disabled):not(.disabled) {
  background: var(--ch-surface-2);
  border-color: var(--ch-border-strong);
}

.option-item.selected {
  border-color: var(--ch-border);
  background: var(--ch-accent-soft);
}

.option-item.selected:hover:not(:disabled) {
  border-color: var(--ch-border);
  background: var(--ch-accent-soft);
}

.custom-option:not(.selected) {
  border: 1.5px dashed var(--ch-border);
  background: var(--ch-surface);
}

.option-item:focus-visible {
  outline: 2px solid var(--ch-accent);
  outline-offset: 0;
}

.option-item:disabled {
  cursor: default;
  opacity: 1;
}

.option-item.disabled {
  cursor: default;
  opacity: 1;
}

.option-copy {
  min-width: 0;
}

.option-item strong {
  font-size: var(--ch-text-md);
  font-weight: 600;
  line-height: 1.4;
  color: var(--ch-text);
}

.option-item p {
  margin: 8px 0 0;
  font-size: var(--ch-text-sm);
  line-height: 1.5;
  color: var(--ch-text-muted);
  overflow-wrap: anywhere;
}

.option-item .custom-answer {
  color: var(--ch-text-secondary);
}

.option-selection {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--ch-accent-soft-text);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}

/* 已选标签常驻占位，仅切换可见性，避免选中时文字列被挤压位移。 */
.selection-label {
  visibility: hidden;
}

.selection-label.visible {
  visibility: visible;
}

.custom-option-editor {
  width: 100%;
  min-height: 40px;
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  padding: 0;
}

.custom-option-editor .option-copy {
  display: block;
}

.custom-editor-value {
  min-width: 0;
}

.option-check {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border: 1.5px solid var(--ch-text-faint);
  border-radius: 50%;
  color: var(--ch-on-accent);
}

.option-check.selected {
  border-color: var(--ch-accent);
  background: var(--ch-accent);
}

.option-check svg,
.primary svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.option-check svg {
  width: 13px;
  height: 13px;
  stroke-width: 2.4;
}

.custom-input {
  width: 100%;
  flex: 1;
  min-width: 0;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface);
  color: var(--ch-text);
  font: 400 14px/1 var(--ch-font-sans);
}

.custom-input:focus {
  outline: none;
  border-color: var(--ch-accent);
}

.custom-input:disabled {
  opacity: .5;
}

.actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  margin-top: var(--ch-space-6);
}

.actions > div {
  display: flex;
  gap: 8px;
}

.actions button {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 16px;
  border-radius: var(--ch-radius-btn);
  font: 600 14px/1 var(--ch-font-sans);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease);
}

.actions button:disabled {
  cursor: default;
  opacity: .5;
}

.secondary {
  border: 1px solid var(--ch-border-strong);
  background: var(--ch-surface);
  color: var(--ch-text);
}

.secondary:hover:not(:disabled) {
  background: var(--ch-surface-2);
}

.primary {
  border: 0;
  background: var(--ch-ink);
  color: var(--ch-on-ink);
}

.primary:hover:not(:disabled) {
  background: var(--ch-ink-hover);
}

.action-error {
  margin: 0;
  margin-right: auto;
  color: var(--ch-danger);
  font-size: 14px;
  font-weight: 500;
  line-height: 1;
  white-space: nowrap;
}

/* 输入区内的 HIL 使用紧凑选择器：保留纵向选择，但不抢占对话阅读空间。 */
.option-card.compact {
  padding: 24px;
  border-color: color-mix(in srgb, var(--ch-border-strong) 72%, white);
  box-shadow: var(--ch-shadow-soft);
}

.option-card.compact.collapsed {
  padding: 16px 24px;
}

.option-card.compact.collapsed .option-controls {
  top: 16px;
}

.compact .options {
  gap: 8px;
}

.compact .option-item {
  min-height: 58px;
  padding: 10px 14px;
  border-radius: 12px;
}

.compact .option-copy {
  display: grid;
  grid-template-columns: minmax(132px, .3fr) minmax(0, 1fr);
  align-items: center;
  gap: 16px;
}

.compact .option-item strong {
  font-size: var(--ch-text-sm);
}

.compact .option-item p {
  display: block;
  margin: 0;
  overflow: hidden;
  font-size: var(--ch-text-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compact .custom-option-editor {
  height: 36px;
  min-height: 0;
  padding: 0;
}

.compact .custom-option-editor .option-copy {
  display: grid;
  grid-template-columns: minmax(132px, .3fr) minmax(0, 1fr);
  align-items: center;
  gap: 16px;
}

.compact .custom-input {
  height: 36px;
  min-height: 0;
  font-size: var(--ch-text-xs);
}

.compact .actions {
  margin-top: 16px;
}

.compact .actions button {
  min-height: 36px;
  padding: 0 14px;
}

@media (max-width: 700px) {
  .option-card {
    --collapsed-reserve: 160px;
    padding: 16px;
  }

  .option-card.compact {
    padding: 16px;
  }

  .option-card.compact.collapsed {
    padding: 16px;
  }

  .option-controls {
    top: 16px;
    right: 16px;
  }

  .compact .option-copy,
  .compact .custom-option-editor .option-copy {
    grid-template-columns: 1fr;
    gap: 2px;
  }

  .compact .option-item p {
    overflow: visible;
    white-space: normal;
  }

  .actions {
    align-items: stretch;
  }

  .actions > div {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }
}
</style>
