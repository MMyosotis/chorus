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

const pulse = computed(() => {
  if (props.task.status === 'running') return props.task.current_activity?.role_line || ''
  if (props.task.status === 'awaiting_confirm') return narrative.value.awaiting_line || ''
  if (props.task.status === 'finished') return narrative.value.done_line || ''
  if (props.task.status === 'failed') return '这步失败了'
  return ''
})

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
        <span class="role-name">{{ roleName }}</span>
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
  border: 1px solid var(--ch-border);
  border-radius: 20px;
  background: #fff;
  padding: 16px 18px;
  transition: box-shadow 0.18s, border-color 0.18s, background 0.18s, transform 0.18s;
}
.role-card.running {
  background: var(--ch-orange-soft);
  border-color: var(--ch-orange-mid);
  box-shadow: 0 0 0 2px rgba(251, 146, 60, 0.18), 0 14px 28px rgba(234, 88, 12, 0.10);
}
.role-card.waiting { background: #fffbeb; border-color: #fbbf24; }
.role-card.done { background: var(--ch-green-soft); border-color: #bbf7d0; }
.role-card.failed { background: var(--ch-red-soft); border-color: #fecaca; }
.role-head { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.role-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: linear-gradient(135deg, var(--ch-orange-mid), var(--ch-orange));
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 15px; font-weight: 850; flex-shrink: 0;
}
.role-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.role-name { font-size: 13px; color: var(--ch-text); font-weight: 760; }
.role-badge { font-size: 11px; font-weight: 850; padding: 2px 7px; border-radius: 999px; width: fit-content; }
.role-badge.idle { background: #f1f5f9; color: var(--ch-muted); }
.role-badge.running { background: #fed7aa; color: #c2410c; }
.role-badge.waiting { background: rgba(251, 191, 36, 0.18); color: #b45309; }
.role-badge.done { background: rgba(52, 211, 153, 0.18); color: #047857; }
.role-badge.failed, .role-badge.cancelled { background: rgba(248, 113, 113, 0.15); color: #b91c1c; }
.role-line { margin-top: 10px; font-size: 12px; line-height: 1.55; color: var(--ch-muted); }
.role-line.done { color: #047857; }
.role-hint { margin-top: 8px; font-size: 12px; color: var(--ch-orange); font-weight: 700; }
.role-error { margin-top: 8px; font-size: 12px; color: #b91c1c; }
.role-card.focused {
  border-color: var(--ch-orange-mid);
  box-shadow: 0 0 0 2px rgba(251, 146, 60, 0.2), 0 16px 32px rgba(234, 88, 12, 0.12);
  transform: translateY(-1px);
}
.role-line.running { color: #c2410c; }
.role-line.failed { color: #b91c1c; }
</style>
