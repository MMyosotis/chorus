<script setup>
import { computed } from 'vue'

import { ROLE_LABELS } from './roleMeta.js'

const props = defineProps({
  agentType: { type: String, default: 'chief' },
  status: { type: String, default: 'finished' },
  standby: { type: Boolean, default: false },
  inactive: { type: Boolean, default: false },
  size: { type: Number, default: 40 },
})

const online = computed(() => ['running', 'awaiting_confirm'].includes(props.status))
const label = computed(() => ROLE_LABELS[props.agentType] || '团队成员')
const avatarSrc = computed(() => {
  const assetName = ROLE_LABELS[props.agentType] ? props.agentType : 'chief'
  return `/team-avatars/${assetName}.png`
})
</script>

<template>
  <span
    class="agent-avatar"
    :class="[{ online, standby, inactive }]"
    :style="{ '--avatar-size': `${size}px` }"
    :title="label"
    :aria-label="label"
  >
    <img class="agent-avatar-image" :src="avatarSrc" alt="" aria-hidden="true" />
    <i aria-hidden="true"></i>
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
  border: 0;
  border-radius: 50%;
  transition: opacity var(--ch-duration-normal) var(--ch-ease);
}

.agent-avatar-image {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  object-fit: cover;
  transition: filter var(--ch-duration-normal) var(--ch-ease),
    opacity var(--ch-duration-normal) var(--ch-ease);
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
  opacity: 0;
  transform: scale(.4);
  transition: opacity var(--ch-duration-normal) var(--ch-ease),
    transform var(--ch-duration-normal) var(--ch-ease-out);
}

.agent-avatar.online i {
  opacity: 1;
  transform: scale(1);
  animation: avatarPulse 1.8s ease-in-out infinite;
}

.agent-avatar.standby {
  opacity: .65;
}

.agent-avatar.standby .agent-avatar-image,
.agent-avatar.inactive .agent-avatar-image {
  filter: grayscale(1) saturate(.12);
}

.agent-avatar.inactive .agent-avatar-image {
  opacity: .58;
}

@keyframes avatarPulse {
  0%, 100% { box-shadow: 0 0 0 2px var(--ch-accent-soft); }
  50% { box-shadow: 0 0 0 5px color-mix(in srgb, var(--ch-accent-soft) 40%, transparent); }
}

@media (prefers-reduced-motion: reduce) {
  .agent-avatar.online i { animation: none; }
}
</style>
