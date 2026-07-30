<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import HilRecap from './HilRecap.vue'
import AgentAvatar from '../team-panel/AgentAvatar.vue'
import { resolveActivityState } from '../composables/messageActivity.js'

const props = defineProps({
  role: { type: String, required: true },
  content: { type: String, required: true },
  active: { type: Boolean, default: false },
  thinking: {
    type: Object,
    default: () => ({ state: 'idle' }),
  },
  tools: {
    type: Object,
    default: () => ({ state: 'idle', items: [] }),
  },
  recaps: { type: Array, default: () => [] },
  suspended: { type: Boolean, default: false },
})

marked.setOptions({ breaks: true, gfm: true })

const formattedContent = computed(() => {
  if (props.role === 'user') {
    return props.content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/\n/g, '<br>')
  }
  const html = marked.parse(props.content || '')
  return DOMPurify.sanitize(html)
})

const bareMode = computed(() =>
  props.role === 'assistant' && !props.content && (props.active || props.recaps.length > 0)
)

const activityState = computed(() => resolveActivityState(props))

const runningTool = computed(() => {
  const items = props.tools.items || []
  for (let i = items.length - 1; i >= 0; i--) {
    if (items[i].duration_ms == null) return items[i]
  }
  return null
})

const activityLabel = computed(() => {
  if (activityState.value === 'thinking') return '正在思考'
  if (activityState.value === 'tools') {
    const label = runningTool.value?.running_label || '处理'
    const action = label.replace(/^正在/, '').replace(/中$/, '')
    return `正在${action}`
  }
  if (activityState.value === 'preparing') return '正在准备'
  return ''
})

const imageItems = computed(() =>
  (props.tools.items || []).filter((it) => it.name === 'generate_image')
)

const planItems = computed(() =>
  (props.tools.items || []).filter(
    (it) => it.name === 'output_plan' && it.duration_ms != null
  )
)

const hideBody = computed(() =>
  props.suspended && !props.content && !planItems.value.length
)

const showActions = computed(() =>
  props.role === 'assistant' && !!props.content && props.content.trim().length > 0 && !props.active
)

const feedback = ref(null)
const copied = ref(false)
let copyTimer = null

function toggleFeedback(kind) {
  feedback.value = feedback.value === kind ? null : kind
}

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.content || '')
    copied.value = true
    if (copyTimer) clearTimeout(copyTimer)
    copyTimer = setTimeout(() => { copied.value = false }, 1500)
  } catch {
    // 剪贴板不可用时静默
  }
}

function extractImageUrl(content) {
  if (typeof content !== 'string') return ''
  const s = content.trim()
  if (!s) return ''
  const m1 = s.match(/^(https?:\/\/\S+)$/i)
  if (m1) return m1[1]
  const m2 = s.match(/!\[[^\]]*\]\((https?:\/\/[^\s)]+)\)/)
  if (m2) return m2[1]
  return ''
}

function isImageReady(item) {
  return item.duration_ms != null && !!extractImageUrl(item.content)
}

function isImageError(item) {
  return (
    item.duration_ms != null &&
    typeof item.content === 'string' &&
    item.content.trim() !== '' &&
    !extractImageUrl(item.content)
  )
}

function imageSrc(item) {
  return extractImageUrl(item.content)
}

function imageAlt(item) {
  const p = item.arguments?.prompt || ''
  return p.length > 80 ? p.slice(0, 80) : p
}

const previewSrc = ref('')
const previewAlt = ref('')

function openPreview(item) {
  const src = imageSrc(item)
  if (!src) return
  previewSrc.value = src
  previewAlt.value = imageAlt(item)
}

function closePreview() {
  previewSrc.value = ''
  previewAlt.value = ''
}
</script>

<template>
  <div :class="['bubble-row', role, { bare: bareMode }]">
    <div v-if="role === 'assistant'" class="turn-head">
      <AgentAvatar agent-type="chief" status="finished" :size="40" />
      <span class="role">主编辑</span>
      <div
        v-if="activityState !== 'idle'"
        class="status-card"
        :class="activityState"
        aria-live="polite"
      >
        <span class="label-stage">
          <Transition name="label-swap">
            <span class="status-text" :key="activityLabel">{{ activityLabel }}</span>
          </Transition>
        </span>
      </div>
    </div>
    <div :class="['bubble', role, { bare: bareMode }]">
      <div v-if="!hideBody" :class="role === 'user' ? 'u-body' : 'a-body'">
        <div v-if="planItems.length" class="plan-list">
          <div v-for="(item, idx) in planItems" :key="`plan-${idx}`" class="plan-card">
            <div class="plan-header">执行计划</div>
            <ol class="plan-steps">
              <li v-for="(step, i) in (item.arguments?.steps || [])" :key="i">{{ step }}</li>
            </ol>
          </div>
        </div>
        <div v-if="content" class="text" v-html="formattedContent"></div>
      </div>

      <div v-if="imageItems.length" class="image-list">
        <div v-for="(item, idx) in imageItems" :key="`img-${idx}`" class="image-item">
          <Transition name="image-reveal" mode="out-in">
            <div v-if="isImageReady(item)" key="ready" class="image-ready" @click="openPreview(item)">
              <img :src="imageSrc(item)" :alt="imageAlt(item)" loading="lazy" />
            </div>
            <div v-else-if="isImageError(item)" key="error" class="image-error">
              {{ item.content }}
            </div>
            <div v-else key="loading" class="image-placeholder">
              <div class="image-skeleton"></div>
              <div class="image-placeholder-text">图片生成中…</div>
            </div>
          </Transition>
        </div>
      </div>

      <div v-if="showActions" class="msg-actions">
        <button class="act-btn" :class="{ on: copied }" type="button" :aria-label="copied ? '已复制' : '复制'" @click="copyContent">
          <svg v-if="!copied" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          <svg v-else viewBox="0 0 24 24" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>
        </button>
        <button class="act-btn" :class="{ on: feedback === 'like' }" type="button" aria-label="点赞" @click="toggleFeedback('like')">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H7a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/></svg>
        </button>
        <button class="act-btn" :class="{ on: feedback === 'dislike' }" type="button" aria-label="点踩" @click="toggleFeedback('dislike')">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H17a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/></svg>
        </button>
      </div>
    </div>

    <div v-if="role === 'assistant' && recaps.length" class="hil-recaps">
      <HilRecap
        v-for="recap in recaps"
        :key="recap.id"
        :intent-state="recap.intentState"
        :option-prompt="recap.optionPrompt"
      />
    </div>
  </div>

  <Teleport to="body">
    <div v-if="previewSrc" class="image-preview-mask" @click.self="closePreview">
      <img :src="previewSrc" :alt="previewAlt" class="image-preview-img" />
      <button class="image-preview-close" @click="closePreview" aria-label="关闭预览">×</button>
    </div>
  </Teleport>
</template>

<style scoped>
.bubble-row {
  position: relative;
  padding: 0;
  margin: 0 0 var(--ch-space-8);
}

.bubble-row + .bubble-row {
  margin-top: 0;
}

.bubble-row.user {
  margin-bottom: var(--ch-space-6);
}

.turn-head {
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
  margin-bottom: var(--ch-space-3);
  min-height: 32px;
}

.turn-head :deep(.agent-avatar) {
  box-shadow: var(--ch-shadow-bubble);
}

.turn-head .role {
  font: 500 16px/20px var(--ch-font-sans);
  color: var(--ch-text);
  letter-spacing: 0;
}

.bubble-row.user .bubble {
  width: fit-content;
  max-width: min(640px, 72%);
  margin-left: auto;
  padding: var(--ch-space-3) 24px;
  background: var(--ch-user-bubble);
  border-radius: var(--ch-radius-card) var(--ch-radius-card) var(--ch-space-1) var(--ch-radius-card);
  box-shadow: var(--ch-shadow-bubble);
  color: var(--ch-text);
}

.bubble {
  grid-column: 1;
  font-size: var(--ch-text-md);
  word-break: break-word;
}

.bubble.user {
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-md);
  font-weight: 400;
  line-height: 1.6;
  text-align: left;
}

.u-body {
  min-width: 0;
  padding: 0;
  text-align: left;
}

.bubble.user .text {
  margin: 0;
}

.bubble.assistant {
  width: 100%;
  max-width: 100%;
  padding: 24px;
  background: var(--ch-surface);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  box-shadow: var(--ch-shadow-soft);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-md);
  font-weight: 400;
  line-height: 1.75;
  letter-spacing: 0;
  text-align: left;
}

.bubble.assistant.bare {
  width: auto;
  max-width: 100%;
  padding: 0;
  margin: 0;
  background: transparent;
  border: none;
  box-shadow: none;
  line-height: 0;
}

.bubble.assistant .text :deep(p) {
  margin: 0 0 var(--ch-space-3);
  line-height: 1.75;
}
.bubble.assistant .text :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble.assistant .text :deep(h1),
.bubble.assistant .text :deep(h2),
.bubble.assistant .text :deep(h3),
.bubble.assistant .text :deep(h4) {
  margin: var(--ch-space-4) 0 var(--ch-space-2);
  font-family: var(--ch-font-sans);
  font-size: 16px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--ch-text);
}
.bubble.assistant .text :deep(h1:first-child),
.bubble.assistant .text :deep(h2:first-child),
.bubble.assistant .text :deep(h3:first-child),
.bubble.assistant .text :deep(h4:first-child) {
  margin-top: 0;
}
.bubble.assistant .text :deep(ul),
.bubble.assistant .text :deep(ol) {
  margin: 0 0 var(--ch-space-3);
  padding-left: var(--ch-space-4);
  line-height: 1.75;
}
.bubble.assistant .text :deep(li) {
  margin: 8px 0;
}
.bubble.assistant .text :deep(li:last-child) {
  margin-bottom: 0;
}
.bubble.assistant .text :deep(code) {
  padding: var(--ch-space-1) var(--ch-space-2);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-divider-subtle);
  font-family: var(--ch-font-mono);
  font-size: 14px;
}
.bubble.assistant .text :deep(pre) {
  padding: 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-divider-subtle);
  color: var(--ch-text);
  overflow-x: auto;
  margin: 0 0 var(--ch-space-3);
  font-size: 14px;
  line-height: 1.7;
}
.bubble.assistant .text :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: inherit;
}
.bubble.assistant .text :deep(blockquote) {
  margin: 0 0 var(--ch-space-3);
  padding: var(--ch-space-1) var(--ch-space-3);
  border-left: 2px solid var(--ch-accent);
  color: var(--ch-text-secondary);
}
.bubble.assistant .text :deep(a) {
  color: var(--ch-accent);
  text-decoration: underline;
}
.bubble.assistant .text :deep(table) {
  border-collapse: collapse;
  margin: 0 0 var(--ch-space-3);
  width: 100%;
  table-layout: auto;
}
.bubble.assistant .text :deep(th),
.bubble.assistant .text :deep(td) {
  border: 1px solid var(--ch-border);
  padding: var(--ch-space-2) var(--ch-space-3);
  line-height: 1.7;
  word-break: break-word;
}
.bubble.assistant .text :deep(th) {
  background: var(--ch-divider-subtle);
  font-weight: 600;
  text-align: left;
}
.bubble.assistant .text :deep(hr) {
  border: none;
  border-top: 1px solid var(--ch-divider-subtle);
  margin: var(--ch-space-3) 0;
}

.hil-recaps {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ch-space-2);
  margin-top: 10px;
}

.hil-recaps :deep(.hil-recap) {
  margin-top: 0;
}

.msg-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: var(--ch-space-3);
}
.act-btn {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  padding: 0;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--ch-text-faint);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease);
}
.act-btn:hover {
  background: var(--ch-accent-subtle);
  color: var(--ch-text-secondary);
}
.act-btn.on {
  color: var(--ch-accent);
}
.act-btn svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.status-card {
  width: fit-content;
  min-height: 20px;
  margin-left: -4px;
  display: flex;
  align-items: center;
  user-select: none;
  font-family: var(--ch-font-sans);
  font-size: 16px;
  line-height: 20px;
}

.status-text {
  color: transparent;
  font-weight: 500;
  background: linear-gradient(100deg, var(--ch-accent-active) 14%, var(--ch-accent) 34%, color-mix(in srgb, var(--ch-accent-2) 44%, var(--ch-surface)) 50%, var(--ch-accent) 66%, var(--ch-accent-active) 86%);
  background-size: 200% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  animation: status-shimmer 1.8s linear infinite;
}

.label-stage {
  display: inline-grid;
  grid-template-areas: "stack";
  height: 20px;
  align-items: center;
  overflow: hidden;
  vertical-align: bottom;
}
.status-text {
  grid-area: stack;
  white-space: nowrap;
  transition: transform 0.4s ease, opacity 0.4s ease;
}
.label-swap-enter-from {
  transform: translateY(8px);
  opacity: 0;
}
.label-swap-leave-to {
  transform: translateY(-8px);
  opacity: 0;
}
.label-swap-leave-active {
  transition: transform 0.2s ease, opacity 0.18s ease;
}

@keyframes status-shimmer {
  to { background-position: -200% 0; }
}

.plan-list {
  display: flex;
  flex-direction: column;
}

.plan-card {
  margin: 0 0 var(--ch-space-4);
  padding: var(--ch-space-3) 0;
  border-top: 1px solid var(--ch-divider-subtle);
  border-bottom: 1px solid var(--ch-divider-subtle);
  background: transparent;
}
.plan-card:last-child {
  margin-bottom: 0;
}

.plan-header {
  font-family: var(--ch-font-sans);
  font-weight: 600;
  font-size: var(--ch-text-sm);
  color: var(--ch-text-secondary);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  margin-bottom: var(--ch-space-3);
  line-height: 1.5;
}

.plan-steps {
  margin: 0;
  padding-left: var(--ch-space-4);
  color: var(--ch-text);
  font-size: var(--ch-text-md);
  line-height: 1.75;
}

.plan-steps li {
  margin: 8px 0;
}

.image-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: var(--ch-space-3) 0 var(--ch-space-1);
}

.image-item {
  max-width: 280px;
}

.image-reveal-enter-active,
.image-reveal-leave-active {
  transition: opacity 180ms var(--ch-ease-out), transform 180ms var(--ch-ease-out);
}

.image-reveal-enter-from {
  opacity: 0;
  transform: scale(.985);
}

.image-reveal-leave-to {
  opacity: 0;
  transform: scale(.99);
}

.image-ready {
  cursor: zoom-in;
  display: inline-block;
  transition: transform 0.15s ease;
}

.image-ready:hover {
  transform: scale(1.01);
}

.image-ready img {
  display: block;
  width: 100%;
  height: auto;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  box-shadow: none;
}

.image-placeholder {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  overflow: hidden;
  background: var(--ch-divider-subtle);
}

.image-skeleton {
  position: absolute;
  inset: 0;
  background: var(--ch-skeleton-gradient);
  background-size: 200% 100%;
  animation: imgShimmer 1.4s ease-in-out infinite;
}

@keyframes imgShimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.image-placeholder-text {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--ch-text-xs);
  color: var(--ch-text-faint);
  letter-spacing: 0.4px;
}

.image-error {
  padding: var(--ch-space-2) var(--ch-space-3);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-danger-soft);
  color: var(--ch-danger);
  font-size: var(--ch-text-xs);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.image-preview-mask {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: var(--ch-overlay-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: zoom-out;
  animation: previewFade 0.15s ease;
}

@keyframes previewFade {
  from { opacity: 0; }
  to   { opacity: 1; }
}

.image-preview-img {
  max-width: 92vw;
  max-height: 92vh;
  width: auto;
  height: auto;
  object-fit: contain;
  border-radius: var(--ch-radius-btn);
  box-shadow: var(--ch-shadow-preview);
  cursor: default;
}

.image-preview-close {
  position: fixed;
  top: 24px;
  right: 24px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: var(--ch-surface-glass-strong);
  color: var(--ch-text);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--ch-shadow-md);
  transition: background 0.15s;
}

.image-preview-close:hover {
  background: var(--ch-surface);
}

@media (prefers-reduced-motion: reduce) {
  .status-text { animation: none; }
}
</style>
