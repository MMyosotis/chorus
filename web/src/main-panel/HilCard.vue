<script setup>
import { computed, ref } from 'vue'
import { confirmTask, retryTask } from '../api.js'
import ArtifactCard from './ArtifactCard.vue'
import ScriptProof from './ScriptProof.vue'

const props = defineProps({
  task: { type: Object, required: true },
  sessionId: { type: String, default: '' },
  confirmed: { type: Boolean, default: false },
})
const emit = defineEmits(['confirmed', 'retried', 'preview-task'])
const artifacts = computed(() => props.task.artifacts || {})
const candidates = computed(() => artifacts.value.candidates || [])
const selectedIdx = ref(props.task.artifacts?.selected ?? null)
const revising = ref(false)
const feedback = ref('')
const busy = ref(false)
const error = ref('')
const needSelect = computed(() => props.task.agent_type === 'idea')
const scriptChars = computed(() => {
  const explicit = props.task.progress?.composing_chars || props.task.artifacts?.char_count
  if (explicit) return explicit
  return (artifacts.value.markdown || '').length
})

const meta = computed(() => ({
  idea: {
    title: '选择一个选题方向',
    description: props.confirmed
      ? `${candidates.value.length || 0} 个候选，已完成选择`
      : `${candidates.value.length || 0} 个候选，选择后即可继续`,
    approve: '确认这个选题',
    revise: '重新生成选题',
  },
  script: {
    title: '确认文案内容',
    description: scriptChars.value ? `当前文案约 ${scriptChars.value} 字` : '检查结构、语气和细节',
    approve: '确认文案',
    revise: '修改文案',
  },
  image: {
    title: '确认配图方案',
    description: `${(artifacts.value.images || []).length || 0} 张配图，检查画面与叙事是否一致`,
    approve: '确认配图',
    revise: '重新配图',
  },
  finalize: {
    title: '确认最终成品',
    description: '检查标题、正文和配图的整体效果',
    approve: '确认成品',
    revise: '继续调整',
  },
}[props.task.agent_type] || {
  title: '确认当前内容',
  description: '检查后决定是否继续',
  approve: '确认',
  revise: '调整',
}))

async function onConfirm() {
  if (needSelect.value && selectedIdx.value == null) {
    error.value = '请先选择一个候选'
    return
  }
  busy.value = true
  error.value = ''
  try {
    await confirmTask(props.task.id, needSelect.value ? selectedIdx.value : null)
    emit('confirmed', props.task.id)
  } catch (e) {
    error.value = e.detail || e.message
  } finally {
    busy.value = false
  }
}

async function onRetry() {
  busy.value = true
  error.value = ''
  try {
    await retryTask(props.task.id, feedback.value || '')
    emit('retried', props.task.id)
  } catch (e) {
    error.value = e.detail || e.message
  } finally {
    busy.value = false
  }
}

</script>

<template>
  <section class="hil-card" :class="`review-${task.agent_type}`">
    <header class="review-head">
      <div>
        <h2>{{ meta.title }}</h2>
        <p>{{ meta.description }}</p>
      </div>
      <span class="ch-status-pill" :class="confirmed ? 'is-complete' : 'is-awaiting'">
        <i aria-hidden="true"></i>{{ confirmed ? '已确认' : '待确认' }}
      </span>
    </header>

    <div class="review-content">
      <div v-if="task.agent_type === 'idea'" class="candidates" role="radiogroup" aria-label="选题候选">
        <button
          v-for="c in candidates"
          :key="c.index"
          type="button"
          class="candidate"
          :class="{ selected: selectedIdx === c.index }"
          role="radio"
          :aria-checked="selectedIdx === c.index"
          :aria-label="[c.title, c.angle || c.reason, selectedIdx === c.index ? '已选择' : ''].filter(Boolean).join('，')"
          :disabled="confirmed"
          @click="selectedIdx = c.index"
        >
          <span class="candidate-copy">
            <h3>{{ c.title }}</h3>
            <span v-if="c.angle || c.reason" class="candidate-summary">{{ c.angle || c.reason }}</span>
          </span>
          <span
            class="candidate-selection"
            :class="{ visible: selectedIdx === c.index }"
            aria-hidden="true"
          >
            <span class="candidate-state">已选择</span>
            <span class="candidate-check" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="m6 12 4 4 8-8" /></svg>
            </span>
          </span>
        </button>
      </div>

      <ScriptProof v-else-if="task.agent_type === 'script'" :markdown="artifacts.markdown || ''" />

      <div v-else-if="task.agent_type === 'image'" class="images">
        <figure v-for="img in artifacts.images || []" :key="img.url">
          <img :src="img.url" :alt="img.caption || ''" loading="lazy" />
          <figcaption>{{ img.caption }}</figcaption>
        </figure>
      </div>

      <ArtifactCard
        v-else-if="task.agent_type === 'finalize'"
        :task="task"
        review
        @preview="$emit('preview-task', task)"
      />
    </div>

    <div v-if="revising" class="feedback">
      <label for="review-feedback">希望怎样调整</label>
      <textarea
        id="review-feedback"
        v-model="feedback"
        placeholder="写下需要修改的内容或方向"
        rows="3"
      ></textarea>
    </div>

    <footer v-if="!confirmed" class="actions">
      <div>
        <button
          v-if="!revising"
          class="secondary"
          type="button"
          :disabled="busy"
          @click="revising = true"
        >
          {{ meta.revise }}
        </button>
        <button
          v-else
          class="secondary"
          type="button"
          :disabled="busy"
          @click="revising = false"
        >
          返回
        </button>
        <button class="primary" type="button" :disabled="busy" @click="revising ? onRetry() : onConfirm()">
          {{ busy ? '正在处理' : (revising ? '提交修改意见' : meta.approve) }}
          <svg v-if="!busy" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
        </button>
      </div>
    </footer>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.hil-card {
  padding: var(--ch-space-5);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-soft);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.review-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ch-border);
}

.review-head h2 {
  margin: 0;
  font-size: var(--ch-text-xl);
  font-weight: 600;
  line-height: var(--ch-leading-snug);
}

.review-head p {
  margin: 8px 0 0;
  color: var(--ch-text-muted);
  font-size: var(--ch-text-md);
  line-height: 1.5;
}

.review-head > span {
  flex: 0 0 auto;
  align-self: center;
  margin-left: auto;
}

.review-content {
  margin: 0;
  padding: 0;
  border: 0;
}

.candidates {
  display: grid;
  gap: var(--ch-space-3);
}

.candidate {
  position: relative;
  width: 100%;
  min-height: 80px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 80px;
  align-items: center;
  gap: var(--ch-space-3);
  padding: 16px 20px;
  overflow: hidden;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-list);
  background: var(--ch-surface);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--ch-duration-fast) var(--ch-ease),
    background var(--ch-duration-fast) var(--ch-ease),
    box-shadow var(--ch-duration-fast) var(--ch-ease),
    transform var(--ch-duration-fast) var(--ch-ease);
}

.candidate:not(:disabled):hover {
  border-color: var(--ch-border-strong);
  background: var(--ch-surface-2);
}

.candidate:disabled {
  cursor: default;
  opacity: 1;
}

.candidate.selected {
  border-color: var(--ch-border);
  background: var(--ch-accent-soft);
  box-shadow: var(--ch-shadow-xs);
  transform: translateY(-1px);
}

.candidate:focus-visible {
  outline: 2px solid var(--ch-accent);
  outline-offset: 0;
}

.candidate-state {
  color: var(--ch-accent-soft-text);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}

.candidate-copy {
  min-width: 0;
  display: block;
}

.candidate-selection {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  visibility: hidden;
  opacity: 0;
  transform: scale(.9);
  transition: opacity var(--ch-duration-fast) var(--ch-ease-out),
    transform var(--ch-duration-fast) var(--ch-ease-out),
    visibility 0s linear var(--ch-duration-fast);
}

.candidate-selection.visible {
  visibility: visible;
  opacity: 1;
  transform: scale(1);
  transition-delay: 0s;
}

.candidate-check {
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--ch-accent);
  color: var(--ch-on-accent);
}

.candidate-check svg {
  width: 13px;
  height: 13px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2.4;
}

.candidate h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
}

.candidate-summary {
  display: block;
  max-width: 100%;
  min-width: 0;
  margin-top: 8px;
  overflow: hidden;
  color: var(--ch-text-secondary);
  font-size: var(--ch-text-sm);
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.images {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--ch-space-3);
}

.images figure {
  min-width: 0;
  margin: 0;
}

.images img {
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: var(--ch-radius-list);
  object-fit: cover;
}

.images figcaption {
  margin-top: 8px;
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.feedback {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--ch-border);
}

.feedback label {
  display: block;
  margin-bottom: 8px;
  font-size: var(--ch-text-md);
  font-weight: 600;
  line-height: 1.5;
}

.feedback textarea {
  width: 100%;
  min-height: 96px;
  padding: 16px;
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  color: var(--ch-text);
  font: 400 var(--ch-text-md)/1.5 var(--ch-font-sans);
  resize: vertical;
  transition: border-color var(--ch-duration-fast) var(--ch-ease);
}

.feedback textarea:focus {
  outline: 0;
  border-color: var(--ch-accent);
}

.actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  margin-top: var(--ch-space-4);
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
  gap: 6px;
  padding: 0 16px;
  border-radius: var(--ch-radius-btn);
  font: 600 var(--ch-text-md)/1 var(--ch-font-sans);
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

.primary svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

.error {
  margin: 16px 0 0;
  color: var(--ch-danger);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 700px) {
  .hil-card {
    padding: 16px;
  }

  .images {
    grid-template-columns: 1fr;
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
