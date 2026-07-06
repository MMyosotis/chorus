<script setup>
import { ref } from 'vue'

import { cancelPipeline, confirmTask, retryTask } from '../api.js'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({
  task: { type: Object, required: true },
  sessionId: { type: String, required: true },
})
const emit = defineEmits(['confirmed', 'retried', 'cancelled'])

const roleName = ROLE_LABELS[props.task.agent_type] || props.task.agent_type
const artifacts = props.task.artifacts || {}

const selectedIdx = ref(artifacts.selected ?? null)
const feedback = ref('')
const busy = ref(false)
const error = ref('')

const needSelect = props.task.agent_type === 'idea'

async function onConfirm() {
  if (needSelect && selectedIdx.value == null) {
    error.value = '请先选择一个候选'
    return
  }
  busy.value = true
  error.value = ''
  try {
    await confirmTask(props.task.id, needSelect ? selectedIdx.value : null)
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
    await retryTask(props.task.id, { feedback: feedback.value || '' })
    emit('retried', props.task.id)
  } catch (e) {
    error.value = e.detail || e.message
  } finally {
    busy.value = false
  }
}

async function onCancel() {
  if (!confirm('放弃整条创作？此操作不可撤销。')) return
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
  <div class="hil-card">
    <div class="hil-title">{{ roleName }} · 等你确认</div>

    <div v-if="task.agent_type === 'idea'" class="hil-candidates">
      <div
        v-for="c in artifacts.candidates || []"
        :key="c.index"
        class="candidate"
        :class="{ selected: selectedIdx === c.index }"
        @click="selectedIdx = c.index"
      >
        <div class="cand-title">{{ c.title }}</div>
        <div class="cand-angle">{{ c.angle }}</div>
        <div class="cand-reason">{{ c.reason }}</div>
      </div>
    </div>

    <div v-else-if="task.agent_type === 'script'" class="hil-preview">
      <div v-for="(b, i) in artifacts.blocks || []" :key="i" :class="['block', b.kind]">
        {{ b.text }}
      </div>
    </div>

    <div v-else-if="task.agent_type === 'image'" class="hil-images">
      <figure v-for="(img, i) in artifacts.images || []" :key="i" class="img-item">
        <img :src="img.url" :alt="img.caption || ''" loading="lazy" />
        <figcaption v-if="img.caption">{{ img.caption }}</figcaption>
      </figure>
    </div>

    <div class="hil-actions">
      <button class="btn primary" :disabled="busy" @click="onConfirm">确认推进</button>
      <button class="btn" :disabled="busy" @click="onRetry">带意见重跑本步</button>
      <button class="btn danger" :disabled="busy" @click="onCancel">放弃整条</button>
    </div>
    <textarea
      v-model="feedback"
      class="hil-feedback"
      placeholder="（可选）对这步产出的意见，点「带意见重跑本步」生效"
      rows="2"
    />
    <div v-if="error" class="hil-error">{{ error }}</div>
  </div>
</template>

<style scoped>
.hil-card {
  border: 1px solid #fbbf24;
  border-radius: var(--ch-radius-md);
  background: #fffbeb;
  padding: 20px 22px;
  margin: 4px 0;
  box-shadow: 0 18px 38px rgba(180, 83, 9, 0.10);
}
.hil-title {
  font-size: 18px;
  font-weight: 850;
  color: #92400e;
  margin-bottom: 14px;
}
.hil-candidates { display: flex; flex-direction: column; gap: 8px; }
.candidate {
  border: 1px solid var(--ch-border); border-radius: 16px; padding: 12px 14px;
  cursor: pointer; background: #fff; transition: border-color 0.15s;
}
.candidate.selected { border-color: var(--ch-orange-mid); box-shadow: 0 0 0 3px rgba(251, 146, 60, 0.14); }
.cand-title { font-weight: 760; color: var(--ch-text); }
.cand-angle { font-size: 13px; color: #c2410c; margin-top: 2px; }
.cand-reason { font-size: 12px; color: var(--ch-muted); margin-top: 4px; }
.hil-preview .block { margin: 4px 0; }
.hil-preview .block.heading { font-weight: 500; color: #1e293b; }
.hil-preview .block.list { white-space: pre-wrap; color: #475569; }
.hil-images { display: flex; flex-wrap: wrap; gap: 8px; }
.img-item { margin: 0; }
.img-item img { width: 120px; height: 120px; object-fit: cover; border-radius: 16px; }
.img-item figcaption { font-size: 11px; color: var(--ch-muted); }
.hil-actions { display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }
.btn {
  border: 1px solid #cbd5e1; background: #fff; color: var(--ch-muted);
  padding: 8px 14px; border-radius: 999px; cursor: pointer; font-size: 13px; font-weight: 760;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn.primary { background: var(--ch-orange); border-color: var(--ch-orange); color: #fff; }
.btn.danger { color: #b91c1c; border-color: #fca5a5; }
.hil-feedback {
  width: 100%; margin-top: 10px; border: 1px solid var(--ch-border); border-radius: 14px;
  padding: 6px 8px; font-size: 13px; resize: vertical; box-sizing: border-box;
}
.hil-error { color: #b91c1c; font-size: 12px; margin-top: 6px; }
</style>
