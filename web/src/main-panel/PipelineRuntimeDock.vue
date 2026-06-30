<script setup>
import { computed } from 'vue'
import AgentActivityPreview from './AgentActivityPreview.vue'
import AgentWorkCard from './AgentWorkCard.vue'
import RecoveryCard from './RecoveryCard.vue'
import FinishWrapCard from './FinishWrapCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  expanded: { type: Boolean, default: false },
  sessionId: { type: String, default: '' },
})
const emit = defineEmits(['focus', 'expand', 'hil-confirmed', 'hil-retried', 'hil-cancelled', 'finish-done'])

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
    <!-- HIL：复用主面板 ChatWindow 的 HilCard 注入路径；Dock 这里只对 failed/activity 渲染。
         HIL 仍由 injectTaskCards 注入消息流，Dock 不重复，避免双卡。 -->
    <template v-if="mode.kind === 'failed'">
      <RecoveryCard :task="mode.task" :session-id="sessionId"
        @retried="$emit('hil-retried', $event)" @cancelled="$emit('hil-cancelled', $event)" />
    </template>
    <template v-else-if="mode.task">
      <AgentWorkCard :task="mode.task" />
      <AgentActivityPreview v-if="mode.kind === 'detail' || mode.kind === 'activity'" :task="mode.task" />
      <FinishWrapCard :task="mode.task" @done="$emit('finish-done', $event)" />
    </template>
  </div>
</template>

<style scoped>
.runtime-dock { border-top: 1px solid rgba(226, 232, 240, 0.55);
  background: rgba(255, 255, 255, 0.55); padding: 12px 16px; flex-shrink: 0;
  display: flex; flex-direction: column; gap: 10px; max-height: 320px; overflow-y: auto; }
</style>
