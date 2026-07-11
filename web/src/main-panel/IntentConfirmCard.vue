<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  state: { type: Object, default: null },
})

const emit = defineEmits(['confirm', 'revise'])

const stamp = ref('')

const slotItems = computed(() => {
  const slots = props.state?.known_slots || {}
  return Object.entries(slots)
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim() !== '')
    .slice(0, 8)
})
const locking = ref(false)

function approve() {
  if (locking.value) return
  locking.value = true
  stamp.value = 'approved'
  setTimeout(() => emit('confirm'), 650)
}

function reject() {
  if (locking.value) return
  locking.value = true
  stamp.value = 'rejected'
  setTimeout(() => emit('revise'), 650)
}
</script>

<template>
  <section class="intent-confirm" :class="[stamp && 'stamped', stamp]">
    <span class="seal">题旨·待确认</span>
    <div class="confirm-title">
      {{ state?.confirmation_summary?.title || state?.goal || '请确认这次创作方向' }}
    </div>
    <div v-if="slotItems.length" class="confirm-items">
      <template v-for="([label, value], idx) in slotItems" :key="idx">
        <span class="label">{{ label }}</span>
        <span class="value">{{ value }}</span>
      </template>
    </div>
    <div class="confirm-actions">
      <button class="primary" :disabled="locking" @click="approve">确认并开始</button>
      <span class="gap">·</span>
      <button class="secondary" :disabled="locking" @click="reject">继续调整</button>
    </div>
    <span v-if="stamp" class="stamp-mark stamp-c" :class="stamp">
        <svg viewBox="0 0 158 158" aria-hidden="true">
          <defs>
            <filter id="stamp-ink">
              <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" seed="7" result="noise" />
              <feDisplacementMap in="SourceGraphic" in2="noise" scale="2.5" xChannelSelector="R" yChannelSelector="G" result="disp" />
              <feGaussianBlur in="disp" stdDeviation="0.2" />
            </filter>
            <path id="arc-top" d="M 21 79 A 58 58 0 0 1 137 79" fill="none" />
            <path id="arc-bot" d="M 11 79 A 68 68 0 0 0 147 79" fill="none" />
          </defs>
          <g class="ink-group">
            <circle class="ring" cx="79" cy="79" r="76" />
            <text class="arc">
              <textPath href="#arc-top" startOffset="50%" text-anchor="middle">题旨确认专用</textPath>
            </text>
            <text class="si-mid" x="79" y="72" text-anchor="middle" dominant-baseline="central">{{ stamp === 'approved' ? '准' : '议' }}</text>
            <text class="arc">
              <textPath href="#arc-bot" startOffset="50%" text-anchor="middle">稿搭 · 七月十日</textPath>
            </text>
          </g>
        </svg>
      </span>
  </section>
</template>

<style scoped>
.intent-confirm {
  width: 100%;
  border-top: 3px double var(--ch-border-2);
  border-bottom: 3px double var(--ch-border-2);
  padding: 38px 0 14px;
  position: relative;
}

.seal {
  position: absolute;
  top: -11px;
  left: 50%;
  transform: translateX(-50%);
  font-family: var(--ch-serif);
  font-size: 11px;
  font-weight: 500;
  color: var(--ch-primary-2);
  letter-spacing: 1px;
  line-height: 1;
  padding: 5px 14px;
  border: 1px solid var(--ch-primary);
  background: var(--ch-surface);
}

.confirm-title {
  font-family: var(--ch-serif);
  font-size: 16px;
  font-weight: 600;
  color: var(--ch-text);
  line-height: 1.5;
  margin-bottom: 14px;
}

.confirm-items {
  display: grid;
  grid-template-columns: auto 1fr;
  column-gap: 18px;
  row-gap: 9px;
  font-size: 13px;
  align-items: baseline;
  margin-bottom: 16px;
}

.confirm-items .label {
  color: var(--ch-muted);
  font-size: 11px;
  letter-spacing: 0.5px;
  line-height: 1.6;
}

.confirm-items .value {
  color: var(--ch-text);
  font-family: var(--ch-serif);
  line-height: 1.6;
}

.confirm-actions {
  display: flex;
  justify-content: center;
  align-items: center;
  font-family: var(--ch-serif);
  font-size: 13.5px;
  margin-top: 14px;
}

.confirm-actions button {
  position: relative;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px 2px;
  font-family: inherit;
  font-size: inherit;
}

.confirm-actions button::after {
  content: '';
  position: absolute;
  left: 2px;
  bottom: 2px;
  width: 0;
  height: 1px;
  background: currentColor;
  transition: width 0.18s cubic-bezier(0.3, 0.7, 0.3, 1);
}

.confirm-actions button:hover:not(:disabled)::after {
  width: calc(100% - 4px);
}

.confirm-actions button:disabled {
  cursor: default;
  opacity: 0.4;
}

.confirm-actions .primary {
  color: var(--ch-orange-2);
  font-weight: 600;
}

.confirm-actions .secondary {
  color: var(--ch-muted);
}

.confirm-actions .gap {
  color: var(--ch-border-2);
  margin: 0 10px;
}

/* 盖章标记：斜放、SVG 圆印压在右侧，盖完不消失 */
.stamp-mark {
  position: absolute;
  top: 44%;
  right: 6%;
  width: 158px;
  height: 158px;
  transform: translateY(-50%) rotate(-13deg) scale(2.2);
  opacity: 0;
  pointer-events: none;
  z-index: 2;
  transition: opacity 0.16s ease-out, transform 0.4s cubic-bezier(0.18, 0.7, 0.3, 1);
}

.intent-confirm.stamped .stamp-mark {
  opacity: 1;
  transform: translateY(-50%) rotate(-13deg) scale(1);
}

.stamp-c {
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.stamp-c svg {
  width: 100%;
  height: 100%;
  display: block;
}

.stamp-c .ink-group {
  filter: url(#stamp-ink);
}

.stamp-c .arc {
  font-family: var(--ch-serif);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 1.5px;
  fill: currentColor;
}

.stamp-c .si-mid {
  font-family: 'Noto Serif SC', var(--ch-serif);
  font-size: 62px;
  font-weight: 700;
  fill: currentColor;
}

.stamp-c .ring {
  fill: none;
  stroke: currentColor;
  stroke-width: 2.5;
}

.stamp-c.approved {
  color: var(--ch-orange);
}

.stamp-c.rejected {
  color: var(--ch-muted);
}
</style>