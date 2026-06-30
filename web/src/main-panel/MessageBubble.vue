<script setup>
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  role: { type: String, required: true },
  content: { type: String, required: true },
  showCursor: { type: Boolean, default: false },
  thinking: {
    type: Object,
    default: () => ({ state: 'idle', items: [], expanded: false }),
  },
  tools: {
    type: Object,
    default: () => ({ state: 'idle', items: [], expanded: false }),
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

const activityState = computed(() => {
  if (props.thinking.state === 'running') return 'thinking'
  if (props.tools.state === 'running') return 'tools'
  if (props.thinking.items.length || props.tools.items.length) return 'completed'
  return 'idle'
})

const activityExpanded = computed({
  get: () => props.thinking.expanded || props.tools.expanded,
  set: (v) => {
    props.thinking.expanded = v
    props.tools.expanded = v
  },
})

const runningTool = computed(() => {
  const items = props.tools.items || []
  for (let i = items.length - 1; i >= 0; i--) {
    if (items[i].duration_ms == null) return items[i]
  }
  return null
})

const activityLabel = computed(() => {
  const tn = props.thinking.items.length
  const mn = props.tools.items.length
  if (activityState.value === 'thinking') {
    return tn > 1 ? `思考中 · 第 ${tn} 段` : '思考中'
  }
  if (activityState.value === 'tools') {
    const verb = runningTool.value?.running_label || '工具调用中'
    return mn > 1 ? `${verb} · 第 ${mn} 步` : verb
  }
  const parts = []
  if (tn > 0) parts.push(`思考 ${tn} 段`)
  if (mn > 0) parts.push(`调用 ${mn} 次工具`)
  return parts.join(' · ')
})

const totalActivityMs = computed(() => {
  const sum =
    props.thinking.items.reduce((s, x) => s + (x.duration_ms || 0), 0) +
    props.tools.items.reduce((s, x) => s + (x.duration_ms || 0), 0)
  return sum > 0 ? sum : null
})

const mergedItems = computed(() => {
  const arr = [
    ...props.thinking.items.map((x) => ({ ...x, kind: 'thinking' })),
    ...props.tools.items.map((x) => ({ ...x, kind: 'tool' })),
  ]
  arr.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
  return arr
})

function formatDur(ms) {
  if (ms == null) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

const TOOL_NAME_ZH = {
  bash: '命令行',
  read_file: '读取文件',
  write_file: '写入文件',
  edit_file: '编辑文件',
  glob_search: '查找文件',
  load_skill: '加载技能',
  generate_image: '生成图像',
  output_plan: '制定计划',
}

function toolDisplayName(name) {
  if (!name) return ''
  return TOOL_NAME_ZH[name] || name
}

function toggleActivity() {
  activityExpanded.value = !activityExpanded.value
}

// generate_image 工具的图片占位/渲染：图片严格归属于产生它的本气泡。
const imageItems = computed(() =>
  (props.tools.items || []).filter((it) => it.name === 'generate_image')
)

// output_plan 工具的计划卡片：tool_result 回来（duration_ms 有值）后才渲染，避免流式空态。
const planItems = computed(() =>
  (props.tools.items || []).filter(
    (it) => it.name === 'output_plan' && it.duration_ms != null
  )
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

// 图片预览（点击放大）
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
  <div :class="['bubble-row', role]">
    <div :class="['bubble', role]">
      <!-- 合并状态条：思考 / 工具调用 -->
      <div
        v-if="activityState !== 'idle'"
        class="status-card"
        :class="activityState"
        @click="toggleActivity"
      >
        <div class="status-header">
          <span class="status-text">{{ activityLabel }}</span>
          <span
            v-if="activityState === 'thinking' || activityState === 'tools'"
            class="dots"
            aria-hidden="true"
          >
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </span>
          <span v-if="activityState === 'completed' && totalActivityMs != null" class="dur header-dur">{{ formatDur(totalActivityMs) }}</span>
          <span
            v-if="activityState !== 'thinking' && activityState !== 'tools'"
            class="caret"
            :class="{ open: activityExpanded }"
            aria-hidden="true"
          >
            <svg viewBox="0 0 12 12" width="10" height="10">
              <path d="M3 4.5 L6 7.5 L9 4.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </span>
        </div>
        <div class="status-body-wrap" :class="{ open: activityExpanded }">
          <div class="status-body-inner">
            <div class="status-body" @click.stop>
              <div v-for="item in mergedItems" :key="`${item.kind}-${item.seq}`" class="step">
                <template v-if="item.kind === 'thinking'">
                  <div class="step-meta">
                    <span class="step-num">思考</span>
                    <span v-if="item.duration_ms != null" class="dur">{{ formatDur(item.duration_ms) }}</span>
                  </div>
                  <pre class="step-text">{{ item.text }}</pre>
                </template>
                <template v-else>
                  <div class="step-meta">
                    <span class="step-num">工具</span>
                    <span v-if="item.duration_ms != null" class="dur">{{ formatDur(item.duration_ms) }}</span>
                  </div>
                  <div class="step-display">{{ item.display || toolDisplayName(item.name) }}</div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 执行计划卡片：output_plan 工具产出，置于正文之前 -->
      <div v-if="planItems.length" class="plan-list">
        <div v-for="(item, idx) in planItems" :key="`plan-${idx}`" class="plan-card">
          <div class="plan-header">执行计划</div>
          <ol class="plan-steps">
            <li v-for="(step, i) in (item.arguments?.steps || [])" :key="i">{{ step }}</li>
          </ol>
        </div>
      </div>

      <!-- 正文 -->
      <div v-if="content" class="text" v-html="formattedContent"></div>

      <!-- 生成图像：占位骨架 → 拿到 URL 后替换为图片（放在正文下方）-->
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
      <span v-if="showCursor && content && activityState !== 'thinking' && activityState !== 'tools'" class="cursor">|</span>
    </div>
  </div>

  <!-- 图片放大预览 -->
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
}

.bubble-row.user {
  justify-content: flex-end;
}

.bubble-row.assistant {
  justify-content: flex-start;
}

.bubble {
  line-height: 1.7;
  font-size: 15px;
  word-break: break-word;
}

.bubble.user {
  max-width: 75%;
  padding: 16px 26px;
  border-radius: 22px;
  background: #f1f5f9;
  color: var(--ch-body);
  box-shadow: none;
}

.bubble.assistant {
  width: 100%;
  max-width: 100%;
  padding: 0;
  background: transparent;
  color: #1e293b;
  border-radius: 0;
}

.bubble.assistant .text :deep(p) {
  margin: 0 0 10px;
  letter-spacing: 0.2px;
}
.bubble.assistant .text :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble.assistant .text :deep(h1),
.bubble.assistant .text :deep(h2),
.bubble.assistant .text :deep(h3),
.bubble.assistant .text :deep(h4) {
  margin: 14px 0 8px;
  font-weight: 600;
  line-height: 1.35;
  letter-spacing: 0.2px;
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
  background: rgba(15, 23, 42, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 13px;
}
.bubble.assistant .text :deep(pre) {
  background: #0f172a;
  color: #e2e8f0;
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
  border-left: 3px solid #cbd5e1;
  color: #475569;
}
.bubble.assistant .text :deep(a) {
  color: #6366f1;
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
  border: 1px solid #cbd5e1;
  padding: 8px 12px;
  line-height: 1.7;
  word-break: break-word;
}
.bubble.assistant .text :deep(th) {
  background: rgba(99, 102, 241, 0.06);
  font-weight: 600;
  text-align: left;
}
.bubble.assistant .text :deep(hr) {
  border: none;
  border-top: 1px solid #cbd5e1;
  margin: 12px 0;
}

.cursor {
  display: inline-block;
  margin-left: 1px;
  animation: blink 0.8s step-end infinite;
  color: #64748b;
  font-weight: 200;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

/* ===== 极简内联状态条（思考 / 工具调用）===== */
.status-card {
  margin: 0 0 14px;
  font-size: 13px;
  cursor: pointer;
  user-select: none;
  background: transparent;
  border-radius: 0;
  transition: opacity 0.15s;
}

.status-card:last-child {
  margin-bottom: 8px;
}

.status-card + .text,
.status-card + .cursor {
  margin-top: 6px;
}

.status-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 2px 0;
  line-height: 1;
}

.status-text {
  font-weight: 500;
  letter-spacing: 0.1px;
  line-height: 1;
}

.caret {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  line-height: 0;
  opacity: 0.7;
  flex-shrink: 0;
  transform: rotate(-90deg);
  transition: transform 0.25s ease, opacity 0.15s;
}
.caret.open {
  transform: rotate(0deg);
}
.caret svg {
  display: block;
}
.status-card:hover .caret {
  opacity: 1;
}

.status-body-wrap {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.25s ease;
}
.status-body-wrap.open {
  grid-template-rows: 1fr;
}
.status-body-inner {
  overflow: hidden;
  min-height: 0;
}

.header-dur {
  font-size: 11px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
  display: inline-flex;
  align-items: center;
  line-height: 1;
}

.status-body {
  margin: 10px 0 2px;
  padding: 4px 0 2px 10px;
  border-left: 2px solid rgba(15, 23, 42, 0.08);
  cursor: default;
  color: #1e293b;
}

.step {
  margin-top: 8px;
}

.step:first-child {
  margin-top: 0;
}

.step-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 4px;
  color: #475569;
  line-height: 1;
}

.step-num {
  font-weight: 600;
  line-height: 1;
}

.tool-name {
  background: transparent;
  padding: 0;
  border-radius: 0;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  color: #1e293b;
}

.dur {
  font-size: 11px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
  display: inline-flex;
  align-items: center;
  line-height: 1;
}

.step-text {
  margin: 0;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow: auto;
}

.step-display {
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #475569;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 配色：运行中保留主题色 + 完成态统一灰化 */
.status-card.thinking {
  color: #6366f1;
  animation: pulseRow 1.6s ease-in-out infinite;
}
.status-card.tools {
  color: #6366f1;
  animation: pulseRow 1.6s ease-in-out infinite;
}
.status-card.completed {
  color: #64748b;
}

@keyframes pulseRow {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.65; }
}

.dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 4px;
  flex-shrink: 0;
}
.dots .dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.25;
  animation: dotWave 1.2s ease-in-out infinite;
}
.dots .dot:nth-child(2) {
  animation-delay: 0.2s;
}
.dots .dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes dotWave {
  0%, 60%, 100% { opacity: 0.25; }
  30%           { opacity: 1; }
}

/* ===== 执行计划卡片 ===== */
.plan-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 4px 0 14px;
}

.plan-card {
  border: 1px solid var(--ch-orange-border);
  background: var(--ch-orange-soft);
  border-radius: 22px;
  padding: 12px 16px;
}

.plan-header {
  font-size: 13px;
  font-weight: 600;
  color: #c2410c;
  letter-spacing: 0.3px;
  margin-bottom: 8px;
  line-height: 1;
}

.plan-steps {
  margin: 0;
  padding-left: 22px;
  color: #1e293b;
  font-size: 14px;
  line-height: 1.7;
}

.plan-steps li {
  margin: 4px 0;
  letter-spacing: 0.2px;
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
  border-radius: 18px;
  box-shadow: 0 14px 32px rgba(30, 41, 59, 0.14), 0 2px 6px rgba(30, 41, 59, 0.06);
}

.image-placeholder {
  position: relative;
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 18px;
  overflow: hidden;
  background: #eef2f7;
}

.image-skeleton {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    rgba(15, 23, 42, 0.04) 0%,
    rgba(15, 23, 42, 0.10) 50%,
    rgba(15, 23, 42, 0.04) 100%
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
  color: #64748b;
  letter-spacing: 0.4px;
}

.image-error {
  padding: 10px 14px;
  border-radius: 8px;
  background: #fef2f2;
  color: #b91c1c;
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
  color: #1e293b;
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
