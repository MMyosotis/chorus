<script setup>
import { computed } from 'vue'
import { ROLE_LABELS, badgeOf } from './roleMeta.js'

const props = defineProps({
  task: { type: Object, required: true },
  focused: { type: Boolean, default: false },
})
const emit = defineEmits(['focus'])

const roleName = computed(() => ROLE_LABELS[props.task.agent_type] || props.task.agent_type)
const badge = computed(() => badgeOf(props.task.status))
const narrative = computed(() => props.task.narrative || {})

// 状态脉搏：running 用 current_activity.role_line，否则用 narrative
const pulse = computed(() => {
  if (props.task.status === 'running') return props.task.current_activity?.role_line || ''
  if (props.task.status === 'awaiting_confirm') return narrative.value.awaiting_line || ''
  if (props.task.status === 'finished') return narrative.value.done_line || ''
  if (props.task.status === 'failed') return '这步失败了'
  return ''
})

// awaiting_confirm / failed：交互卡（HIL/Recovery）在对话流，这里只给一句引导，不放按钮
const needsChatAction = computed(() =>
  props.task.status === 'awaiting_confirm' || props.task.status === 'failed'
)

function onClick() {
  emit('focus', props.task.id)
}
</script>

<template>
  <div class="role-card" :class="[badge.cls, { focused }]">
    <div class="role-head" @click="onClick">
      <span class="role-avatar">{{ roleName.slice(0, 1) }}</span>
      <div class="role-info">
        <span class="role-name">{{ narrative.role_name || roleName }}</span>
        <span class="role-badge" :class="badge.cls">{{ badge.label }}</span>
      </div>
    </div>
    <div v-if="pulse" class="role-line" :class="badge.cls">{{ pulse }}</div>
    <div v-if="needsChatAction" class="role-hint">需要在对话中处理</div>
    <div v-if="task.error" class="role-error">{{ task.error }}</div>
  </div>
</template>

<style scoped>
.role-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  padding: 10px 12px;
  transition: box-shadow 0.18s, border-color 0.18s;
}
.role-card.running { border-color: rgba(99, 102, 241, 0.4); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.08); }
.role-card.waiting { border-color: rgba(251, 191, 36, 0.5); }
.role-card.done { border-color: rgba(52, 211, 153, 0.4); }
.role-card.failed { border-color: rgba(248, 113, 113, 0.5); }
.role-head { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.role-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, #818cf8, #6366f1);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 500; flex-shrink: 0;
}
.role-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.role-name { font-size: 14px; color: #1e293b; font-weight: 500; }
.role-badge { font-size: 12px; padding: 1px 6px; border-radius: 4px; width: fit-content; }
.role-badge.idle { background: #f1f5f9; color: #64748b; }
.role-badge.running { background: rgba(99, 102, 241, 0.12); color: #6366f1; }
.role-badge.waiting { background: rgba(251, 191, 36, 0.18); color: #b45309; }
.role-badge.done { background: rgba(52, 211, 153, 0.18); color: #047857; }
.role-badge.failed, .role-badge.cancelled { background: rgba(248, 113, 113, 0.15); color: #b91c1c; }
.role-line { margin-top: 8px; font-size: 13px; color: #475569; }
.role-line.done { color: #047857; }
.role-hint { margin-top: 6px; font-size: 12px; color: #6366f1; }
.role-error { margin-top: 6px; font-size: 12px; color: #b91c1c; }
.role-card.focused { border-color: rgba(99, 102, 241, 0.6); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12); }
.role-line.running { color: #6366f1; }
.role-line.failed { color: #b91c1c; }
</style>
