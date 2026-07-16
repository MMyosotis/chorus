<script setup>
import { computed, ref } from 'vue'
import { retryTask, cancelPipeline } from '../api.js'
import { ROLE_FULL, stepOf } from '../team-panel/roleMeta.js'
import StageHeader from './StageHeader.vue'

const props = defineProps({
  task: { type: Object, required: true },
  sessionId: { type: String, required: true },
})
const emit = defineEmits(['retried', 'cancelled'])

const roleName = computed(() => ROLE_FULL[props.task.agent_type] || props.task.agent_type)
const stepNo = computed(() => String(stepOf(props.task.agent_type)).padStart(2, '0'))
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
  <section class="recovery-card">
    <StageHeader :number="stepNo" :title="`${roleName} · 需要处理`" english="RECOVERY DESK" status="已中断" status-tone="danger" />
    <div class="rc-body">
      <div class="rc-caption">EDITOR'S<br>NOTE</div>
      <div class="rc-copy">
        <p class="rc-lead">本阶段未能完成，请核对异常说明后重试。</p>
        <div v-if="task.error" class="rc-error-text">{{ task.error }}</div>
        <label for="recovery-feedback">重试批注 · 可选</label>
        <textarea id="recovery-feedback" v-model="feedback" class="rc-feedback"
          placeholder="补充本阶段重新执行时需要注意的方向" rows="2" />
        <div class="rc-actions">
          <button class="btn primary" :disabled="busy" @click="onRetry">重试本步</button>
          <button class="btn danger" :disabled="busy" @click="onCancel">放弃整条</button>
        </div>
        <div v-if="error" class="rc-error">{{ error }}</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.recovery-card {
  margin: 0 0 24px;
  border: 0;
  background: rgba(255, 253, 248, .28);
}
.rc-body { display: grid; grid-template-columns: 118px minmax(0, 1fr); border-top: 2px solid rgba(27, 25, 22, .9); border-bottom: 1px solid rgba(27, 25, 22, .62); }
.rc-caption { display: flex; align-items: center; justify-content: center; padding: 18px 12px; border-right: 1px dotted rgba(110, 103, 93, .48); color: var(--ch-warm); font: 600 var(--ch-chat-label-size)/1.45 var(--ch-serif); letter-spacing: .08em; text-align: center; }
.rc-copy { min-width: 0; padding: 18px 0 18px 24px; }
.rc-lead { margin: 0 0 12px; color: var(--ch-text); font: 600 var(--ch-chat-subtitle-size)/1.7 var(--ch-serif); }
.rc-error-text {
  font: 500 var(--ch-chat-note-size)/1.7 var(--ch-serif);
  color: var(--ch-red);
  background: rgba(141, 51, 37, .055);
  padding: 9px 11px;
  margin-bottom: 12px;
  border-left: 2px solid rgba(141, 51, 37, .55);
}
.rc-copy label { display: block; margin-bottom: 5px; color: var(--ch-muted); font: 600 10px/1.3 var(--ch-serif); letter-spacing: .04em; }
.rc-feedback {
  width: 100%; box-sizing: border-box;
  min-height: 68px;
  border: 1px solid var(--ch-border-2);
  border-radius: 0; background: rgba(255, 253, 248, .58);
  padding: 10px 12px; color: var(--ch-text); font: 500 13px/1.65 var(--ch-serif); resize: vertical;
}
.rc-actions { display: flex; gap: 18px; flex-wrap: wrap; align-items: center; margin-top: 13px; }
.btn {
  background: transparent; border: none; cursor: pointer;
  font: 600 13px/1 var(--ch-serif);
  letter-spacing: .02em;
  padding: 0; color: var(--ch-faint);
  border-bottom: 1px solid transparent;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn:hover:not(:disabled) { border-bottom-color: currentColor; }
.btn.primary { color: var(--ch-primary); text-decoration: underline; text-underline-offset: 5px; }
.btn.danger { color: var(--ch-red); }
.rc-error { color: var(--ch-red); font: 500 11px/1.5 var(--ch-serif); margin-top: 9px; }
@media (max-width: 620px) {
  .rc-body { grid-template-columns: 1fr; }
  .rc-caption { border-right: 0; border-bottom: 1px dotted rgba(110, 103, 93, .48); padding: 10px 0; }
  .rc-copy { padding: 14px 0 18px; }
}
</style>
