<script setup>
import { computed } from 'vue'
import AgentActivityPreview from './AgentActivityPreview.vue'
import AgentWorkCard from './AgentWorkCard.vue'
import FinishWrapCard from './FinishWrapCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  expanded: { type: Boolean, default: false },
  sessionId: { type: String, default: '' },
})
const emit = defineEmits(['finish-done'])

const tasks = computed(() => {
  const ts = props.graph?.tasks || []
  return [...ts].sort((a, b) => a.seq - b.seq)
})

const focusedTask = computed(() => tasks.value.find((t) => t.id === props.focusedTaskId) || null)

// mode 优先级：hil > failed > detail(if expanded) > activity
const mode = computed(() => {
  const ts = tasks.value
  const hil = ts.find((t) => t.status === 'awaiting_confirm')
  if (hil) return { kind: 'hil', task: hil }
  const failed = ts.find((t) => t.status === 'failed')
  if (failed) return { kind: 'failed', task: failed }
  if (props.expanded && focusedTask.value) {
    return { kind: 'detail', task: focusedTask.value }
  }
  // 默认：焦点任务活动流（无焦点则取当前 running）
  const t = focusedTask.value || ts.find((x) => x.status === 'running') || ts[ts.length - 1]
  return { kind: 'activity', task: t }
})
</script>

<template>
  <div v-if="tasks.length" class="runtime-dock">
    <!-- Dock 纯遥测：仅渲染 detail/activity 的实时活动流（AgentWorkCard + AgentActivityPreview + FinishWrapCard）。
         交互卡（HilCard / RecoveryCard / PostCard）归 ChatStream，经 injectTaskCards 注入消息流——Dock 不重复，避免双卡。
         hil(awaiting_confirm) 与 failed 在 Dock 不渲染任何卡片（chat 流已承载交互）。 -->
    <template v-if="mode.kind === 'detail' || mode.kind === 'activity'">
      <AgentWorkCard :task="mode.task" />
      <AgentActivityPreview :task="mode.task" />
      <FinishWrapCard :task="mode.task" @done="$emit('finish-done', $event)" />
    </template>
  </div>
</template>

<style scoped>
.runtime-dock { border-top: 1px solid rgba(226, 232, 240, 0.55);
  background: rgba(255, 255, 255, 0.55); padding: 12px 16px; flex-shrink: 0;
  display: flex; flex-direction: column; gap: 10px; max-height: 320px; overflow-y: auto; }
</style>
