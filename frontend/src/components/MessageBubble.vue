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

const thinkingLabel = computed(() => {
  const n = props.thinking.items.length
  if (props.thinking.state === 'running') {
    return n > 1 ? `思考中 · 第 ${n} 段` : '思考中...'
  }
  return n > 1 ? `已完成 ${n} 段思考` : '思考完成'
})

const toolsLabel = computed(() => {
  const n = props.tools.items.length
  if (props.tools.state === 'running') {
    return n > 1 ? `工具调用中 · 第 ${n} 步` : '工具调用中...'
  }
  return n > 1 ? `已完成 ${n} 次工具调用` : '工具调用完成'
})

function formatDur(ms) {
  if (ms == null) return ''
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function toggleThinking() {
  props.thinking.expanded = !props.thinking.expanded
}

function toggleTools() {
  props.tools.expanded = !props.tools.expanded
}
</script>

<template>
  <div :class="['bubble-row', role]">
    <div :class="['bubble', role]">
      <!-- 思考状态条 -->
      <div
        v-if="thinking.state !== 'idle'"
        class="status-card thinking"
        :class="thinking.state"
        @click="toggleThinking"
      >
        <div class="status-header">
          <span v-if="thinking.state === 'running'" class="spinner thinking-spinner"></span>
          <span v-else class="check">✓</span>
          <span class="status-text">{{ thinkingLabel }}</span>
          <span class="caret">{{ thinking.expanded ? '▾' : '▸' }}</span>
        </div>
        <div v-if="thinking.expanded" class="status-body" @click.stop>
          <div v-for="(item, i) in thinking.items" :key="i" class="step">
            <div class="step-meta">
              <span class="step-num">第 {{ i + 1 }} 段</span>
              <span v-if="item.duration_ms != null" class="dur">{{ formatDur(item.duration_ms) }}</span>
            </div>
            <pre class="step-text">{{ item.text }}</pre>
          </div>
        </div>
      </div>

      <!-- 工具状态条 -->
      <div
        v-if="tools.state !== 'idle'"
        class="status-card tools"
        :class="tools.state"
        @click="toggleTools"
      >
        <div class="status-header">
          <span v-if="tools.state === 'running'" class="spinner tools-spinner"></span>
          <span v-else class="check">✓</span>
          <span class="status-text">{{ toolsLabel }}</span>
          <span class="caret">{{ tools.expanded ? '▾' : '▸' }}</span>
        </div>
        <div v-if="tools.expanded" class="status-body" @click.stop>
          <div v-for="(item, i) in tools.items" :key="i" class="step">
            <div class="step-meta">
              <span class="step-num">{{ i + 1 }}.</span>
              <code class="tool-name">{{ item.name }}</code>
              <span v-if="item.duration_ms != null" class="dur">{{ formatDur(item.duration_ms) }}</span>
            </div>
            <div class="step-display">{{ item.display || item.name }}</div>
          </div>
        </div>
      </div>

      <!-- 正文 -->
      <div v-if="content" class="text" v-html="formattedContent"></div>
      <span v-if="showCursor" class="cursor">|</span>
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
  max-width: 75%;
  padding: 10px 16px;
  border-radius: 16px;
  line-height: 1.6;
  font-size: 15px;
  word-break: break-word;
}

.bubble.user {
  background: #3b82f6;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble.assistant {
  background: #f1f5f9;
  color: #1e293b;
  border-bottom-left-radius: 4px;
}

.bubble.assistant .text :deep(p) {
  margin: 0 0 8px;
}
.bubble.assistant .text :deep(p:last-child) {
  margin-bottom: 0;
}
.bubble.assistant .text :deep(h1),
.bubble.assistant .text :deep(h2),
.bubble.assistant .text :deep(h3),
.bubble.assistant .text :deep(h4) {
  margin: 12px 0 6px;
  font-weight: 600;
  line-height: 1.3;
}
.bubble.assistant .text :deep(h1) { font-size: 20px; }
.bubble.assistant .text :deep(h2) { font-size: 18px; }
.bubble.assistant .text :deep(h3) { font-size: 16px; }
.bubble.assistant .text :deep(ul),
.bubble.assistant .text :deep(ol) {
  margin: 0 0 8px;
  padding-left: 24px;
}
.bubble.assistant .text :deep(li) {
  margin: 2px 0;
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
  margin: 8px 0;
}
.bubble.assistant .text :deep(th),
.bubble.assistant .text :deep(td) {
  border: 1px solid #cbd5e1;
  padding: 4px 8px;
}
.bubble.assistant .text :deep(hr) {
  border: none;
  border-top: 1px solid #cbd5e1;
  margin: 12px 0;
}

.cursor {
  display: inline;
  animation: blink 0.8s step-end infinite;
  color: inherit;
  font-weight: 200;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

/* ===== 状态卡片（思考 / 工具调用）===== */
.status-card {
  margin-bottom: 8px;
  border-radius: 10px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s;
  user-select: none;
}

.status-card:last-child {
  margin-bottom: 0;
}

.status-card + .text,
.status-card + .cursor {
  margin-top: 4px;
}

.status-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
}

.status-text {
  flex: 1;
}

.caret {
  font-size: 11px;
  opacity: 0.7;
}

.status-body {
  padding: 8px 12px 10px;
  border-top: 1px solid rgba(15, 23, 42, 0.08);
  cursor: default;
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
  opacity: 0.85;
}

.step-num {
  font-weight: 600;
}

.tool-name {
  background: rgba(15, 23, 42, 0.08);
  padding: 1px 6px;
  border-radius: 4px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  color: #1e293b;
}

.dur {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.06);
  color: #475569;
  font-variant-numeric: tabular-nums;
}

.step-text {
  margin: 0;
  padding: 8px 10px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 6px;
  font-family: 'SF Mono', Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.55;
  color: #1e293b;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 320px;
  overflow: auto;
}

.step-display {
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.6);
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.5;
  color: #1e293b;
  white-space: pre-wrap;
  word-break: break-all;
}

/* 思考：紫蓝色调 */
.status-card.thinking.running {
  background: rgba(139, 92, 246, 0.08);
  color: #7c3aed;
}
.status-card.thinking.running:hover {
  background: rgba(139, 92, 246, 0.14);
}
.status-card.thinking.completed {
  background: rgba(139, 92, 246, 0.06);
  color: #6d28d9;
}
.status-card.thinking.completed:hover {
  background: rgba(139, 92, 246, 0.12);
}

/* 工具：保留原蓝/绿配色 */
.status-card.tools.running {
  background: rgba(59, 130, 246, 0.08);
  color: #3b82f6;
}
.status-card.tools.running:hover {
  background: rgba(59, 130, 246, 0.14);
}
.status-card.tools.completed {
  background: rgba(34, 197, 94, 0.08);
  color: #16a34a;
}
.status-card.tools.completed:hover {
  background: rgba(34, 197, 94, 0.14);
}

.spinner {
  display: inline-block;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 2px solid;
  animation: spin 0.8s linear infinite;
}

.thinking-spinner {
  border-color: rgba(139, 92, 246, 0.25);
  border-top-color: #7c3aed;
}

.tools-spinner {
  border-color: rgba(59, 130, 246, 0.25);
  border-top-color: #3b82f6;
}

.check {
  font-weight: 700;
  font-size: 14px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
