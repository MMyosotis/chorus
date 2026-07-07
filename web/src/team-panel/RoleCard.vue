<script setup>
import { computed } from 'vue'
import { ROLE_LABELS, ROLE_TAG, stepOf, badgeOf } from './roleMeta.js'

const props = defineProps({
  task: { type: Object, required: true },
  focused: { type: Boolean, default: false },
})
const emit = defineEmits(['focus'])

const roleName = computed(() => ROLE_LABELS[props.task.agent_type] || props.task.agent_type)
const badge = computed(() => badgeOf(props.task.status))
const step = computed(() => stepOf(props.task.agent_type))
const roleTag = computed(() => ROLE_TAG[props.task.agent_type] || '')
const tagText = computed(() => `第 ${step.value} 步 · ${roleTag.value}`)
const narrative = computed(() => props.task.narrative || {})

const pulse = computed(() => {
  if (props.task.status === 'running') return props.task.current_activity?.role_line || ''
  if (props.task.status === 'awaiting_confirm') return narrative.value.awaiting_line || ''
  if (props.task.status === 'failed') return '这步失败了'
  return ''
})

const sumLine = computed(() =>
  props.task.status === 'finished' ? (narrative.value.done_line || '') : ''
)

const needsChatAction = computed(() =>
  props.task.status === 'awaiting_confirm' || props.task.status === 'failed'
)

function onClick() {
  emit('focus', props.task.id)
}
</script>

<template>
  <div class="role-card" :class="[badge.cls, { focused }]" @click="onClick">
    <div class="role-top">
      <span class="role-avatar" :class="badge.cls">{{ roleName.slice(0, 1) }}</span>
      <div class="role-info">
        <span class="role-name" v-tip="roleName">{{ roleName }}</span>
        <span class="role-tag" v-tip="tagText">{{ tagText }}</span>
      </div>
      <span class="role-badge" :class="badge.cls">
        <span v-if="badge.cls === 'running'" class="blip" aria-hidden="true"></span>
        {{ badge.label }}
      </span>
    </div>
    <div v-if="pulse" class="role-line" :class="badge.cls" v-tip="pulse">{{ pulse }}</div>
    <div v-else-if="sumLine" class="role-sum" v-tip="sumLine">{{ sumLine }}</div>
    <div v-if="needsChatAction" class="role-hint">需要在对话中处理</div>
    <div v-if="task.error" class="role-error">{{ task.error }}</div>
  </div>
</template>

<style scoped>
.role-card {
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-lg);
  background: var(--ch-surface);
  padding: 13px 14px;
  cursor: pointer;
  transition: box-shadow 0.18s, border-color 0.18s;
}
.role-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  border-color: var(--ch-border-2);
}

.role-card.running { --accent: var(--ch-orange); --accent-soft: var(--ch-orange-soft); }
.role-card.waiting { --accent: var(--ch-primary); --accent-soft: var(--ch-primary-soft); }
.role-card.done { --accent: var(--ch-green); --accent-soft: var(--ch-green-soft); }
.role-card.failed { --accent: var(--ch-red); --accent-soft: var(--ch-red-soft); }
.role-card.idle { --accent: var(--ch-border-2); --accent-soft: color-mix(in srgb, var(--ch-text) 8%, transparent); }

.role-top {
  display: flex;
  align-items: center;
  gap: 10px;
}

.role-avatar {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  background: var(--ch-bg-cool);
  color: var(--ch-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--ch-serif);
  font-size: 15px;
  font-weight: 700;
  flex-shrink: 0;
}
.role-avatar.running { background: var(--ch-orange); color: #fff; }
.role-avatar.waiting { background: var(--ch-primary-soft); color: var(--ch-primary-2); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ch-primary) 30%, transparent); }
.role-avatar.done { background: var(--ch-green-soft); color: var(--ch-green); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--ch-green) 30%, transparent); }
.role-avatar.failed { background: var(--ch-red-soft); color: var(--ch-red); }
.role-avatar.idle { background: var(--ch-bg-cool); color: var(--ch-muted); }

.role-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.role-name {
  font-family: var(--ch-serif);
  font-weight: 600;
  font-size: 13.5px;
  color: var(--ch-text);
  letter-spacing: 0.01em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-tag {
  font-size: 11px;
  color: var(--ch-faint);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}
.role-badge.running { background: var(--ch-orange-soft); color: var(--ch-orange-2); }
.role-badge.waiting { background: var(--ch-primary-soft); color: var(--ch-primary-2); }
.role-badge.done { background: var(--ch-green-soft); color: var(--ch-green); }
.role-badge.failed { background: var(--ch-red-soft); color: var(--ch-red); }
.role-badge.idle,
.role-badge.cancelled { background: var(--ch-bg-cool); color: var(--ch-muted); }

.blip {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ch-orange);
  animation: pulse 1.4s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

.role-line {
  margin-top: 8px;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--ch-muted);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.role-line.running { color: var(--ch-orange-2); }
.role-line.waiting { color: var(--ch-primary-2); }
.role-line.failed { color: var(--ch-red); }

.role-sum {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ch-green);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.role-hint {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ch-muted);
  font-weight: 600;
}

.role-error {
  margin-top: 8px;
  font-size: 12px;
  color: var(--ch-red);
}

.role-card.focused {
  border-color: var(--accent);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.05);
}
</style>
