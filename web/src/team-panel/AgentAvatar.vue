<script setup>
import { computed } from 'vue'

import { ROLE_INITIALS, ROLE_LABELS } from './roleMeta.js'

const props = defineProps({
  agentType: { type: String, default: 'chief' },
  status: { type: String, default: 'finished' },
  standby: { type: Boolean, default: false },
  inactive: { type: Boolean, default: false },
  size: { type: Number, default: 40 },
})

const online = computed(() => ['running', 'awaiting_confirm'].includes(props.status))
const label = computed(() => ROLE_LABELS[props.agentType] || '团队成员')
const initial = computed(() => ROLE_INITIALS[props.agentType] || '员')
</script>

<template>
  <span
    class="agent-avatar"
    :class="[{ online, standby, inactive }]"
    :style="{ '--avatar-size': `${size}px` }"
    :title="label"
    :aria-label="label"
  >
    {{ initial }}
    <i v-if="online" aria-hidden="true"></i>
  </span>
</template>

<style scoped>
.agent-avatar {
  position: relative;
  width: var(--avatar-size);
  height: var(--avatar-size);
  display: grid;
  flex: 0 0 var(--avatar-size);
  place-items: center;
  border: 1px solid var(--ch-accent-soft);
  border-radius: 50%;
  background: var(--ch-accent-soft);
  color: var(--ch-accent-soft-text);
  font-family: var(--ch-font-sans);
  font-size: 14px;
  font-weight: 600;
  line-height: 1;
}

.agent-avatar i {
  position: absolute;
  right: -2px;
  bottom: -2px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--ch-success);
  box-shadow: 0 0 0 2px var(--ch-accent-soft);
}

.agent-avatar.online i {
  animation: avatarPulse 1.8s ease-in-out infinite;
}

.agent-avatar.standby {
  opacity: .55;
  filter: saturate(.4);
}

.agent-avatar.inactive {
  border-color: var(--ch-border);
  background: var(--ch-surface-3);
  color: var(--ch-text-faint);
}

@keyframes avatarPulse {
  0%, 100% { opacity: .45; }
  50% { opacity: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .agent-avatar.online i { animation: none; }
}
</style>
