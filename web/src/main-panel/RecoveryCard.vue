<script setup>
import { ref } from 'vue'
import { retryTask, cancelPipeline } from '../api.js'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({
  task: { type: Object, required: true },
  sessionId: { type: String, required: true },
})
const emit = defineEmits(['retried', 'cancelled'])

const roleName = ROLE_LABELS[props.task.agent_type] || props.task.agent_type
const feedback = ref('')
const busy = ref(false)
const error = ref('')

async function onRetry() {
  busy.value = true; error.value = ''
  try {
    await retryTask(props.task.id, { feedback: feedback.value || '' })
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
  <div class="recovery-card">
    <div class="rc-title">{{ roleName }} · 这步失败了</div>
    <div v-if="task.error" class="rc-error-text">{{ task.error }}</div>
    <textarea v-model="feedback" class="rc-feedback"
      placeholder="（可选）补充意见，点「重试本步」生效" rows="2" />
    <div class="rc-actions">
      <button class="btn primary" :disabled="busy" @click="onRetry">重试本步</button>
      <button class="btn danger" :disabled="busy" @click="onCancel">放弃整条</button>
    </div>
    <div v-if="error" class="rc-error">{{ error }}</div>
  </div>
</template>

<style scoped>
.recovery-card { border: 1px solid rgba(248, 113, 113, 0.5); border-radius: 12px;
  background: rgba(254, 242, 242, 0.7); padding: 14px; margin: 8px 0; }
.rc-title { font-weight: 500; color: #b91c1c; margin-bottom: 8px; }
.rc-error-text { font-size: 13px; color: #b91c1c; background: rgba(248, 113, 113, 0.1);
  border-radius: 6px; padding: 6px 8px; margin-bottom: 8px; }
.rc-feedback { width: 100%; box-sizing: border-box; border: 1px solid #e2e8f0; border-radius: 6px;
  padding: 6px 8px; font-size: 13px; resize: vertical; margin-bottom: 8px; }
.rc-actions { display: flex; gap: 8px; }
.btn { border: 1px solid #cbd5e1; background: #fff; color: #475569; padding: 6px 12px;
  border-radius: 6px; cursor: pointer; font-size: 13px; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn.primary { background: #6366f1; border-color: #6366f1; color: #fff; }
.btn.danger { color: #b91c1c; border-color: #fca5a5; }
.rc-error { color: #b91c1c; font-size: 12px; margin-top: 6px; }
</style>
