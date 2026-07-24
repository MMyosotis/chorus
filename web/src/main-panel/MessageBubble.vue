<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import IntentConfirmCard from './IntentConfirmCard.vue'
import AgentAvatar from '../team-panel/AgentAvatar.vue'

const props = defineProps({
  role: { type: String, required: true },
  content: { type: String, required: true },
  active: { type: Boolean, default: false },
  createdAt: { type: Number, default: null },
  thinking: {
    type: Object,
    default: () => ({ state: 'idle' }),
  },
  tools: {
    type: Object,
    default: () => ({ state: 'idle', items: [] }),
  },
  intentState: { type: Object, default: null },
  suspended: { type: Boolean, default: false },
})

const emit = defineEmits(['intent-confirm', 'intent-revise'])

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

const hasRunningTool = computed(() =>
  (props.tools.items || []).some((it) => it.duration_ms == null)
)

const bareMode = computed(() => props.role === 'assistant' && props.active && !props.content)

const timeLabel = computed(() => {
  if (!props.createdAt) return ''
  const d = new Date(props.createdAt * 1000)
  const h = String(d.getHours()).padStart(2, '0')
  const m = String(d.getMinutes()).padStart(2, '0')
  return `${h}:${m}`
})

const activityState = computed(() => {
  if (props.tools.state === 'running' && hasRunningTool.value) return 'tools'
  // 正文一出状态条即消失，让位正文；正文未出期间，思考过则持续酝酿中
  if (props.active && !props.content) {
    return props.thinking.state === 'running' ? 'thinking' : 'preparing'
  }
  return 'idle'
})

const runningTool = computed(() => {
  const items = props.tools.items || []
  for (let i = items.length - 1; i >= 0; i--) {
    if (items[i].duration_ms == null) return items[i]
  }
  return null
})

const activityLabel = computed(() => {
  if (activityState.value === 'thinking') return '酝酿中'
  if (activityState.value === 'tools') {
    return runningTool.value?.running_label || '落笔中'
  }
  if (activityState.value === 'preparing') return '铺纸中'
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

// 挂起态且无正文无计划：只留确认卡，不渲染空正文外壳
const hideBody = computed(() =>
  props.suspended && !props.content && !planItems.value.length
)

function extractImageUrl(content) {
  if (typeof content !== 'string') return ''
  const s = content.trim()
  if (!s) return ''
  // 纯 URL
  const m1 = s.match(/^(https?:\/\/\S+)$/i)
  if (m1) return m1[1]
  // 兼容旧数据：Markdown ![alt](url)
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
      <AgentAvatar agent-type="chief" :status="active ? 'running' : 'finished'" :size="40" />
      <span class="role">主编辑 AI</span>
      <span v-if="timeLabel" class="time">{{ timeLabel }}</span>
    </div>
    <div :class="['bubble', role, { bare: bareMode, 'assistant-card': role === 'assistant' }]">
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
          <div v-if="isImageReady(item)" class="image-ready" @click="openPreview(item)">
            <img :src="imageSrc(item)" :alt="imageAlt(item)" loading="lazy" />
          </div>
          <div v-else-if="isImageError(item)" class="image-error">
            {{ item.content }}
          </div>
          <div v-else class="image-placeholder">
            <div class="image-skeleton"></div>
            <div class="image-placeholder-text">图片生成中…</div>
          </div>
        </div>
      </div>

    </div>

    <IntentConfirmCard
      v-if="role === 'assistant' && intentState"
      class="standalone-intent"
      :state="intentState"
      @confirm="emit('intent-confirm')"
      @revise="emit('intent-revise')"
    />

    <div v-if="content && activityState === 'tools'" class="tool-running-line" aria-hidden="true">
      <span class="dot-wrap" aria-hidden="true">
        <span class="halo"></span>
        <span class="core"></span>
      </span>
      <span class="label-stage">
        <Transition name="label-swap">
          <span class="tool-running-label" :key="runningTool?.running_label">{{ runningTool?.running_label || '落笔中' }}</span>
        </Transition>
      </span>
    </div>

    <div
      v-if="activityState !== 'idle' && !(activityState === 'tools' && content)"
      class="status-card"
      :class="activityState"
    >
      <div class="status-header">
        <span class="dot-wrap" aria-hidden="true">
          <span class="halo"></span>
          <span class="core"></span>
        </span>
        <span class="label-stage">
          <Transition name="label-swap">
            <span class="status-text" :key="activityLabel">{{ activityLabel }}</span>
          </Transition>
        </span>
      </div>
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
  margin: 0 0 32px;
}

.bubble-row + .bubble-row {
  margin-top: 0;
}

.turn-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-family: var(--ch-font-sans);
  min-height: 32px;
  font-size: var(--ch-text-xs);
  font-weight: 600;
}

.bubble-row.assistant .turn-head {
  color: var(--ch-text);
}

.turn-head .role {
  min-height: auto;
  display: inline-flex;
  align-items: center;
  padding: 0;
  background: transparent;
  color: inherit !important;
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-xs);
  font-weight: 600;
  letter-spacing: 0;
  line-height: 1;
}

.turn-head .sep {
  display: none;
}

.turn-head .time {
  margin-left: auto;
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-xs);
  font-weight: 500;
  letter-spacing: 0.06em;
  color: var(--ch-text-faint);
  text-transform: none;
  font-variant-numeric: tabular-nums;
  line-height: 24px;
}
.bubble-row.assistant .turn-head .role {
  color: var(--ch-accent);
}

.bubble-row.user .turn-head .role {
  color: var(--ch-text);
}

.bubble-row.assistant .turn-head::after,
.bubble-row.user .turn-head::before { content: none; }

.bubble-row.user .bubble {
  text-align: right;
  width: fit-content;
  max-width: min(540px, 88%);
  margin-left: auto;
  padding: 16px 24px;
  background: var(--ch-accent-gradient);
  border: 1px solid transparent;
  border-radius: 16px 16px 4px 16px;
  box-shadow: var(--ch-shadow-sm);
  color: var(--ch-on-accent);
}

.bubble {
  grid-column: 1;
  line-height: var(--ch-leading-normal);
  font-size: var(--ch-text-sm);
  word-break: break-word;
}

.bubble.user {
  max-width: min(540px, 88%);
  color: var(--ch-on-accent);
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-medium);
  line-height: var(--ch-leading-normal);
  letter-spacing: 0.01em;
}

.u-body {
  min-width: 0;
  padding: 0;
  text-align: right;
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
  border-radius: 4px 16px 16px 16px;
  box-shadow: var(--ch-shadow-sm);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-medium);
  line-height: var(--ch-leading-normal);
  letter-spacing: 0.01em;
  text-align: left;
}

.standalone-intent {
  margin-top: 16px;
}

.bubble.assistant.bare {
  width: auto;
  max-width: 100%;
  padding: 0;
  margin: 0;
  background: transparent;
  border: none;
  line-height: 0;
}

.bubble.assistant .text :deep(p) {
  margin: 0 0 16px;
  letter-spacing: 0.01em;
}
.bubble.assistant .text :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble.assistant .text :deep(h1),
.bubble.assistant .text :deep(h2),
.bubble.assistant .text :deep(h3),
.bubble.assistant .text :deep(h4) {
  margin: 24px 0 8px;
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-base);
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: 0;
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
  margin: 0 0 16px;
  padding-left: 24px;
}
.bubble.assistant .text :deep(li) {
  margin: 4px 0;
  letter-spacing: 0.2px;
}
.bubble.assistant .text :deep(code) {
  padding: 1px 4px;
  border-bottom: 1px solid var(--ch-border-strong);
  background: var(--ch-surface-3);
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: var(--ch-text-sm);
}
.bubble.assistant .text :deep(pre) {
  padding: 16px;
  border-top: 1px solid var(--ch-border-strong);
  border-bottom: 1px solid var(--ch-border-strong);
  background: var(--ch-surface-3);
  color: var(--ch-text);
  overflow-x: auto;
  margin: 16px 0;
  font-size: var(--ch-text-sm);
  line-height: 1.7;
}
.bubble.assistant .text :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: inherit;
}
.bubble.assistant .text :deep(blockquote) {
  margin: 16px 0;
  padding: 8px 16px;
  border-left: 2px solid var(--ch-accent);
  color: var(--ch-text-secondary);
}
.bubble.assistant .text :deep(a) {
  color: var(--ch-accent);
  text-decoration: underline;
}
.bubble.assistant .text :deep(table) {
  border-collapse: collapse;
  margin: 16px 0;
  width: 100%;
  table-layout: auto;
}
.bubble.assistant .text :deep(th),
.bubble.assistant .text :deep(td) {
  border: 1px solid var(--ch-border);
  padding: 8px 16px;
  line-height: 1.7;
  word-break: break-word;
}
.bubble.assistant .text :deep(th) {
  background: var(--ch-surface-3);
  font-weight: 600;
  text-align: left;
}
.bubble.assistant .text :deep(hr) {
  border: none;
  border-top: 1px dashed var(--ch-border);
  margin: 16px 0;
}

.status-card {
  margin: 8px 0 0;
  user-select: none;
  background: transparent;
  border-radius: 0;
  color: var(--ch-text-secondary);
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-sm);
  line-height: var(--ch-leading-normal);
  letter-spacing: 0.01em;
}

.bubble-row.bare .status-card {
  margin-top: 0;
}

.status-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-text {
  font-weight: 500;
}

.dot-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  margin-left: -1px;
}
.halo {
  position: absolute;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--ch-accent) 0%, rgba(99, 102, 241, 0.32) 55%, transparent 100%);
  animation: breath 1.4s ease-in-out infinite;
}
.core {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ch-accent);
  opacity: 0.9;
}
@keyframes breath {
  0%, 100% { opacity: 0.28; }
  50%      { opacity: 1; }
}

.label-stage {
  display: inline-grid;
  grid-template-areas: "stack";
  height: calc(var(--ch-leading-normal) * 1em);
  overflow: hidden;
  vertical-align: bottom;
}
.status-text,
.tool-running-label {
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

.tool-running-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin: 8px 0 0;
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-sm);
  line-height: var(--ch-leading-normal);
  color: var(--ch-text-secondary);
  letter-spacing: 0.01em;
}
.tool-running-label {
  font-weight: 500;
}

.plan-list {
  display: flex;
  flex-direction: column;
}

.plan-card {
  margin: 24px 0;
  padding: 24px 0;
  border-top: 1px solid var(--ch-border);
  border-bottom: 1px solid var(--ch-border);
  background: var(--ch-surface);
}

.plan-header {
  font-family: var(--ch-font-sans);
  font-weight: 600;
  font-size: var(--ch-text-sm);
  color: var(--ch-text);
  letter-spacing: 0;
  margin-bottom: 16px;
  line-height: 1.5;
}

.plan-steps {
  margin: 0;
  padding-left: 24px;
  color: var(--ch-text-secondary);
  font-size: var(--ch-text-sm);
  line-height: 1.6;
}

.plan-steps li {
  margin: 8px 0;
}

.image-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin: 16px 0 8px;
}

.image-item {
  max-width: 280px;
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
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-btn);
  box-shadow: none;
}

.image-placeholder {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-btn);
  overflow: hidden;
  background: var(--ch-surface-3);
}

.image-skeleton {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    rgba(0, 0, 0, 0.04) 0%,
    rgba(0, 0, 0, 0.10) 50%,
    rgba(0, 0, 0, 0.04) 100%
  );
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
  color: var(--ch-text-muted);
  letter-spacing: 0.4px;
}

.image-error {
  padding: 8px 16px;
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
  background: rgba(15, 23, 42, 0.78);
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
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
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
  background: rgba(255, 255, 255, 0.92);
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
  background: #fff;
}
</style>
