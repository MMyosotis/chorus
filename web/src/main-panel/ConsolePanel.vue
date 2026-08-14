<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  activeId: { type: String, default: null },
  traceStore: { type: Object, required: true },
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

function close() {
  emit('close')
}

const traces = computed(() => props.traceStore.getTraces(props.activeId))

const tracesBySource = computed(() => {
  const all = traces.value
  const groups = new Map()
  for (const t of all) {
    let key, label
    if (t.source === 'supervisor') {
      key = 'supervisor'
      label = 'supervisor'
    } else if (t.source === 'scheduler') {
      key = 'scheduler'
      label = 'scheduler'
    } else {
      key = 'task:' + (t.task_id || '?')
      label = (t.source || 'subagent') + ' · ' + (t.task_id || '?')
    }
    if (!groups.has(key)) groups.set(key, { key, label, items: [] })
    groups.get(key).items.push(t)
  }
  return [...groups.values()]
})

const CONSOLE_POLL = 1500
let consoleTimer = null

function startConsolePoll() {
  if (consoleTimer || !props.activeId) return
  props.traceStore.pollFromServer(props.activeId)
  consoleTimer = setInterval(() => {
    if (props.activeId) props.traceStore.pollFromServer(props.activeId)
  }, CONSOLE_POLL)
}

function stopConsolePoll() {
  if (consoleTimer) {
    clearInterval(consoleTimer)
    consoleTimer = null
  }
}

watch(() => props.open, (o) => {
  if (o) {
    startConsolePoll()
  } else {
    stopConsolePoll()
  }
})
watch(() => props.activeId, (sid) => {
  if (!props.open || !sid) return
  props.traceStore.clearTrace(sid)
  props.traceStore.loadFromServer(sid)
})
onBeforeUnmount(stopConsolePoll)

function clearCurrentTrace() {
  if (!props.activeId) return
  if (!confirm('清空当前会话的 trace？')) return
  props.traceStore.clearTrace(props.activeId)
}

function fmtTs(created_at) {
  if (!created_at) return ''
  const d = new Date(created_at * 1000)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  const ms = String(d.getMilliseconds()).padStart(3, '0')
  return `${hh}:${mm}:${ss}.${ms}`
}

function shortJson(v) {
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

function previewText(s, max = 200) {
  if (typeof s !== 'string') return s
  if (s.length <= max) return s
  return s.slice(0, max) + '…'
}

const ROLE_COLOR = {
  system: 'var(--ch-text-muted)',
  user: 'var(--ch-info-text)',
  assistant: 'var(--ch-success-text)',
  tool: 'var(--ch-accent-soft-text)',
}

function roleColor(role) {
  return ROLE_COLOR[role] || 'var(--ch-text-muted)'
}

function renderMessageContent(m) {
  if (typeof m.content === 'string') return [{ kind: 'text', text: m.content }]
  if (Array.isArray(m.content)) {
    return m.content.map((part) => {
      if (typeof part === 'string') return { kind: 'text', text: part }
      if (part && part.type === 'text') return { kind: 'text', text: part.text || '' }
      if (part && part.type === 'image_url') {
        const url = part.image_url?.url || part.image_url || ''
        return { kind: 'image', url }
      }
      return { kind: 'text', text: shortJson(part) }
    })
  }
  if (m.content && typeof m.content === 'object' && m.content.__truncated) {
    return [{ kind: 'truncated', size: m.content.size, head: m.content.head }]
  }
  if (m.content == null) return []
  return [{ kind: 'text', text: shortJson(m.content) }]
}
</script>

<template>
  <aside v-if="open" class="console-panel" role="dialog" aria-label="控制台">
      <header class="console-header">
        <div class="title">
          Trace <span v-if="traces.length" class="count">{{ traces.length }}</span>
        </div>
        <button class="close-btn" @click="close" title="关闭">×</button>
      </header>

      <section class="console-body trace-body">
        <div class="trace-toolbar">
          <span class="hint">当前会话的 LLM 请求/响应、工具调用 trace</span>
          <button class="text-btn" @click="clearCurrentTrace" :disabled="!traces.length">清空</button>
        </div>
        <div v-if="!traces.length" class="empty-hint">暂无 trace。发条消息试试。</div>

        <details v-for="g in tracesBySource" :key="g.key" class="iter-group src-group" open>
          <summary>
            <span class="iter-title">{{ g.label }}</span>
            <span class="iter-meta"><span class="iter-count">{{ g.items.length }} 事件</span></span>
          </summary>
          <div v-for="(it, idx) in g.items" :key="idx" class="trace-item" :class="`phase-${it.phase}`">
            <div class="trace-head">
              <span class="phase-tag">{{ it.phase }}</span>
              <span class="ts">{{ fmtTs(it.created_at) }}</span>
            </div>

            <template v-if="it.phase === 'model_request'">
              <div class="kv">
                <span class="k">model</span>
                <span class="v">{{ it.payload?.model }}</span>
              </div>
              <details class="sub">
                <summary>messages ({{ (it.payload?.messages || []).length }})</summary>
                <div v-for="(m, mi) in it.payload?.messages || []" :key="mi" class="msg-row"
                  :style="{ borderLeftColor: roleColor(m.role) }">
                  <div class="msg-role" :style="{ color: roleColor(m.role) }">{{ m.role }}</div>
                  <div v-for="(p, pi) in renderMessageContent(m)" :key="pi" class="msg-part">
                    <pre v-if="p.kind === 'text'" class="text-block">{{ p.text }}</pre>
                    <img v-else-if="p.kind === 'image'" :src="p.url" class="thumb" alt="" />
                    <div v-else-if="p.kind === 'truncated'" class="truncated">
                      [已截断，{{ p.size }} 字节] {{ p.head }}…
                    </div>
                  </div>
                  <div v-if="m.tool_calls" class="tool-calls">
                    <div v-for="(tc, ti) in m.tool_calls" :key="ti" class="tool-call-line">
                      <span class="mono">{{ tc.function?.name || tc.name }}</span>
                      <span class="mono dim">({{ previewText(tc.function?.arguments || '', 120) }})</span>
                    </div>
                  </div>
                  <div v-if="m.tool_call_id" class="kv">
                    <span class="k">tool_call_id</span>
                    <span class="v mono dim">{{ m.tool_call_id }}</span>
                  </div>
                </div>
              </details>
              <details class="sub">
                <summary>tools ({{ (it.payload?.tools || []).length }})</summary>
                <pre class="text-block">{{ shortJson(it.payload?.tools) }}</pre>
              </details>
            </template>

            <template v-else-if="it.phase === 'model_response'">
              <div class="kv">
                <span class="k">finish_reason</span>
                <span class="v badge" :class="`badge-${it.payload?.finish_reason}`">
                  {{ it.payload?.finish_reason || '—' }}
                </span>
              </div>
              <pre v-if="it.payload?.content" class="text-block">{{ it.payload.content }}</pre>
              <div v-if="(it.payload?.tool_calls || []).length" class="sub-block">
                <div class="sub-title">tool_calls</div>
                <div v-for="(tc, ti) in it.payload.tool_calls" :key="ti" class="tool-call-line">
                  <span class="mono">{{ tc.name }}</span>
                  <span class="mono dim">({{ previewText(tc.arguments, 200) }})</span>
                </div>
              </div>
              <details v-if="(it.payload?.thinking_segments || []).length" class="sub">
                <summary>thinking_segments ({{ it.payload.thinking_segments.length }})</summary>
                <pre class="text-block">{{ shortJson(it.payload.thinking_segments) }}</pre>
              </details>
            </template>

            <template v-else-if="it.phase === 'tool_call'">
              <div class="kv">
                <span class="k">tool</span>
                <span class="v mono">{{ it.payload?.name }}</span>
              </div>
              <div class="kv">
                <span class="k">id</span>
                <span class="v mono dim">{{ it.payload?.tool_call_id }}</span>
              </div>
              <pre class="text-block">{{ shortJson(it.payload?.arguments) }}</pre>
            </template>

            <template v-else-if="it.phase === 'tool_result'">
              <div class="kv">
                <span class="k">tool</span>
                <span class="v mono">{{ it.payload?.name }}</span>
                <span v-if="it.payload?.duration_ms != null" class="dur">{{ it.payload.duration_ms }}ms</span>
              </div>
              <pre class="text-block">{{ previewText(it.payload?.content || '', 4000) }}</pre>
            </template>

            <template v-else>
              <pre v-if="it.payload" class="text-block">{{ shortJson(it.payload) }}</pre>
            </template>
          </div>
        </details>
      </section>
    </aside>
</template>

<style scoped>
.console-panel {
  width: 100%;
  height: 100%;
  background: var(--ch-surface-glass-strong);
  border-right: 1px solid var(--ch-border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-size: 14px;
  color: var(--ch-text);
}


.console-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ch-space-2) var(--ch-space-3);
  border-bottom: 1px solid var(--ch-border);
  background: var(--ch-canvas);
  flex-shrink: 0;
}

.title {
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
  font-size: 14px;
  font-weight: 600;
  color: var(--ch-text);
}

.count {
  display: inline-block;
  margin-left: 4px;
  padding: 0 var(--ch-space-2);
  background: var(--ch-accent);
  color: var(--ch-on-accent);
  border-radius: var(--ch-radius-pill);
  font-size: 12px;
  line-height: 16px;
  vertical-align: 1px;
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 24px;
  line-height: 1;
  color: var(--ch-text-muted);
  cursor: pointer;
  padding: 0 var(--ch-space-2);
}

.close-btn:hover {
  color: var(--ch-text);
}

.console-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--ch-space-3);
}

.text-btn {
  background: transparent;
  border: none;
  color: var(--ch-accent);
  cursor: pointer;
  font-size: 12px;
  padding: var(--ch-space-1);
}

.text-btn:disabled {
  color: var(--ch-border-strong);
  cursor: not-allowed;
}

.text-btn:hover:not(:disabled) {
  text-decoration: underline;
}

.trace-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.hint {
  color: var(--ch-text-faint);
  font-size: 12px;
}

.src-group > .trace-item .text-block {
  max-height: 200px;
  overflow-y: auto;
}

.empty-hint {
  text-align: center;
  color: var(--ch-text-faint);
  padding: 40px 0;
  font-size: 14px;
}

.iter-group {
  margin-bottom: var(--ch-space-3);
  background: var(--ch-surface);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  overflow: hidden;
}

.iter-group > summary {
  cursor: pointer;
  padding: var(--ch-space-2) var(--ch-space-3);
  background: var(--ch-canvas);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
  list-style: none;
}

.iter-group > summary::-webkit-details-marker,
.iter-group > summary::marker {
  display: none;
  content: '';
}

.iter-title {
  font-weight: 500;
  color: var(--ch-text);
}

.iter-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.iter-count {
  color: var(--ch-text-muted);
}

.trace-item {
  padding: var(--ch-space-2) var(--ch-space-3);
  border-top: 1px solid var(--ch-border);
  border-left: 2px solid transparent;
}

.trace-item.phase-model_request {
  border-left-color: var(--ch-accent);
}

.trace-item.phase-model_response {
  border-left-color: var(--ch-success);
}

.trace-item.phase-tool_call,
.trace-item.phase-tool_result {
  border-left-color: var(--ch-accent-active);
}

.trace-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.phase-tag {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--ch-text-secondary);
}

.phase-model_request .phase-tag { color: var(--ch-accent); }
.phase-model_response .phase-tag { color: var(--ch-success); }
.phase-tool_call .phase-tag,
.phase-tool_result .phase-tag { color: var(--ch-accent-active); }

.ts {
  font-size: 12px;
  color: var(--ch-text-faint);
  font-family: ui-monospace, monospace;
}

.kv {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: var(--ch-space-1) 0;
  font-size: 12px;
}

.kv .k {
  color: var(--ch-text-faint);
  min-width: 80px;
  flex-shrink: 0;
}

.kv .v {
  color: var(--ch-text);
  word-break: break-all;
}

.dim {
  color: var(--ch-text-faint);
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}

.dur {
  font-size: 12px;
  color: var(--ch-text-muted);
  margin-left: auto;
}

.badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 12px;
  background: var(--ch-canvas);
  color: var(--ch-text-secondary);
}

.badge-tool_calls { background: var(--ch-accent-soft); color: var(--ch-accent); }
.badge-stop { background: var(--ch-success-soft); color: var(--ch-success); }
.badge-error { background: var(--ch-danger-soft); color: var(--ch-danger); }

.text-block {
  margin: 4px 0;
  padding: 6px 8px;
  background: var(--ch-canvas);
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  line-height: 1.5;
  color: var(--ch-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow: auto;
}

.sub {
  margin: 4px 0;
}

.sub > summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--ch-text-muted);
  user-select: none;
  padding: 2px 0;
  list-style: none;
}

.sub > summary::-webkit-details-marker,
.sub > summary::marker {
  display: none;
  content: '';
}

.sub > summary::before {
  content: '▸ ';
  display: inline-block;
  transition: transform 0.15s;
}

.sub[open] > summary::before {
  content: '▾ ';
}

.sub-block {
  margin: var(--ch-space-2) 0;
}

.sub-title {
  font-size: 12px;
  color: var(--ch-text-faint);
  margin-bottom: 4px;
}

.msg-row {
  margin: 4px 0;
  padding: 4px 8px;
  border-left: 2px solid var(--ch-border-strong);
  background: var(--ch-canvas);
  border-radius: 0 4px 4px 0;
}

.msg-role {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}

.msg-part {
  margin: var(--ch-space-1) 0;
}

.thumb {
  max-width: 120px;
  max-height: 120px;
  border-radius: 4px;
  display: block;
}

.truncated {
  font-size: 12px;
  color: var(--ch-text-faint);
  font-style: italic;
  padding: 4px 6px;
  background: var(--ch-canvas);
  border-radius: 3px;
}

.tool-calls {
  margin-top: 4px;
}

.tool-call-line {
  font-size: 12px;
  padding: 2px 0;
  word-break: break-all;
}
</style>
