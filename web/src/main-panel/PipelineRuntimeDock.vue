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

// 交互卡归 ChatStream；Dock 只负责遥测。HIL/failed 时也显示对应 task 的只读活动，不放按钮。
const mode = computed(() => {
  const ts = tasks.value
  const hil = ts.find((t) => t.status === 'awaiting_confirm')
  if (hil) return { kind: 'activity', task: hil }
  const failed = ts.find((t) => t.status === 'failed')
  if (failed) return { kind: 'activity', task: failed }
  // 默认：焦点任务活动流（无焦点则取当前 running，再退到末位任务）
  const t = focusedTask.value || ts.find((x) => x.status === 'running') || ts[ts.length - 1]
  return { kind: 'activity', task: t }
})
</script>

<template>
  <div v-if="tasks.length" class="runtime-dock">
    <!-- Dock 纯遥测：只渲染一张 ActivityPreview 焦点卡。
         交互卡（HilCard / RecoveryCard / PostCard）归 ChatStream，经 injectTaskCards 注入消息流——Dock 不重复，避免双卡。
         hil(awaiting_confirm) 与 failed 在 Dock 仍显示只读活动，不放按钮。 -->
    <template v-if="mode.kind === 'activity'">
      <AgentActivityPreview :task="mode.task" />
      <FinishWrapCard :task="mode.task" @done="$emit('finish-done', $event)" />
    </template>
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
