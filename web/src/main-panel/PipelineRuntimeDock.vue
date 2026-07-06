<script setup>
// 运行时遥测面板：只显示焦点任务活动与收尾卡，交互卡由消息流注入避免重复
import { computed } from 'vue'
import AgentActivityPreview from './AgentActivityPreview.vue'
import FinishWrapCard from './FinishWrapCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  sessionId: { type: String, default: '' },
})
const emit = defineEmits(['finish-done'])

const tasks = computed(() => props.graph?.tasks || [])

const focusedTask = computed(() => tasks.value.find((t) => t.id === props.focusedTaskId) || null)

const hasInteraction = computed(() =>
  tasks.value.some((t) => t.status === 'awaiting_confirm' || t.status === 'failed')
)

const activityTask = computed(() => {
  if (hasInteraction.value) return null
  // 有进行中任务则跟踪焦点，否则回看用户选中的角色
  const running = tasks.value.find((x) => x.status === 'running')
  if (running) {
    return (focusedTask.value && focusedTask.value.status === 'running') ? focusedTask.value : running
  }
  return focusedTask.value || tasks.value.find((t) => t.agent_type === 'finalize' && t.status === 'finished') || null
})

const finalizeFinished = computed(() =>
  tasks.value.find((t) => t.status === 'finished' && t.agent_type === 'finalize') || null
)

const visible = computed(() => tasks.value.length > 0 && (activityTask.value || finalizeFinished.value))
</script>

<template>
  <div v-if="visible" class="runtime-dock">
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
