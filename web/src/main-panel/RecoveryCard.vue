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
.recovery-card {
  border: 1px solid color-mix(in srgb, var(--ch-red) 30%, var(--ch-border));
  border-radius: var(--ch-radius-md);
  background: var(--ch-red-soft);
  padding: 20px 22px;
  margin: 4px 0;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.04);
}
.rc-title {
  font-size: 17px;
  font-family: var(--ch-serif);
  font-weight: 600;
  color: var(--ch-red);
  margin-bottom: 10px;
}
.rc-error-text {
  font-size: 13px;
  color: var(--ch-red);
  background: var(--ch-surface);
  border-radius: var(--ch-radius-sm);
  padding: 8px 10px;
  margin-bottom: 10px;
}
.rc-feedback {
  width: 100%; box-sizing: border-box;
  border: 1px solid var(--ch-border); border-radius: var(--ch-radius-sm);
  padding: 6px 8px; font-size: 13px; resize: vertical; margin-bottom: 8px;
}
.rc-actions { display: flex; gap: 8px; }
.btn {
  border: 1px solid var(--ch-border-2); background: var(--ch-surface); color: var(--ch-muted);
  padding: 8px 14px; border-radius: 999px; cursor: pointer; font-size: 13px; font-weight: 600;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn.primary { background: var(--ch-orange); border-color: var(--ch-orange); color: #fff; }
.btn.primary:hover:not(:disabled) { background: var(--ch-orange-2); border-color: var(--ch-orange-2); }
.btn.danger { color: var(--ch-red); border-color: color-mix(in srgb, var(--ch-red) 40%, var(--ch-border)); }
.rc-error { color: var(--ch-red); font-size: 12px; margin-top: 6px; }
</style>
