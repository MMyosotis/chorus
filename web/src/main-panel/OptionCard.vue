<script setup>
import { ref } from 'vue'

const props = defineProps({
  prompt: { type: Object, required: true },
})
const emit = defineEmits(['choose'])
const locking = ref(false)
const customText = ref('')

function choose(signal, customText) {
  if (locking.value) return
  locking.value = true
  const payload = { signal }
  if (customText != null) payload.custom_text = customText
  emit('choose', payload)
}

function chooseCustom() {
  const text = customText.value.trim()
  if (!text || locking.value) return
  choose('__custom__', text)
}
</script>

<template>
  <section class="option-card">
    <header class="card-head">
      <div class="head-copy">
        <h2>{{ prompt.question }}</h2>
        <p>选择一个方向，或补充你的想法</p>
      </div>
      <span class="status">待选择</span>
    </header>

    <div class="options">
      <button
        v-for="opt in prompt.options"
        :key="opt.signal"
        class="option-item"
        type="button"
        :disabled="locking"
        @click="choose(opt.signal)"
      >
        <strong>{{ opt.label }}</strong>
        <p>{{ opt.description }}</p>
      </button>
    </div>

    <div v-if="prompt.allow_custom" class="custom">
      <input
        v-model="customText"
        class="custom-input"
        type="text"
        placeholder="或补充你的想法"
        :disabled="locking"
        @keydown.enter="chooseCustom"
      />
      <button
        class="custom-submit"
        type="button"
        :disabled="locking || !customText.trim()"
        @click="chooseCustom"
      >
        补充
      </button>
    </div>
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
  display: inline-flex;
  min-height: 32px;
  flex: 0 0 auto;
  align-items: center;
  margin-left: auto;
  padding: 0 var(--ch-space-3);
  border-radius: var(--ch-radius-pill);
  background: var(--ch-warning-soft);
  color: var(--ch-warning-text);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
}

.options {
  display: grid;
  gap: var(--ch-space-3);
  margin-top: 24px;
}

.option-item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-list);
  background: var(--ch-surface);
  text-align: left;
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease);
}

.option-item:hover:not(:disabled) {
  background: var(--ch-surface-2);
  border-color: var(--ch-border-strong);
}

.option-item:disabled {
  cursor: default;
  opacity: .5;
}

.option-item strong {
  font-size: var(--ch-text-md);
  font-weight: 600;
  line-height: 1.4;
  color: var(--ch-text);
}

.option-item p {
  margin: 0;
  font-size: var(--ch-text-sm);
  line-height: 1.5;
  color: var(--ch-text-muted);
  overflow-wrap: anywhere;
}

.custom {
  display: flex;
  gap: 8px;
  margin-top: var(--ch-space-3);
}

.custom-input {
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

.custom-submit {
  flex: 0 0 auto;
  min-height: 40px;
  padding: 0 16px;
  border: 0;
  border-radius: var(--ch-radius-btn);
  background: var(--ch-ink);
  color: var(--ch-on-ink);
  font: 600 14px/1 var(--ch-font-sans);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease);
}

.custom-submit:hover:not(:disabled) {
  background: var(--ch-ink-hover);
}

.custom-submit:disabled {
  opacity: .5;
  cursor: default;
}

@media (max-width: 700px) {
  .option-card {
    padding: 16px;
  }
}
</style>
