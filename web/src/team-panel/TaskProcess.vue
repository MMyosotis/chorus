<script setup>
import { ref, watch } from 'vue'

import { getTaskSteps } from '../api.js'

const props = defineProps({ task: { type: Object, required: true } })

const steps = ref([])
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    steps.value = await getTaskSteps(props.task.id)
  } catch (e) {
    error.value = e.status === 404 ? '任务不存在' : e.message
  } finally {
    loading.value = false
  }
}

watch(() => props.task.id, load, { immediate: true })
</script>

<template>
  <div class="task-process">
    <div class="tp-title">创作过程 · {{ task.agent_type }}</div>
    <div v-if="loading" class="tp-hint">加载中...</div>
    <div v-else-if="error" class="tp-error">{{ error }}</div>
    <div v-else-if="!steps.length" class="tp-hint">暂无过程记录</div>
    <details v-for="s in steps" :key="s.iteration" class="tp-iter" open>
      <summary>第 {{ s.iteration }} 轮 · {{ s.finish_reason || '进行中' }}</summary>
      <div v-if="s.thinking" class="tp-block">
        <span class="tp-label">思考</span>
        <pre class="tp-text">{{ s.thinking }}</pre>
      </div>
      <div v-if="s.text" class="tp-block">
        <span class="tp-label">正文</span>
        <pre class="tp-text">{{ s.text }}</pre>
      </div>
      <div v-if="s.tool_calls && s.tool_calls.length" class="tp-block">
        <span class="tp-label">工具调用</span>
        <pre class="tp-text">{{ JSON.stringify(s.tool_calls, null, 2) }}</pre>
      </div>
      <div v-if="s.tool_results && s.tool_results.length" class="tp-block">
        <span class="tp-label">工具结果</span>
        <pre class="tp-text">{{ JSON.stringify(s.tool_results, null, 2) }}</pre>
      </div>
    </details>
  </div>
</template>

<style scoped>
.task-process {
  font-size: 12px;
  color: #475569;
  padding: 10px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}
.tp-title { font-weight: 500; color: #1e293b; margin-bottom: 6px; }
.tp-hint, .tp-error { color: #94a3b8; }
.tp-error { color: #b91c1c; }
.tp-iter { margin-top: 6px; }
.tp-iter > summary { cursor: pointer; color: #6366f1; }
.tp-block { margin-top: 4px; }
.tp-label { color: #94a3b8; font-size: 11px; }
.tp-text {
  margin: 2px 0 6px;
  padding: 6px;
  background: #fff;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 160px;
  overflow-y: auto;
}
</style>
