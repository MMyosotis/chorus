<script setup>
import { computed } from 'vue'
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

const activityLabel = computed(() => {
  const tn = props.thinking.items.length
  const mn = props.tools.items.length
  if (activityState.value === 'thinking') {
    return tn > 1 ? `思考中 · 第 ${tn} 段` : '思考中'
  }
  if (activityState.value === 'tools') {
    return mn > 1 ? `工具调用中 · 第 ${mn} 步` : '工具调用中'
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
}

function toolDisplayName(name) {
  if (!name) return ''
  return TOOL_NAME_ZH[name] || name
}

function toggleActivity() {
  activityExpanded.value = !activityExpanded.value
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

      <!-- 正文 -->
      <div v-if="content" class="text" v-html="formattedContent"></div>
      <span v-if="showCursor && content && activityState !== 'thinking' && activityState !== 'tools'" class="cursor">|</span>
    </div>
  </div>
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
  padding: 10px 16px;
  border-radius: 16px;
  border-bottom-right-radius: 4px;
  background: #3b82f6;
  color: #fff;
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
  color: #2563eb;
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
  background: #f1f5f9;
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
  color: #7c3aed;
  animation: pulseRow 1.6s ease-in-out infinite;
}
.status-card.tools {
  color: #3b82f6;
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
</style>
