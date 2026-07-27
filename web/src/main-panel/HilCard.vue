<script setup>
import { computed, ref } from 'vue'
import { cancelPipeline, confirmTask, retryTask } from '../api.js'
import ArtifactCard from './ArtifactCard.vue'
import ScriptProof from './ScriptProof.vue'

const props = defineProps({ task: { type: Object, required: true }, sessionId: { type: String, required: true } })
const emit = defineEmits(['confirmed', 'retried', 'cancelled', 'preview-task'])
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
  return (artifacts.value.blocks || []).reduce((sum, block) => sum + String(block.text || '').length, 0)
})

const meta = computed(() => ({
  idea: {
    title: '选择一个选题方向',
    description: `${candidates.value.length || 0} 个候选，选择后即可继续`,
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

async function onCancel() {
  if (!confirm('放弃整条创作？已确认的内容会保留。')) return
  busy.value = true
  error.value = ''
  try {
    await cancelPipeline(props.sessionId)
    emit('cancelled', props.sessionId)
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
      <span>待确认</span>
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
          @click="selectedIdx = c.index"
        >
          <span class="candidate-state">{{ selectedIdx === c.index ? '已选择' : '候选选题' }}</span>
          <h3>{{ c.title }}</h3>
          <p v-if="c.angle" class="angle">{{ c.angle }}</p>
          <p v-if="c.reason" class="reason">{{ c.reason }}</p>
        </button>
      </div>

      <ScriptProof v-else-if="task.agent_type === 'script'" :blocks="artifacts.blocks || []" />

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

    <footer class="actions">
      <button class="cancel" type="button" :disabled="busy" @click="onCancel">放弃创作</button>
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
        </button>
      </div>
    </footer>

    <p v-if="error" class="error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.hil-card {
  padding: var(--ch-space-4);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-sm);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.review-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.review-head h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  line-height: 1.3;
}

.review-head p {
  margin: 8px 0 0;
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.review-head > span {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 8px;
  border-radius: var(--ch-radius-pill);
  background: var(--ch-warning-soft);
  color: var(--ch-warning-text);
  font: 600 12px/1 var(--ch-font-sans);
  white-space: nowrap;
}

.review-content {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--ch-border);
}

.candidates {
  display: grid;
  gap: 16px;
}

.candidate {
  width: 100%;
  padding: 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
  text-align: left;
  cursor: pointer;
  transition: border-color var(--ch-duration-fast) var(--ch-ease), background var(--ch-duration-fast) var(--ch-ease);
}

.candidate:hover,
.candidate.selected {
  border-color: var(--ch-accent);
  background: var(--ch-accent-soft);
}

.candidate:focus-visible {
  outline: 2px solid var(--ch-accent);
  outline-offset: 0;
}

.candidate-state {
  color: var(--ch-text-muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
}

.candidate.selected .candidate-state {
  color: var(--ch-accent-soft-text);
}

.candidate h3 {
  margin: 8px 0 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.5;
}

.candidate p {
  margin: 8px 0 0;
}

.angle {
  color: var(--ch-text-secondary);
  font-size: 14px;
  line-height: 1.5;
}

.reason {
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.images {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.images figure {
  min-width: 0;
  margin: 0;
}

.images img {
  display: block;
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: var(--ch-radius-card);
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
  font-size: 14px;
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
  font: 400 14px/1.5 var(--ch-font-sans);
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
  justify-content: space-between;
  gap: 16px;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--ch-border);
}

.actions > div {
  display: flex;
  gap: 8px;
}

.actions button {
  min-height: 40px;
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

.cancel {
  padding-left: 0;
  border: 0;
  background: transparent;
  color: var(--ch-text-muted);
}

.cancel:hover:not(:disabled) {
  color: var(--ch-danger);
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
  background: var(--ch-accent);
  color: var(--ch-on-accent);
}

.primary:hover:not(:disabled) {
  background: var(--ch-accent-hover);
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
    flex-direction: column-reverse;
  }

  .actions > div {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

  .cancel {
    align-self: flex-start;
  }
}
</style>
