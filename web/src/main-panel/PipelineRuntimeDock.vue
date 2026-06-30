<script setup>
import { computed } from 'vue'
import AgentActivityPreview from './AgentActivityPreview.vue'
import FinishWrapCard from './FinishWrapCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  sessionId: { type: String, default: '' },
})
const emit = defineEmits(['finish-done'])

const tasks = computed(() => {
  const ts = props.graph?.tasks || []
  return [...ts].sort((a, b) => a.seq - b.seq)
})

const focusedTask = computed(() => tasks.value.find((t) => t.id === props.focusedTaskId) || null)

// 交互卡归 ChatStream（verdict B：Dock 纯遥测）。
// awaiting_confirm / failed 时 Dock 不渲染活动卡——按钮在 ChatStream 的 HilCard / RecoveryCard，
// 这里再显示就会双卡。FinishWrapCard 独立绑 finalize finished，与活动卡解耦。
const hasInteraction = computed(() =>
  tasks.value.some((t) => t.status === 'awaiting_confirm' || t.status === 'failed')
)

const activityTask = computed(() => {
  if (hasInteraction.value) return null
  // 有 running：自动跟踪进行中任务（焦点 running 优先）——遥测。
  // 无 running：回看模式——用户点了哪个 RoleCard 显示哪个；未点则默认
  // 显示 finalize finished（成品作者）作为入口，供"查看详情"展开。
  const running = tasks.value.find((x) => x.status === 'running')
  if (running) {
    return (focusedTask.value && focusedTask.value.status === 'running') ? focusedTask.value : running
  }
  return focusedTask.value || tasks.value.find((t) => t.agent_type === 'finalize' && t.status === 'finished') || null
})

const finalizeFinished = computed(() =>
  tasks.value.find((t) => t.status === 'finished' && t.agent_type === 'finalize') || null
)

// Dock 可见：有活动卡或收尾卡时才渲染，避免 HIL/failed 时空框
const visible = computed(() => tasks.value.length > 0 && (activityTask.value || finalizeFinished.value))
</script>

<template>
  <div v-if="visible" class="runtime-dock">
    <!-- Dock 纯遥测：只渲染一张 ActivityPreview 焦点卡 + 收尾卡。
         交互卡（HilCard / RecoveryCard / PostCard）归 ChatStream，经 injectTaskCards 注入消息流——
         Dock 不重复，避免双卡。awaiting_confirm / failed 时 Dock 整体退场。 -->
    <AgentActivityPreview v-if="activityTask" :task="activityTask" />
    <FinishWrapCard v-if="finalizeFinished" :task="finalizeFinished" @done="$emit('finish-done', $event)" />
  </div>
</template>

<style scoped>
.runtime-dock {
  width: min(var(--ch-runtime-width), calc(100% - 32px));
  margin: 0 auto 10px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  border-radius: var(--ch-radius-lg);
  border: 1px solid var(--ch-orange-border);
  background: linear-gradient(135deg, var(--ch-orange-soft) 0%, var(--ch-violet-soft) 100%);
  box-shadow: 0 14px 32px rgba(234, 88, 12, 0.08), 0 1px 0 rgba(255, 255, 255, 0.8) inset;
  overflow: hidden;
  animation: dockIn 180ms ease-out;
}

@keyframes dockIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
