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

const seqNo = computed(() => {
  const source = props.state?.goal || props.state?.confirmation_summary?.title || ''
  let hash = 0
  for (let i = 0; i < source.length; i++) hash = (hash * 31 + source.charCodeAt(i)) >>> 0
  return 'No.' + String(hash % 10000).padStart(4, '0')
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
    <span class="knob" aria-hidden="true"></span>
    <div class="receipt-spine" aria-hidden="true">
      <span class="spine-tag">CONFIRM</span>
      <span class="spine-no">{{ seqNo }}</span>
      <span class="spine-seam"></span>
    </div>
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
    <div class="stamp-clip" aria-hidden="true">
      <span class="stamp-mark stamp-c" :class="stamp">
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
    </div>
  </section>
</template>

<style scoped>
.intent-confirm {
  position: relative;
  align-self: center;
  width: calc(100% - 96px);
  background: #fffdf7;
  border: 1px solid var(--ch-border-2);
  padding: 22px 60px 22px 22px;
  box-shadow:
    0 6px 16px -6px rgba(0, 0, 0, 0.05),
    0 2px 4px -1px rgba(0, 0, 0, 0.02);
  background-image:
    radial-gradient(rgba(120, 100, 70, 0.035) 1px, transparent 1px);
  background-size: 3px 3px;
}

.knob {
  position: absolute;
  top: -7px;
  left: 50%;
  transform: translateX(-50%);
  width: 15px;
  height: 15px;
  border-radius: 50%;
  background: var(--ch-primary);
  box-shadow:
    inset 0 1px 1.5px rgba(255, 255, 255, 0.55),
    inset 0 -1px 1.5px rgba(0, 0, 0, 0.18),
    0 2px 3px rgba(0, 0, 0, 0.25);
  z-index: 3;
}

/* 凭证脊:右侧竖排抬头+骑缝撕线连成一条,印章压在中段 */
.receipt-spine {
  position: absolute;
  top: 16px;
  bottom: 16px;
  right: 14px;
  width: 28px;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 4;
  pointer-events: none;
}

.receipt-spine .spine-tag {
  font-family: var(--ch-serif);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 2px;
  color: var(--ch-primary-2);
  writing-mode: vertical-rl;
  text-orientation: mixed;
  line-height: 1;
  padding-bottom: 6px;
}

.receipt-spine .spine-no {
  font-family: var(--ch-serif);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.5px;
  color: var(--ch-muted);
  writing-mode: vertical-rl;
  text-orientation: mixed;
  font-variant-numeric: tabular-nums;
  line-height: 1;
  padding-bottom: 8px;
}

.receipt-spine .spine-seam {
  flex: 1;
  width: 1px;
  background-image: linear-gradient(to bottom, var(--ch-border-2) 50%, transparent 0);
  background-size: 1px 5px;
  background-repeat: repeat-y;
  opacity: 0.8;
}

.confirm-title {
  font-family: var(--ch-serif);
  font-size: 16px;
  font-weight: 600;
  color: var(--ch-text);
  line-height: 1.5;
  text-align: center;
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

/* 盖章裁切层:覆盖整卡裁掉斜印溢出,不挡按钮 */
.stamp-clip {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 2;
}

/* 盖章标记:压在右侧骑缝撕线上,半探出右边被裁,常驻隐形,盖章时过渡显形 */
.stamp-mark {
  position: absolute;
  top: 55%;
  right: 28px;
  width: 116px;
  height: 116px;
  transform: translate(50%, -50%) rotate(-13deg) scale(2.2);
  opacity: 0;
  transition: opacity 0.16s ease-out, transform 0.4s cubic-bezier(0.18, 0.7, 0.3, 1);
}

.intent-confirm.stamped .stamp-mark {
  opacity: 1;
  transform: translate(50%, -50%) rotate(-13deg) scale(1);
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
