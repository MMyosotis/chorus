<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { getTaskActivities } from '../api.js'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({
  task: { type: Object, default: null }, // graph.tasks 项
})

const activities = ref([])
const expanded = ref(false)
const loading = ref(false)
let timer = null

async function loadMore() {
  if (!props.task) return
  const tid = props.task.id
  // running 才轮询；非 running 拉一次全量
  const isRunning = props.task.status === 'running'
  if (!isRunning && timer) return
  loading.value = true
  try {
    const data = await getTaskActivities(tid, { limit: 100 })
    activities.value = data.activities
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
  loadMore()
  // running 时轮询全量；非 running 不起 timer
  if (props.task && props.task.status === 'running') {
    timer = setInterval(() => loadMore(), 1500)
  }
}

watch(() => props.task?.id, () => { activities.value = []; expanded.value = false; start() }, { immediate: true })
watch(() => props.task?.status, (s) => {
  if (s !== 'running') { stop(); loadMore() }
  else if (!timer) { start() }
})

// 卸载时清理定时器：Dock mode 翻转（如另一任务 → failed）会卸载本组件，
// 此时 task 仍 running、status watcher 不会触发 stop，需在此兜底，避免泄漏与对陈旧 task.id 的轮询
onUnmounted(stop)

const roleName = computed(() => ROLE_LABELS[props.task?.agent_type] || props.task?.agent_type || '')
const current = computed(() => props.task?.current_activity || activities.value[activities.value.length - 1] || null)
const roleLine = computed(() => {
  if (current.value?.role_line) return current.value.role_line
  if (props.task?.status === 'pending') return `${roleName.value}正在等待前序角色完成。`
  if (props.task?.status === 'finished') return props.task?.narrative?.done_line || `${roleName.value}已经完成这一步。`
  return `${roleName.value || '角色'}准备接手。`
})
const progress = computed(() => current.value?.progress_json || null)
const recent = computed(() => activities.value.slice(-2))
// 展开时显示全部活动（倒序：最新在上），否则只显最近 2 条
const shownActivities = computed(() => expanded.value ? [...activities.value].reverse() : recent.value)
</script>

<template>
  <div class="activity-preview">
    <div class="dock-label">PIPELINE FOCUS DOCK · 当前焦点</div>
    <div class="ap-main">
      <span class="role-avatar">{{ roleName.slice(0, 1) }}</span>
      <div class="ap-copy">
        <div class="ap-title">{{ roleName }}正在推进</div>
        <div class="ap-line">{{ roleLine }}</div>
      </div>
      <span class="detail-pill" @click="expanded = !expanded">
        {{ expanded ? '收起' : '查看详情' }}
      </span>
    </div>

    <div v-if="progress?.total" class="mini-progress">
      <span>第 {{ progress.current }}/{{ progress.total }} {{ progress.unit || '' }}</span>
      <div class="mini-track">
        <i :style="{ width: Math.min(100, Math.round((progress.current / progress.total) * 100)) + '%' }"></i>
      </div>
    </div>

    <div v-if="shownActivities.length" class="ap-list">
      <div v-for="a in shownActivities" :key="a.id" class="ap-item" :class="a.status">
        <span class="ap-dot" :class="a.status" />
        <span class="ap-recent-line">{{ a.role_line }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.activity-preview {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px 28px;
}
.dock-label {
  color: #c2410c;
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.1em;
}
.ap-main {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
}
.role-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--ch-orange-mid), var(--ch-orange));
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 850;
  box-shadow: 0 8px 18px rgba(234, 88, 12, 0.22);
}
.ap-copy {
  min-width: 0;
}
.ap-title {
  font-size: 13px;
  color: var(--ch-text);
  font-weight: 760;
  margin-bottom: 6px;
}
.ap-line {
  font-size: 14px;
  line-height: 1.45;
  color: var(--ch-body);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.detail-pill {
  border: 1px solid var(--ch-orange-mid);
  background: #fff;
  color: #c2410c;
  border-radius: 999px;
  padding: 8px 18px;
  font-size: 11px;
  font-weight: 850;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.detail-pill:hover { background: var(--ch-orange-mid); color: #fff; }
.mini-progress {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 12px;
  color: #c2410c;
  font-size: 12px;
  font-weight: 760;
}
.mini-track {
  height: 6px;
  border-radius: 999px;
  background: #fed7aa;
  overflow: hidden;
}
.mini-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--ch-orange-mid), var(--ch-orange));
}
.ap-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-left: 48px;
}
.ap-item {
  display: flex;
  gap: 10px;
  align-items: center;
  min-width: 0;
}
.ap-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: var(--ch-faint);
}
.ap-dot.running { background: var(--ch-orange-mid); animation: softPulse 1.4s ease-in-out infinite; }
.ap-dot.done { background: var(--ch-green-mid); }
.ap-dot.warning { background: var(--ch-amber); }
.ap-dot.failed { background: #f87171; }
.ap-recent-line {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--ch-muted);
}

@keyframes softPulse {
  0%, 100% { opacity: 0.62; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.12); }
}

@media (max-width: 760px) {
  .activity-preview {
    padding: 18px;
  }
  .ap-main {
    grid-template-columns: 36px minmax(0, 1fr);
  }
  .detail-pill {
    display: none;
  }
}
</style>
