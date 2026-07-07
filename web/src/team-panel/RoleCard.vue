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
  border-radius: 14px;
  background: #fff;
  padding: 16px 18px 14px;
  transition: box-shadow 0.18s, border-color 0.18s, background 0.18s, transform 0.18s;
}
.role-card.running {
  background: #ffffff;
  border-color: #cfd7e8;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
}
.role-card.waiting { background: #ffffff; border-color: #e7c56a; }
.role-card.done { background: #ffffff; border-color: #c8e7da; }
.role-card.failed { background: #ffffff; border-color: #f2c4c4; }
.role-head { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.role-avatar {
  width: 36px; height: 36px; border-radius: 50%;
  background: #eef2f7;
  color: #344054;
  display: flex; align-items: center; justify-content: center;
  font-size: 15px; font-weight: 780; flex-shrink: 0;
}
.role-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.role-name { font-size: 13px; color: var(--ch-text); font-weight: 760; }
.role-badge { font-size: 11px; font-weight: 760; padding: 0; border-radius: 0; width: fit-content; background: transparent; }
.role-badge.idle { background: #f1f5f9; color: var(--ch-muted); }
.role-badge.running { color: #b45309; }
.role-badge.waiting { color: #b45309; }
.role-badge.done { color: #047857; }
.role-badge.failed, .role-badge.cancelled { color: #b91c1c; }
.role-line { margin-top: 10px; font-size: 12px; line-height: 1.55; color: var(--ch-muted); }
.role-line.done { color: #047857; }
.role-hint { margin-top: 8px; font-size: 12px; color: #667085; font-weight: 600; }
.role-error { margin-top: 8px; font-size: 12px; color: #b91c1c; }
.role-card.focused {
  border-color: #cfd7e8;
  box-shadow: 0 0 0 2px rgba(207, 215, 232, 0.5), 0 12px 24px rgba(15, 23, 42, 0.08);
  transform: translateY(-1px);
}
.role-line.running { color: #b45309; }
.role-line.failed { color: #b91c1c; }
</style>
