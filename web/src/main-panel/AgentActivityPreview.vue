<script setup>
import { ref, watch } from 'vue'
import { getTaskActivities } from '../api.js'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({
  task: { type: Object, default: null }, // graph.tasks 项
})

const activities = ref([])
const afterSeq = ref(0)
const loading = ref(false)
let timer = null

async function loadMore(initial = false) {
  if (!props.task) return
  const tid = props.task.id
  // running 才轮询；非 running 拉一次全量
  const isRunning = props.task.status === 'running'
  if (!initial && !isRunning) return
  loading.value = true
  try {
    const data = await getTaskActivities(tid, { limit: 100, afterSeq: initial ? null : afterSeq.value })
    if (initial) {
      activities.value = data.activities
    } else {
      activities.value.push(...data.activities)
    }
    if (data.activities.length) {
      afterSeq.value = data.activities[data.activities.length - 1].seq
    }
  } catch {
    // 忽略，下轮重试
  } finally {
    loading.value = false
  }
}

function stop() {
  if (timer) { clearInterval(timer); timer = null }
}

function start() {
  stop()
  loadMore(true)
  // running 时轮询增量；非 running 不起 timer
  if (props.task && props.task.status === 'running') {
    timer = setInterval(() => loadMore(false), 1500)
  }
}

watch(() => props.task?.id, () => { afterSeq.value = 0; activities.value = []; start() }, { immediate: true })
watch(() => props.task?.status, (s) => {
  if (s !== 'running') { stop(); loadMore(true) }
  else if (!timer) { start() }
})
</script>

<template>
  <div class="activity-preview">
    <div class="ap-title">{{ ROLE_LABELS[task?.agent_type] || '' }} · 活动过程</div>
    <div class="ap-list">
      <div v-for="a in activities" :key="a.seq" class="ap-item" :class="a.status">
        <span class="ap-dot" :class="a.status" />
        <div class="ap-body">
          <div class="ap-line">{{ a.role_line }}</div>
          <div v-if="a.summary_json" class="ap-summary">
            <span v-for="(b, i) in (a.summary_json.bullets || []).slice(0, 3)" :key="i" class="ap-bullet">{{ b.title }}</span>
          </div>
        </div>
      </div>
      <div v-if="!activities.length && loading" class="ap-empty">加载中…</div>
      <div v-else-if="!activities.length" class="ap-empty">暂无活动</div>
    </div>
  </div>
</template>

<style scoped>
.activity-preview { display: flex; flex-direction: column; gap: 8px; }
.ap-title { font-size: 13px; color: #64748b; font-weight: 500; }
.ap-list { display: flex; flex-direction: column; gap: 6px; max-height: 220px; overflow-y: auto; }
.ap-item { display: flex; gap: 8px; padding: 4px 0; }
.ap-dot { width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; flex-shrink: 0; background: #94a3b8; }
.ap-dot.running { background: #6366f1; }
.ap-dot.done { background: #34d399; }
.ap-dot.warning { background: #fbbf24; }
.ap-dot.failed { background: #f87171; }
.ap-body { min-width: 0; flex: 1; }
.ap-line { font-size: 13px; color: #334155; }
.ap-summary { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
.ap-bullet { font-size: 11px; color: #64748b; background: #f1f5f9; padding: 1px 6px; border-radius: 4px; }
.ap-empty { font-size: 12px; color: #94a3b8; padding: 8px 0; }
</style>
