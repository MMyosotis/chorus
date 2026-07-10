<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

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

const hasRunningTool = computed(() =>
  (props.tools.items || []).some((it) => it.duration_ms == null)
)

const bareMode = computed(() => props.role === 'assistant' && props.active && !props.content)

const activityState = computed(() => {
  if (props.thinking.state === 'running') return 'thinking'
  if (props.tools.state === 'running' && hasRunningTool.value) return 'tools'
  if (props.active && !props.content && !hasRunningTool.value) return 'preparing'
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

// 流式期间不显示已完成工具 chip，等本轮结束再留痕
const doneToolChips = computed(() => {
  if (props.active) return []
  return (props.tools.items || [])
    .filter((it) =>
      it.duration_ms != null &&
      it.name !== 'generate_image' &&
      it.name !== 'output_plan' &&
      it.name !== 'update_intent_state'
    )
    .map((it) => it.display || it.name)
})

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
    <div :class="['sender', role]">{{ role === 'user' ? '我' : '助手' }}</div>
    <div :class="['bubble', role, { bare: bareMode }]">
      <div :class="role === 'user' ? 'u-body' : 'a-body'">
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

    <div v-if="!bareMode && doneToolChips.length" class="tool-chips">
      <span v-for="(label, idx) in doneToolChips" :key="`tc-${idx}`" class="tool-chip">
        <span class="tool-chip-tick" aria-hidden="true">✓</span>{{ label }}
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
  display: flex;
  flex-direction: column;
}

.bubble-row.user {
  align-items: flex-end;
}

.bubble-row.assistant {
  align-items: flex-start;
}

.sender {
  display: inline-flex;
  align-items: center;
  font-family: var(--ch-serif);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  height: 24px;
  padding: 0 8px;
  margin: 0 0 14px;
  line-height: 1;
}

.sender.assistant {
  background: var(--ch-primary-soft);
  color: var(--ch-primary-2);
}

.sender.user {
  background: #eef0f2;
  color: var(--ch-muted);
}

.bubble {
  line-height: 1.7;
  font-size: 14px;
  word-break: break-word;
}

.bubble.user {
  max-width: 82%;
  color: var(--ch-text);
  font-family: var(--ch-serif);
  font-size: 15px;
  line-height: 1.82;
  letter-spacing: 0.2px;
}

.u-body {
  min-width: 0;
  padding: 1px 0;
  text-align: left;
}

.bubble.user .text {
  margin: 0;
}

.bubble.assistant {
  width: 100%;
  max-width: 100%;
  padding: 0;
  background: transparent;
  border: none;
  color: var(--ch-text);
  font-family: var(--ch-serif);
  font-size: 15px;
  line-height: 1.95;
  letter-spacing: 0.25px;
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
  margin: 0 0 14px;
  letter-spacing: 0.2px;
}
.bubble.assistant .text :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble.assistant .text :deep(h1),
.bubble.assistant .text :deep(h2),
.bubble.assistant .text :deep(h3),
.bubble.assistant .text :deep(h4) {
  margin: 28px 0 14px;
  font-family: var(--ch-serif);
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: 0.4px;
}
.bubble.assistant .text :deep(h1) { font-size: 20px; }
.bubble.assistant .text :deep(h2) { font-size: 18px; }
.bubble.assistant .text :deep(h3) { font-size: 16px; }
.bubble.assistant .text :deep(ul),
.bubble.assistant .text :deep(ol) {
  margin: 0 0 10px;
  padding-left: 24px;
}
.bubble.assistant .text :deep(li) {
  margin: 4px 0;
  letter-spacing: 0.2px;
}
.bubble.assistant .text :deep(code) {
  background: var(--ch-bg-cool);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 13px;
}
.bubble.assistant .text :deep(pre) {
  background: #1a1a1f;
  color: #e4e4e7;
  padding: 12px 14px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
  font-size: 13px;
  line-height: 1.5;
}
.bubble.assistant .text :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
  font-size: inherit;
}
.bubble.assistant .text :deep(blockquote) {
  margin: 8px 0;
  padding: 4px 12px;
  border-left: 3px solid var(--ch-border-2);
  color: var(--ch-body);
}
.bubble.assistant .text :deep(a) {
  color: var(--ch-primary);
  text-decoration: underline;
}
.bubble.assistant .text :deep(table) {
  border-collapse: collapse;
  margin: 12px 0;
  width: 100%;
  table-layout: auto;
}
.bubble.assistant .text :deep(th),
.bubble.assistant .text :deep(td) {
  border: 1px solid var(--ch-border);
  padding: 8px 12px;
  line-height: 1.7;
  word-break: break-word;
}
.bubble.assistant .text :deep(th) {
  background: var(--ch-bg-cool);
  font-weight: 600;
  text-align: left;
}
.bubble.assistant .text :deep(hr) {
  border: none;
  border-top: 1px dashed var(--ch-border);
  margin: 18px 0;
}

/* ===== 过程态:墨色呼吸点 + 文案自下而上切换 ===== */
.status-card {
  margin: 8px 0 0;
  user-select: none;
  background: transparent;
  border-radius: 0;
  color: var(--ch-body);
  font-family: var(--ch-serif);
  font-size: 14px;
  line-height: 1.95;
  letter-spacing: 0.3px;
}

.bubble-row.bare .status-card {
  margin-top: 0;
}

.status-header {
  display: flex;
  align-items: center;
  gap: 9px;
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
  background: radial-gradient(circle, var(--ch-primary) 0%, rgba(59, 90, 114, 0.32) 55%, transparent 100%);
  animation: breath 1.4s ease-in-out infinite;
}
.core {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--ch-primary-2);
  opacity: 0.9;
}
@keyframes breath {
  0%, 100% { transform: scale(0.7); opacity: 0.55; }
  50%      { transform: scale(1.9); opacity: 0.18; }
}

.label-stage {
  display: inline-grid;
  grid-template-areas: "stack";
  height: 1.95em;
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

/* 已完成工具的紧凑留痕 */
.tool-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0 0;
}

.tool-running-line {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  margin: 10px 0 0;
  font-family: var(--ch-serif);
  font-size: 14px;
  line-height: 1.95;
  color: var(--ch-body);
  letter-spacing: 0.3px;
}
.tool-running-label {
  font-weight: 500;
}
.tool-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  max-width: 100%;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--ch-bg-warm);
  border: 1px solid var(--ch-border);
  color: var(--ch-muted);
  font-size: 12px;
  line-height: 1.4;
  letter-spacing: 0.1px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.tool-chip-tick {
  color: var(--ch-primary);
  font-weight: 600;
  flex-shrink: 0;
}

/* ===== 执行计划卡片 ===== */
.plan-list {
  display: flex;
  flex-direction: column;
}

.plan-card {
  border-left: 2px solid var(--ch-border-2);
  padding: 4px 0 4px 18px;
  margin: 18px 0 20px;
  background: transparent;
}

.plan-header {
  font-family: var(--ch-serif);
  font-weight: 600;
  font-size: 13px;
  color: var(--ch-muted);
  letter-spacing: 0.4px;
  margin-bottom: 10px;
  line-height: 1;
}

.plan-steps {
  margin: 0;
  padding-left: 20px;
  color: var(--ch-body);
  font-size: 13.5px;
  line-height: 1.9;
}

.plan-steps li {
  margin: 3px 0;
}

/* ===== 生成图像：占位 / 渲染 ===== */
.image-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 20px 0 4px;
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
  border-radius: var(--ch-radius-lg);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
}

.image-placeholder {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: var(--ch-radius-lg);
  overflow: hidden;
  background: var(--ch-bg-cool);
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
  font-size: 13px;
  color: var(--ch-muted);
  letter-spacing: 0.4px;
}

.image-error {
  padding: 10px 14px;
  border-radius: 8px;
  background: var(--ch-red-soft);
  color: var(--ch-red);
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 图片放大预览遮罩 */
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
  border-radius: 8px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45);
  cursor: default;
}

.image-preview-close {
  position: fixed;
  top: 20px;
  right: 24px;
  width: 36px;
  height: 36px;
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
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
  transition: background 0.15s;
}

.image-preview-close:hover {
  background: #fff;
}
</style>
