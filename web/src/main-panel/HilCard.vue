<script setup>
import { computed, ref } from 'vue'
import { Check, ChevronRight } from '@lucide/vue'
import { confirmTask, retryTask, editTask } from '../api.js'
import { parseFrontMatter, stripFrontMatter } from '../composables/renderPostCard.js'
import ArtifactCard from './ArtifactCard.vue'
import ScriptProof from './ScriptProof.vue'

const props = defineProps({
  task: { type: Object, required: true },
  sessionId: { type: String, default: '' },
  confirmed: { type: Boolean, default: false },
})
const emit = defineEmits(['confirmed', 'retried', 'edited', 'preview-task'])
const artifacts = computed(() => props.task.artifacts || {})
const candidates = computed(() => artifacts.value.candidates || [])
const selectedIdx = ref(props.task.artifacts?.selected ?? null)
const revising = ref(false)
const feedback = ref('')
const busy = ref(false)
const error = ref('')
const needSelect = computed(() => props.task.agent_type === 'idea')
const editable = computed(() => ['idea', 'script', 'finalize'].includes(props.task.agent_type))
const editing = ref(false)
const actionsFolded = computed(() => props.confirmed || editing.value || editingCandidate.value)

function isEditingSlot(candidate) {
  return Boolean(editingCandidate.value && draftCandidate.value && candidate.index === selectedIdx.value)
}
const draftTitle = ref('')
const draftFrontLines = ref([])
const draftMarkdown = ref('')
const editingCandidate = ref(false)
const draftCandidate = ref(null)
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
    edit: '编辑选题',
  },
  script: {
    title: '确认文案内容',
    description: scriptChars.value ? `当前文案约 ${scriptChars.value} 字` : '检查结构、语气和细节',
    approve: '确认文案',
    revise: '重新生成',
    edit: '编辑文案',
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
    edit: '编辑成品',
  },
}[props.task.agent_type] || {
  title: '确认当前内容',
  description: '检查后决定是否继续',
  approve: '确认',
  revise: '调整',
  edit: '编辑',
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

function startEdit() {
  if (props.task.agent_type === 'idea') {
    if (selectedIdx.value == null) {
      error.value = '请先选择一个候选'
      return
    }
    const current = candidates.value.find((item) => item.index === selectedIdx.value)
    draftCandidate.value = { ...current }
    editingCandidate.value = true
    return
  }
  const markdown = artifacts.value.markdown || ''
  const { front, body } = stripFrontMatter(markdown)
  draftTitle.value = parseFrontMatter(markdown).title || ''
  draftFrontLines.value = front.filter((line) => !line.startsWith('title:'))
  draftMarkdown.value = body
  editing.value = true
}

async function saveEdit() {
  if (!draftTitle.value.trim()) {
    error.value = '标题不能为空'
    return false
  }
  if (!draftMarkdown.value.trim()) {
    error.value = '正文不能为空'
    return false
  }
  const lines = [`title: ${draftTitle.value.trim()}`, ...draftFrontLines.value]
  const markdown = `---\n${lines.join('\n')}\n---\n\n${draftMarkdown.value}`
  busy.value = true
  error.value = ''
  try {
    await editTask(props.task.id, { markdown })
    editing.value = false
    emit('edited', props.task.id)
    return true
  } catch (e) {
    error.value = e.detail || e.message
    return false
  } finally {
    busy.value = false
  }
}

async function saveCandidate() {
  const draft = draftCandidate.value
  if (!draft.title.trim()) {
    error.value = '标题不能为空'
    return false
  }
  const next = candidates.value.map((item) => (item.index === draft.index ? draft : item))
  busy.value = true
  error.value = ''
  try {
    await editTask(props.task.id, { candidates: next })
    editingCandidate.value = false
    emit('edited', props.task.id)
    return true
  } catch (e) {
    error.value = e.detail || e.message
    return false
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
      <div class="head-tools">
        <span class="ch-status-pill" :class="confirmed ? 'is-complete' : 'is-awaiting'">
          <i aria-hidden="true"></i>{{ confirmed ? '已确认' : '待确认' }}
        </span>
      </div>
    </header>

    <div class="review-content">
      <div v-if="task.agent_type === 'idea'" class="candidates" role="radiogroup" aria-label="选题候选">
        <div v-for="c in candidates" :key="c.index" class="candidate-slot">
          <div class="swap-stage">
            <div class="swap-pane" :class="{ off: !isEditingSlot(c) }">
              <div class="pane-frame">
                <div v-if="draftCandidate && draftCandidate.index === c.index" class="candidate-edit">
                  <label>
                    <span>标题</span>
                    <input v-model="draftCandidate.title" type="text" />
                  </label>
                  <label>
                    <span>切入角度</span>
                    <input v-model="draftCandidate.angle" type="text" />
                  </label>
                  <label>
                    <span>推荐理由</span>
                    <textarea v-model="draftCandidate.reason" rows="2"></textarea>
                  </label>
                  <div class="edit-actions">
                    <button class="secondary" type="button" :disabled="busy" @click="editingCandidate = false">
                      取消
                    </button>
                    <button class="primary" type="button" :disabled="busy" @click="saveCandidate()">
                      {{ busy ? '正在保存' : '保存修改' }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
            <div class="swap-pane" :class="{ off: isEditingSlot(c) }">
              <div class="pane-frame">
                <button
                  type="button"
                  class="candidate"
                  :class="{ selected: selectedIdx === c.index }"
                  role="radio"
                  :aria-checked="selectedIdx === c.index"
                  :aria-label="[c.title, c.angle || c.reason, selectedIdx === c.index ? '已选择' : ''].filter(Boolean).join('，')"
                  :disabled="confirmed || editingCandidate"
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
                      <Check />
                    </span>
                  </span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <template v-else-if="task.agent_type === 'script'">
        <div class="swap-stage">
          <div class="swap-pane" :class="{ off: !editing }">
            <div class="pane-frame">
              <div class="edit-fields">
                <label>
                  <span>标题</span>
                  <input v-model="draftTitle" type="text" />
                </label>
                <label>
                  <span>正文</span>
                  <textarea v-model="draftMarkdown" class="edit-area" rows="14"></textarea>
                </label>
              </div>
            </div>
          </div>
          <div class="swap-pane" :class="{ off: editing }">
            <div class="pane-frame">
              <ScriptProof :markdown="artifacts.markdown || ''" />
            </div>
          </div>
        </div>
      </template>

      <div v-else-if="task.agent_type === 'image'" class="images">
        <figure v-for="img in artifacts.images || []" :key="img.url">
          <img :src="img.url" :alt="img.caption || ''" loading="lazy" />
          <figcaption>{{ img.caption }}</figcaption>
        </figure>
      </div>

      <template v-else-if="task.agent_type === 'finalize'">
        <div class="swap-stage">
          <div class="swap-pane" :class="{ off: !editing }">
            <div class="pane-frame">
              <div class="edit-fields">
                <label>
                  <span>标题</span>
                  <input v-model="draftTitle" type="text" />
                </label>
                <label>
                  <span>正文</span>
                  <textarea v-model="draftMarkdown" class="edit-area" rows="14"></textarea>
                </label>
              </div>
            </div>
          </div>
          <div class="swap-pane" :class="{ off: editing }">
            <div class="pane-frame">
              <ArtifactCard
                :card="artifacts"
                :finished="task.status === 'finished'"
                review
                @preview="$emit('preview-task', task)"
              />
            </div>
          </div>
        </div>
      </template>

      <div class="swap-stage">
        <div class="swap-pane" :class="{ off: !editing }">
          <div class="pane-frame">
            <div class="edit-actions">
              <button class="secondary" type="button" :disabled="busy" @click="editing = false">
                取消
              </button>
              <button class="primary" type="button" :disabled="busy" @click="saveEdit()">
                {{ busy ? '正在保存' : '保存修改' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="feedback" :class="{ folded: !revising }" :inert="!revising">
      <div class="feedback-frame">
        <div class="feedback-body">
          <label for="review-feedback">希望怎样调整</label>
          <textarea
            id="review-feedback"
            v-model="feedback"
            placeholder="写下需要修改的内容或方向"
            rows="3"
          ></textarea>
        </div>
      </div>
    </div>

    <footer class="actions" :class="{ folded: actionsFolded }" :inert="actionsFolded">
      <div class="actions-frame">
        <Transition name="action-swap" mode="out-in">
          <div v-if="!revising" key="review" class="actions-group">
            <button
              v-if="editable"
              class="secondary"
              type="button"
              :disabled="busy"
              @click="startEdit"
            >
              {{ meta.edit }}
            </button>
            <button
              class="secondary"
              type="button"
              :disabled="busy"
              @click="revising = true"
            >
              {{ meta.revise }}
            </button>
          </div>
          <div v-else key="revise" class="actions-group">
            <button
              class="secondary"
              type="button"
              :disabled="busy"
              @click="revising = false"
            >
              返回
            </button>
          </div>
        </Transition>
        <button class="primary" type="button" :disabled="busy" @click="revising ? onRetry() : onConfirm()">
          {{ busy ? '正在处理' : (revising ? '提交修改意见' : meta.approve) }}
          <ChevronRight v-if="!busy" aria-hidden="true" />
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

.head-tools {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 8px;
  margin-left: auto;
  align-self: center;
}

.review-content {
  margin: 0;
  padding: 0;
  border: 0;
}

.review-finalize .review-content {
  border: 1px solid transparent;
  border-radius: var(--ch-radius-list);
  transition: border-color var(--ch-duration-fast) var(--ch-ease);
}

.review-finalize .review-content:has(.artifact-card:hover),
.review-finalize .review-content:has(.artifact-card:focus-visible) {
  border-color: var(--ch-accent);
}

.candidates {
  display: grid;
  gap: var(--ch-space-3);
}

.candidate-slot {
  min-width: 0;
}

.candidate-edit {
  display: grid;
  gap: 16px;
  padding: 16px 20px;
  border: 1px solid var(--ch-accent);
  border-radius: var(--ch-radius-list);
  background: var(--ch-surface);
}

.candidate-edit label {
  display: grid;
  gap: 8px;
  color: var(--ch-text-muted);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
}

.edit-fields {
  display: grid;
  gap: 16px;
}

.edit-fields label {
  display: grid;
  gap: 8px;
  color: var(--ch-text-muted);
  font-size: var(--ch-text-sm);
  font-weight: 600;
  line-height: 1.5;
}

.candidate-edit input,
.candidate-edit textarea,
.edit-fields input,
.edit-area {
  width: 100%;
  padding: 16px;
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  color: var(--ch-text);
  font: 400 14px/1.6 var(--ch-font-sans);
  resize: vertical;
  transition: border-color var(--ch-duration-fast) var(--ch-ease);
}

.candidate-edit input:focus,
.candidate-edit textarea:focus,
.edit-fields input:focus,
.edit-area:focus {
  outline: 0;
  border-color: var(--ch-accent);
}

.edit-area {
  min-height: 320px;
  font: 400 14px/1.6 var(--ch-font-sans);
}

.edit-actions {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 16px;
}

.edit-actions button {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  padding: 0 16px;
  border-radius: var(--ch-radius-btn);
  font: 600 14px/1 var(--ch-font-sans);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease);
}

.edit-actions button:disabled {
  cursor: default;
  opacity: .5;
}

.edit-actions .secondary {
  border: 1px solid var(--ch-border-strong);
  background: var(--ch-surface);
  color: var(--ch-text);
}

.edit-actions .secondary:hover:not(:disabled) {
  background: var(--ch-surface-2);
}

.edit-actions .primary {
  border: 0;
  background: var(--ch-ink);
  color: var(--ch-on-ink);
}

.edit-actions .primary:hover:not(:disabled) {
  background: var(--ch-ink-hover);
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
  grid-template-columns: repeat(auto-fit, minmax(min(180px, 100%), 1fr));
  align-items: start;
  gap: var(--ch-space-3);
}

.images figure {
  min-width: 0;
  margin: 0;
}

.images img {
  display: block;
  width: 100%;
  border-radius: var(--ch-radius-list);
}

.images figcaption {
  margin-top: 8px;
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.feedback {
  display: grid;
  grid-template-rows: 1fr;
  overflow: hidden;
  transition: grid-template-rows 320ms cubic-bezier(.22, .8, .25, 1);
}

.feedback.folded {
  grid-template-rows: 0fr;
}

.feedback-frame {
  min-height: 0;
  overflow: hidden;
}

.feedback-body {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--ch-border);
  opacity: 1;
  transform: translateY(0);
  transition: opacity 180ms ease, transform 320ms cubic-bezier(.22, .8, .25, 1);
}

.feedback.folded .feedback-body {
  opacity: 0;
  transform: translateY(8px);
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
  display: grid;
  grid-template-rows: 1fr;
  overflow: hidden;
  transition: grid-template-rows 280ms cubic-bezier(.22, .8, .25, 1);
}

.actions.folded {
  grid-template-rows: 0fr;
}

.actions-frame {
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: var(--ch-space-3);
  opacity: 1;
  transform: translateY(0);
  transition: margin-top 280ms cubic-bezier(.22, .8, .25, 1),
    opacity 180ms ease,
    transform 280ms cubic-bezier(.22, .8, .25, 1);
}

.actions.folded .actions-frame {
  margin-top: 0;
  opacity: 0;
  transform: translateY(8px);
}

.actions-group {
  display: flex;
  gap: 8px;
}

.action-swap-enter-active {
  transition: opacity 160ms ease, transform 200ms cubic-bezier(.22, .8, .25, 1);
}

.action-swap-leave-active {
  transition: opacity 120ms ease;
}

.action-swap-enter-from {
  opacity: 0;
  transform: translateY(4px);
}

.action-swap-leave-to {
  opacity: 0;
}

.actions button {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 16px;
  border-radius: var(--ch-radius-btn);
  font: 600 var(--ch-text-sm)/1 var(--ch-font-sans);
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

.swap-stage {
  min-width: 0;
  display: grid;
}

.swap-pane {
  grid-area: 1 / 1;
  align-self: start;
  min-width: 0;
  display: grid;
  grid-template-rows: 1fr;
  overflow: hidden;
  opacity: 1;
  transform: translateY(0);
  transition: grid-template-rows 320ms cubic-bezier(.22, .8, .25, 1),
    opacity 180ms ease,
    transform 320ms cubic-bezier(.22, .8, .25, 1);
}

.swap-pane.off {
  grid-template-rows: 0fr;
  opacity: 0;
  transform: translateY(8px);
  visibility: hidden;
  pointer-events: none;
  transition: grid-template-rows 320ms cubic-bezier(.22, .8, .25, 1),
    opacity 180ms ease,
    transform 320ms cubic-bezier(.22, .8, .25, 1),
    visibility 0s linear 320ms;
}

.pane-frame {
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 700px) {
  .hil-card {
    padding: 16px;
  }

  .actions-frame {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .actions-group {
    display: grid;
    grid-template-columns: 1fr 1fr;
  }

}
</style>
