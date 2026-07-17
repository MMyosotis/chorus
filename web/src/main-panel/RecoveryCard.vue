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
    <StageHeader :number="stepNo" :title="`${roleName} · 需要处理`" english="RECOVERY DESK" status="待重试" status-tone="danger" />

    <div class="recovery-sheet">
      <header class="rc-mast">
        <div class="rc-kicker">中断记录 <small>INTERRUPTION NOTE</small></div>
        <div class="rc-preserved"><i aria-hidden="true"></i>已完成内容保留</div>
      </header>

      <div class="rc-copy">
        <div class="rc-section-label">异常说明 · ISSUE</div>
        <p class="rc-lead">本阶段未能完成，核对下方说明后可从当前步骤继续。</p>
        <div v-if="task.error" class="rc-error-text" role="status">{{ task.error }}</div>

        <div class="rc-feedback-group">
          <div class="rc-feedback-head">
            <label :for="feedbackId">重试批注</label>
            <small>可选 · 会随重试一并提交</small>
          </div>
          <textarea :id="feedbackId" v-model="feedback" class="rc-feedback"
            placeholder="补充重新执行时需要注意的方向" rows="2" />
        </div>

        <footer class="rc-actions">
          <span>重试只会重新执行本阶段</span>
          <div class="rc-action-buttons">
            <button class="btn danger" :disabled="busy" @click="onCancel">放弃整条创作</button>
            <button class="btn primary" :disabled="busy" @click="onRetry">{{ busy ? '正在处理…' : '重试本步' }}</button>
          </div>
        </footer>
        <div v-if="error" class="rc-error" role="alert">{{ error }}</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.recovery-card {
  margin: 0 0 24px;
  padding: 0 0 24px;
  border: 0;
}
.recovery-sheet {
  border-top: 2px solid rgba(27, 25, 22, .9);
  border-bottom: 1px solid rgba(27, 25, 22, .62);
  background: var(--ch-slip-soft);
}
.rc-mast {
  min-height: 42px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 0 16px;
  border-bottom: 3px double rgba(27, 25, 22, .72);
}
.rc-kicker {
  display: flex;
  align-items: baseline;
  gap: 9px;
  color: var(--ch-warm);
  font: 600 12px/1.2 var(--ch-serif);
  letter-spacing: .06em;
}
.rc-kicker small {
  color: var(--ch-muted);
  font: 600 9px/1 var(--ch-sans);
  letter-spacing: .12em;
}
.rc-preserved {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: var(--ch-green);
  font: 600 11px/1 var(--ch-serif);
  white-space: nowrap;
}
.rc-preserved i { width: 5px; height: 5px; border-radius: 50%; background: currentColor; }
.rc-copy { min-width: 0; padding: 20px 16px 16px; }
.rc-section-label { margin-bottom: 7px; color: var(--ch-muted); font: 600 9px/1.2 var(--ch-sans); letter-spacing: .13em; }
.rc-lead { margin: 0 0 12px; color: var(--ch-text); font: 600 var(--ch-chat-subtitle-size)/1.75 var(--ch-serif); letter-spacing: .01em; }
.rc-error-text {
  padding: 10px 12px;
  border-left: 2px solid rgba(161, 47, 36, .62);
  background: rgba(161, 47, 36, .055);
  color: var(--ch-red);
  font: 500 var(--ch-chat-note-size)/1.75 var(--ch-serif);
}
.rc-feedback-group { margin-top: 18px; padding-top: 15px; border-top: 1px dotted rgba(110, 103, 93, .48); }
.rc-feedback-head { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin-bottom: 7px; }
.rc-feedback-head label { color: var(--ch-body); font: 600 12px/1.3 var(--ch-serif); letter-spacing: .04em; }
.rc-feedback-head small { color: var(--ch-muted); font: 500 10px/1.3 var(--ch-serif); }
.rc-feedback {
  width: 100%; box-sizing: border-box;
  min-height: 72px;
  border: 1px solid var(--ch-border-2);
  border-radius: 0;
  background: rgba(255, 253, 248, .65);
  padding: 11px 13px;
  color: var(--ch-text);
  font: 500 13px/1.65 var(--ch-serif);
  resize: vertical;
}
.rc-feedback::placeholder { color: var(--ch-faint); }
.rc-actions {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: 16px;
  margin-top: 2px;
}
.rc-actions > span { margin-right: auto; color: var(--ch-muted); font: 500 11px/1.5 var(--ch-serif); }
.rc-action-buttons { display: flex; align-items: center; gap: 12px; }
.btn {
  min-height: 44px;
  padding: 0 4px;
  border: 0;
  background: transparent;
  color: var(--ch-muted);
  font: 500 13px/1 var(--ch-serif);
  white-space: nowrap;
  cursor: pointer;
  transition: color .18s ease;
}
.btn:disabled { color: var(--ch-faint); opacity: .55; cursor: default; }
.btn.primary { color: var(--ch-warm); font-weight: 600; text-decoration: underline; text-decoration-thickness: 1px; text-underline-offset: 5px; }
.btn.primary:hover:not(:disabled) { color: var(--ch-text); }
.btn.danger:hover:not(:disabled) { color: var(--ch-red); }
.rc-error { margin: 2px 0 0; color: var(--ch-red); font: 500 11px/1.55 var(--ch-serif); }
@media (max-width: 620px) {
  .rc-mast { align-items: flex-start; flex-direction: column; gap: 5px; padding-block: 10px; }
  .rc-feedback-head { align-items: flex-start; flex-direction: column; gap: 4px; }
  .rc-actions { align-items: flex-start; flex-direction: column; gap: 0; }
  .rc-action-buttons { width: 100%; justify-content: space-between; }
}
</style>
