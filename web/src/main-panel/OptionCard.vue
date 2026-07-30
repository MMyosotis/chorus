<script setup>
import { computed, nextTick, ref } from 'vue'

const props = defineProps({
  prompt: { type: Object, required: true },
})
const emit = defineEmits(['choose'])
const locking = ref(false)
const selectedSignal = ref(null)
const customText = ref('')
const customInput = ref(null)
const error = ref('')
const archived = computed(() => props.prompt.status === 'answered')
const selectedValue = computed(() => props.prompt.answer?.signal || selectedSignal.value)
const customSelected = computed(() => selectedValue.value === '__custom__')
const archivedCustomText = computed(() => props.prompt.answer?.custom_text || '已补充自定义想法')

function selectOption(signal) {
  if (locking.value || archived.value) return
  selectedSignal.value = signal
  error.value = ''

  if (signal === '__custom__') {
    nextTick(() => customInput.value?.focus())
  }
}

function reconsider() {
  if (locking.value || archived.value) return
  selectedSignal.value = null
  customText.value = ''
  error.value = ''
}

function confirmChoice() {
  if (locking.value || archived.value) return
  if (selectedSignal.value == null) {
    error.value = '请先选择一个选项'
    return
  }
  if (customSelected.value && !customText.value.trim()) {
    error.value = '请补充你的想法'
    nextTick(() => customInput.value?.focus())
    return
  }
  locking.value = true
  const payload = { signal: selectedSignal.value }
  if (customSelected.value) payload.custom_text = customText.value.trim()
  emit('choose', payload)
}
</script>

<template>
  <section class="option-card" :class="{ archived }">
    <header class="card-head">
      <div class="head-copy">
        <h2>{{ prompt.question }}</h2>
        <p>{{ archived ? '已确认本次选择' : '选择一个方向，或补充你的想法' }}</p>
      </div>
      <span class="status ch-status-pill" :class="archived ? 'is-complete' : 'is-pending'">
        <i aria-hidden="true"></i>{{ archived ? '已确认' : '待选择' }}
      </span>
    </header>

    <div class="options" role="radiogroup" aria-label="可选方向">
      <button
        v-for="opt in prompt.options"
        :key="opt.signal"
        class="option-item"
        :class="{ selected: selectedValue === opt.signal }"
        type="button"
        role="radio"
        :aria-checked="selectedValue === opt.signal"
        :disabled="locking || archived"
        @click="selectOption(opt.signal)"
      >
        <span class="option-copy">
          <strong>{{ opt.label }}</strong>
          <p>{{ opt.description }}</p>
        </span>
        <span class="option-selection" :class="{ visible: selectedValue === opt.signal }" aria-hidden="true">
          <span>已选择</span>
          <span class="option-check">
            <svg viewBox="0 0 24 24"><path d="m6 12 4 4 8-8" /></svg>
          </span>
        </span>
      </button>

      <Transition name="custom-option" mode="out-in">
        <button
          v-if="prompt.allow_custom && !customSelected"
          key="prompt"
          class="option-item custom-option"
          type="button"
          role="radio"
          :aria-checked="false"
          :disabled="locking || archived"
          @click="selectOption('__custom__')"
        >
          <span class="option-copy">
            <strong>补充你的想法</strong>
            <p>写下你希望突出呈现的角度或内容。</p>
          </span>
          <span class="custom-chevron" aria-hidden="true">
            <svg viewBox="0 0 24 24"><path d="m9 6 6 6-6 6" /></svg>
          </span>
        </button>

        <div v-else-if="prompt.allow_custom" key="input" class="option-item custom-option selected">
          <div class="option-copy">
            <strong>补充你的想法</strong>
            <p v-if="archived" class="custom-answer">{{ archivedCustomText }}</p>
            <input
              v-else
              ref="customInput"
              v-model="customText"
              class="custom-input"
              type="text"
              placeholder="写下你希望突出呈现的角度或内容"
              :disabled="locking || archived"
              @keydown.enter="confirmChoice"
            />
          </div>
        </div>
      </Transition>
    </div>

    <footer v-if="!archived" class="actions">
      <p v-if="error" class="action-error" role="alert">{{ error }}</p>
      <div>
        <button class="secondary" type="button" @click="reconsider">
          重新考虑
        </button>
        <button
          class="primary"
          type="button"
          @click="confirmChoice"
        >
          {{ locking ? '正在确认' : '确认选项' }}
          <svg v-if="!locking" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
        </button>
      </div>
    </footer>
  </section>
</template>

<style scoped>
.option-card {
  width: 100%;
  padding: var(--ch-space-4);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-soft);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.head-copy {
  min-width: 0;
}

.head-copy h2 {
  margin: 0;
  font-size: var(--ch-text-xl);
  font-weight: 600;
  line-height: var(--ch-leading-snug);
  overflow-wrap: anywhere;
}

.head-copy p {
  margin: 8px 0 0;
  color: var(--ch-text-muted);
  font-size: var(--ch-text-sm);
  line-height: 1.5;
}

.status {
  flex: 0 0 auto;
  margin-left: auto;
}

.options {
  display: grid;
  gap: var(--ch-space-3);
  margin-top: 24px;
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

.option-item:hover:not(:disabled) {
  background: var(--ch-surface-2);
  border-color: var(--ch-border-strong);
}

.option-item.selected {
  border-color: var(--ch-border);
  background: var(--ch-accent-soft);
  box-shadow: var(--ch-shadow-xs);
  transform: translateY(-1px);
}

.option-item.selected:hover:not(:disabled) {
  border-color: var(--ch-border);
  background: var(--ch-accent-soft);
}

.option-item:focus-visible {
  outline: 2px solid var(--ch-accent);
  outline-offset: 0;
}

.option-item:disabled {
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
  visibility: hidden;
  opacity: 0;
  transform: scale(.9);
  color: var(--ch-accent-soft-text);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
  transition: opacity var(--ch-duration-fast) var(--ch-ease-out),
    transform var(--ch-duration-fast) var(--ch-ease-out),
    visibility 0s linear var(--ch-duration-fast);
}

.option-selection.visible {
  visibility: visible;
  opacity: 1;
  transform: scale(1);
  transition-delay: 0s;
}

.custom-option-enter-active,
.custom-option-leave-active {
  transition: opacity var(--ch-duration-fast) var(--ch-ease-out),
    transform var(--ch-duration-normal) var(--ch-ease-out);
}

.custom-option-enter-from {
  opacity: 0;
  transform: translateY(-6px);
}

.custom-option-leave-to {
  opacity: 0;
  transform: translateY(4px);
}

.option-check {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--ch-accent);
  color: var(--ch-on-accent);
}

.option-check svg,
.custom-chevron svg,
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

.custom-chevron {
  display: grid;
  place-items: center;
  color: var(--ch-text-muted);
}

.custom-input {
  width: 100%;
  margin-top: 12px;
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

@media (max-width: 700px) {
  .option-card {
    padding: 16px;
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
