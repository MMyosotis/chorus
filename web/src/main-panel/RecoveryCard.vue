<script setup>
import { computed, ref } from 'vue'
import { retryTask, cancelPipeline } from '../api.js'
import { ROLE_FULL } from '../team-panel/roleMeta.js'

const props = defineProps({
  task: { type: Object, required: true },
  sessionId: { type: String, required: true },
})
const emit = defineEmits(['retried', 'cancelled'])

const roleName = computed(() => ROLE_FULL[props.task.agent_type] || props.task.agent_type)
const feedback = ref('')
const busy = ref(false)
const error = ref('')
const feedbackId = computed(() => `recovery-feedback-${props.task.id}`)

async function onRetry() {
  busy.value = true; error.value = ''
  try {
    await retryTask(props.task.id, feedback.value || '')
    emit('retried', props.task.id)
  } catch (e) {
    error.value = e.detail || e.message
  } finally { busy.value = false }
}

async function onCancel() {
  if (!confirm('放弃整条创作？此操作不可撤销。')) return
  busy.value = true; error.value = ''
  try {
    await cancelPipeline(props.sessionId)
    emit('cancelled', props.sessionId)
  } catch (e) {
    error.value = e.detail || e.message
  } finally { busy.value = false }
}
</script>

<template>
  <section class="recovery-card" :aria-busy="busy">
    <header class="recovery-head">
      <div>
        <h2>{{ roleName }}未能完成</h2>
        <p>已完成的内容会保留，可以从当前阶段重新开始。</p>
      </div>
      <span>需要处理</span>
    </header>

    <div class="recovery-content">
      <div v-if="task.error" class="recovery-message" role="status">
        <small>问题说明</small>
        <p>{{ task.error }}</p>
      </div>

      <div class="feedback">
        <label :for="feedbackId">补充要求</label>
        <small>选填，重新执行时会一并提交</small>
        <textarea
          :id="feedbackId"
          v-model="feedback"
          placeholder="写下重新执行时需要注意的内容"
          rows="3"
        />
      </div>
    </div>

    <footer class="actions">
      <button class="cancel" :disabled="busy" @click="onCancel">放弃创作</button>
      <button class="primary" :disabled="busy" @click="onRetry">
        {{ busy ? '正在处理' : '重新执行当前阶段' }}
        <svg v-if="!busy" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
      </button>
    </footer>
    <div v-if="error" class="error" role="alert">{{ error }}</div>
  </section>
</template>

<style scoped>
.recovery-card {
  padding: var(--ch-space-5);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-soft);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}
.recovery-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: var(--ch-space-4);
  padding-bottom: var(--ch-space-4);
  border-bottom: 1px solid var(--ch-border);
}
.recovery-head h2 {
  margin: 0;
  font-size: var(--ch-text-xl);
  font-weight: 600;
  line-height: var(--ch-leading-snug);
}
.recovery-head p {
  margin: 8px 0 0;
  color: var(--ch-text-muted);
  font-size: var(--ch-text-sm);
  line-height: 1.5;
}
.recovery-head > span {
  display: inline-flex;
  flex: 0 0 auto;
  align-self: center;
  align-items: center;
  min-height: 32px;
  margin-left: auto;
  padding: 0 var(--ch-space-3);
  border-radius: var(--ch-radius-pill);
  background: var(--ch-danger-soft);
  color: var(--ch-danger-text);
  font: 600 12px/1 var(--ch-font-sans);
  white-space: nowrap;
}
.recovery-content {
  margin: 0;
  padding: 0;
  border: 0;
}
.recovery-message {
  padding: var(--ch-space-3);
  border-radius: var(--ch-radius-list);
  background: var(--ch-muted-gradient);
}
.recovery-message small {
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 1.5;
}
.recovery-message p {
  margin: 8px 0 0;
  color: var(--ch-danger-text);
  font-size: 14px;
  line-height: 1.5;
}
.feedback {
  margin-top: var(--ch-space-4);
  padding-top: var(--ch-space-4);
  border-top: 1px solid var(--ch-border);
}
.feedback label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
}
.feedback small {
  display: block;
  margin-top: 8px;
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 1.5;
}
.feedback textarea {
  width: 100%; box-sizing: border-box;
  min-height: 96px;
  margin-top: 16px;
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
  justify-content: flex-end;
  gap: 16px;
  margin-top: var(--ch-space-4);
}
.actions button {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 0 16px;
  border: 1px solid transparent;
  border-radius: var(--ch-radius-btn);
  font: 600 14px/1 var(--ch-font-sans);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease);
}
.actions button:disabled { cursor: default; opacity: .5; }
.cancel {
  border-color: var(--ch-border-strong);
  background: var(--ch-surface);
  color: var(--ch-text);
}
.cancel:hover:not(:disabled) { background: var(--ch-surface-2); }
.primary {
  background: var(--ch-ink);
  color: var(--ch-on-ink);
}
.primary:hover:not(:disabled) { background: var(--ch-ink-hover); }
.primary svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}
.error { margin: 16px 0 0; color: var(--ch-danger); font-size: 12px; line-height: 1.5; }
@media (max-width: 620px) {
  .recovery-card { padding: 16px; }
  .actions { align-items: stretch; flex-direction: column-reverse; }
  .cancel { align-self: flex-start; }
}
</style>
