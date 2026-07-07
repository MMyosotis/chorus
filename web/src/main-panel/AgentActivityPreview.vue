<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import { getTaskActivities } from '../api.js'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({
  task: { type: Object, default: null },
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

onUnmounted(stop)

const roleName = computed(() => ROLE_LABELS[props.task?.agent_type] || props.task?.agent_type || '')
const current = computed(() => props.task?.current_activity || activities.value[activities.value.length - 1] || null)
const roleLine = computed(() => {
  if (current.value?.role_line) return current.value.role_line
  if (props.task?.status === 'pending') return `${roleName.value}正在等待前序角色完成。`
  if (props.task?.status === 'finished') return props.task?.narrative?.done_line || `${roleName.value}已经完成这一步。`
  return `${roleName.value || '角色'}准备接手。`
})
const progress = computed(() => current.value?.payload?.total ? current.value.payload : null)
const recent = computed(() => activities.value.slice(-2))
const history = computed(() => activities.value.slice(0, -2))
</script>

<template>
  <div class="activity-preview">
    <div class="ap-main">
      <span :class="['role-avatar', { running: task?.status === 'running' }]">{{ roleName.slice(0, 1) }}</span>
      <div class="ap-copy">
        <div class="ap-title">{{ roleName }}</div>
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

    <div class="ap-list">
      <div v-if="history.length" class="ap-history-wrap" :class="{ expanded }">
        <div class="ap-history-inner">
          <div v-for="a in history" :key="a.id" class="ap-item" :class="a.status">
            <span class="ap-dot" :class="a.status" />
            <span class="ap-recent-line">{{ a.role_line }}</span>
          </div>
        </div>
      </div>
      <div v-for="a in recent" :key="a.id" class="ap-item" :class="a.status">
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
  padding: 18px 28px;
}
.ap-main {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto;
  align-items: start;
  gap: 14px;
}
.role-avatar {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: var(--ch-bg-cool);
  color: var(--ch-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--ch-serif);
  font-size: 15px;
  font-weight: 700;
}
.role-avatar.running {
  background: var(--ch-orange-soft);
  color: var(--ch-orange-2);
}
.ap-copy {
  min-width: 0;
}
.ap-title {
  font-size: 14px;
  color: var(--ch-text);
  font-family: var(--ch-serif);
  font-weight: 600;
  margin-bottom: 6px;
}
.ap-line {
  font-size: 13px;
  line-height: 1.5;
  color: var(--ch-body);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.detail-pill {
  background: var(--ch-primary-soft);
  color: var(--ch-primary-2);
  border: 1px solid transparent;
  border-radius: 999px;
  padding: 8px 16px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background 0.15s;
}
.detail-pill:hover { background: color-mix(in srgb, var(--ch-primary) 14%, var(--ch-primary-soft)); }
.mini-progress {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  gap: 12px;
  color: var(--ch-muted);
  font-size: 12px;
  font-weight: 600;
}
.mini-track {
  height: 6px;
  border-radius: 999px;
  background: var(--ch-border);
  overflow: hidden;
}
.mini-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--ch-orange);
}
.ap-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-left: 50px;
}
.ap-history-wrap {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s ease;
}
.ap-history-wrap.expanded {
  grid-template-rows: 1fr;
}
.ap-history-inner {
  overflow: hidden;
  display: flex;
  flex-direction: column;
  gap: 8px;
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
.ap-dot.running { background: var(--ch-orange); animation: softPulse 1.4s ease-in-out infinite; }
.ap-dot.done { background: var(--ch-green); }
.ap-dot.warning { background: var(--ch-amber); }
.ap-dot.failed { background: var(--ch-red); }
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
