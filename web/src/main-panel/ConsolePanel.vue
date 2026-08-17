<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import { PanelLeft } from '@lucide/vue'
import { ROLE_FULL } from '../team-panel/roleMeta.js'

const props = defineProps({
  activeId: { type: String, default: null },
  traceStore: { type: Object, required: true },
  taskGraph: { type: Object, default: null },
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['close'])

const traces = computed(() => props.traceStore.getTraces(props.activeId))

const taskById = computed(() => new Map(
  (props.taskGraph?.tasks || []).map((task) => [task.id, task]),
))

function roleFor(source, taskId) {
  if (source === 'supervisor' || !source) return { key: 'supervisor', label: '主编' }
  if (source === 'scheduler') return { key: 'scheduler', label: '调度器' }
  const task = taskById.value.get(taskId)
  return {
    key: `task:${taskId || '?'}`,
    label: ROLE_FULL[task?.agent_type] || '子 Agent',
  }
}

const modelCalls = computed(() => {
  const byMessage = new Map()
  const ordered = [...traces.value].sort((a, b) => (a.created_at || 0) - (b.created_at || 0))

  for (const trace of ordered) {
    const key = trace.message_id || `${trace.source || 'supervisor'}:${trace.task_id || ''}:${trace.created_at}`
    if (trace.phase === 'model_request') {
      byMessage.set(key, {
        key,
        created_at: trace.created_at,
        source: trace.source || 'supervisor',
        task_id: trace.task_id || null,
        request: trace,
        response: null,
        toolCalls: [],
        toolResults: new Map(),
      })
      continue
    }

    const call = byMessage.get(key)
    if (!call) continue
    if (trace.phase === 'model_response') call.response = trace
    if (trace.phase === 'tool_call') call.toolCalls.push(trace)
    if (trace.phase === 'tool_result') call.toolResults.set(trace.payload?.tool_call_id, trace)
  }
  return [...byMessage.values()].sort((a, b) => a.created_at - b.created_at)
})

const timeline = computed(() => {
  const result = []
  let previousUserKey = null

  for (const call of modelCalls.value) {
    const user = userInputFor(call)
    if (user && user.key !== previousUserKey) {
      result.push({ kind: 'user', created_at: call.created_at, message: user })
      previousUserKey = user.key
    }

    const role = roleFor(call.source, call.task_id)
    const previous = result.at(-1)
    if (previous?.kind === 'role' && previous.role.key === role.key) {
      previous.calls.push(call)
    } else {
      result.push({ kind: 'role', created_at: call.created_at, role, calls: [call] })
    }
  }
  return result
})

function userInputFor(call) {
  const messages = call.request?.payload?.messages || []
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role !== 'user') continue
    const content = typeof message.content === 'string' ? message.content : shortJson(message.content)
    if (!content) return null
    return { key: `${index}:${content}`, content }
  }
  return null
}

function toolsFor(call) {
  const rows = new Map()
  for (const tool of call.response?.payload?.tool_calls || []) {
    rows.set(tool.tool_call_id, {
      id: tool.tool_call_id,
      name: tool.name,
      arguments: tool.arguments,
      display: tool.name,
      runningLabel: '',
    })
  }
  for (const trace of call.toolCalls) {
    const payload = trace.payload || {}
    rows.set(payload.tool_call_id, {
      id: payload.tool_call_id,
      name: payload.name,
      arguments: payload.arguments,
      display: payload.display || payload.name,
      runningLabel: payload.running_label || '',
    })
  }
  return [...rows.values()].map((tool) => ({
    ...tool,
    result: call.toolResults.get(tool.id),
  }))
}

function fmtTs(value) {
  if (!value) return ''
  const date = new Date(value * 1000)
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  const ss = String(date.getSeconds()).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

function previewText(value, max = 96) {
  if (typeof value !== 'string') return ''
  return value.length > max ? `${value.slice(0, max)}…` : value
}

function shortJson(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value || '')
  }
}

function finishReason(call) {
  return call.response?.payload?.finish_reason || (call.response ? '—' : '请求中')
}

function callSummary(call) {
  const response = call.response?.payload
  const tools = toolsFor(call)
  if (!response) return '等待模型响应…'
  if (response.content) return previewText(response.content, 72)
  if (tools.length) return `无文本输出 · ${tools.length} 个工具调用`
  return '无文本输出'
}

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
  if (!consoleTimer) return
  clearInterval(consoleTimer)
  consoleTimer = null
}

watch(() => props.open, (isOpen) => {
  if (isOpen) startConsolePoll()
  else stopConsolePoll()
}, { immediate: true })
watch(() => props.activeId, (sessionId) => {
  if (!props.open || !sessionId) return
  props.traceStore.clearTrace(sessionId)
  props.traceStore.loadFromServer(sessionId)
})
onBeforeUnmount(stopConsolePoll)

function clearCurrentTrace() {
  if (!props.activeId || !confirm('清空当前会话的 trace？')) return
  props.traceStore.clearTrace(props.activeId)
}
</script>

<template>
  <aside v-if="open" class="console-panel" aria-label="执行轨迹">
    <header class="sidebar-header console-header">
      <h2 class="sidebar-title">执行轨迹</h2>
      <button class="sidebar-collapse" type="button" title="收起侧栏" aria-label="收起侧栏" @click="emit('close')">
        <PanelLeft aria-hidden="true" />
      </button>
    </header>

    <section class="trace-body">
      <div class="trace-toolbar">
        <span>{{ traces.length }} 条 trace</span>
        <button class="clear-btn" type="button" :disabled="!traces.length" @click="clearCurrentTrace">清空</button>
      </div>
      <div v-if="!timeline.length" class="empty-hint">暂无执行轨迹。发送一条消息后，这里会展示模型调用过程。</div>

      <template v-for="item in timeline" :key="`${item.kind}:${item.created_at}:${item.role?.key || item.message?.id}`">
        <article v-if="item.kind === 'user'" class="trace-user-card">
          <div class="trace-user-label"><span>用户输入</span><time>{{ fmtTs(item.created_at) }}</time></div>
          <p>{{ item.message.content }}</p>
        </article>

        <details v-else class="role-chapter" open>
          <summary>
            <span class="role-avatar">{{ item.role.label.slice(0, 1) }}</span>
            <span class="role-heading">
              <strong>{{ item.role.label }}</strong>
              <small>{{ item.calls.length }} 次模型调用</small>
            </span>
            <span class="chapter-caret">⌄</span>
          </summary>

          <div class="call-list">
            <details v-for="call in item.calls" :key="call.key" class="model-call">
              <summary>
                <span class="call-time">{{ fmtTs(call.created_at) }}</span>
                <span class="call-model">{{ call.request.payload?.model || '未指定模型' }}</span>
                <span class="finish-chip" :class="`finish-${finishReason(call)}`">{{ finishReason(call) }}</span>
                <span class="call-caret">⌄</span>
                <span class="call-summary">{{ callSummary(call) }}</span>
              </summary>

              <div class="call-details">
                <details class="request-block" open>
                  <summary>
                    <span>请求</span>
                    <small>{{ (call.request.payload?.messages || []).length }} 条消息 · {{ (call.request.payload?.tools || []).length }} 个工具</small>
                  </summary>
                  <div class="request-content">
                    <div v-for="(message, index) in call.request.payload?.messages || []" :key="index" class="request-message">
                      <span class="message-role">{{ message.role || 'message' }}</span>
                      <pre>{{ typeof message.content === 'string' ? message.content : shortJson(message.content) }}</pre>
                    </div>
                    <details v-if="(call.request.payload?.tools || []).length" class="tools-schema">
                      <summary>工具定义（{{ call.request.payload.tools.length }}）</summary>
                      <pre>{{ shortJson(call.request.payload.tools) }}</pre>
                    </details>
                  </div>
                </details>

                <section class="response-block" :class="{ pending: !call.response }">
                  <div class="response-head">
                    <strong>模型返回</strong>
                    <span class="finish-chip" :class="`finish-${finishReason(call)}`">{{ finishReason(call) }}</span>
                  </div>
                  <template v-if="call.response">
                    <details v-if="(call.response.payload?.thinking_segments || []).length" class="thinking-block">
                      <summary>思考片段 · {{ call.response.payload.thinking_segments.length }}</summary>
                      <pre v-for="(segment, index) in call.response.payload.thinking_segments" :key="index">{{ segment.text }}</pre>
                    </details>
                    <pre v-if="call.response.payload?.content" class="response-content">{{ call.response.payload.content }}</pre>
                    <p v-else-if="toolsFor(call).length" class="empty-response">本次未返回文本</p>
                    <p v-else class="empty-response">无文本输出</p>

                    <div v-if="toolsFor(call).length" class="tool-results">
                      <span class="tool-results-title">tool_calls · {{ toolsFor(call).length }}</span>
                      <article v-for="tool in toolsFor(call)" :key="tool.id" class="tool-row">
                        <div class="tool-row-head">
                          <strong>{{ tool.display || tool.name }}</strong>
                          <small>{{ tool.name }}</small>
                          <span v-if="tool.runningLabel && !tool.result" class="tool-running">{{ tool.runningLabel }}</span>
                        </div>
                        <details class="tool-arguments">
                          <summary>参数</summary>
                          <pre>{{ shortJson(tool.arguments) }}</pre>
                        </details>
                        <details v-if="tool.result" class="tool-result" open>
                          <summary>返回结果 <span>{{ tool.result.payload?.duration_ms }} ms</span></summary>
                          <pre>{{ tool.result.payload?.content }}</pre>
                        </details>
                      </article>
                    </div>
                    <p v-else class="no-tools">无工具调用</p>
                  </template>
                  <p v-else class="empty-response">模型请求已发出，等待响应…</p>
                </section>
              </div>
            </details>
          </div>
        </details>
      </template>
    </section>
  </aside>
</template>

<style scoped>
.console-panel { display: flex; flex-direction: column; width: 100%; height: 100%; overflow: hidden; background: #fff; color: var(--ch-text); }
.console-header { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; min-height: 28px; margin: 0; padding: 24px 16px 0; background: #fff; }
.sidebar-title { margin: 0; font-size: var(--ch-text-lg); font-weight: var(--ch-font-bold); letter-spacing: .3px; }
.sidebar-collapse { width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; padding: 0; border: 0; border-radius: var(--ch-radius-btn); background: transparent; color: var(--ch-text-faint); cursor: pointer; transition: background var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease); }
.sidebar-collapse:hover { background: var(--ch-surface-2); color: var(--ch-text); }
.sidebar-collapse :deep(svg) { width: 20px; height: 20px; transform: translateX(6px); fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.clear-btn { border: 0; background: transparent; color: var(--ch-accent); font-weight: 600; cursor: pointer; }
.clear-btn { padding: 8px; font-size: 13px; }
.clear-btn:disabled { color: var(--ch-text-faint); cursor: not-allowed; }
.trace-body { flex: 1; overflow-y: auto; padding: 16px 12px 28px; background: #fff; }
.trace-toolbar { display: flex; align-items: center; justify-content: space-between; margin: 0 4px 12px; color: var(--ch-text-muted); font-size: 12px; }
.empty-hint { padding: 56px 16px; color: var(--ch-text-muted); text-align: center; line-height: 1.7; }
.trace-user-card { margin: 0 4px 16px; padding: 14px 16px; border: 1px solid var(--ch-accent-border); border-radius: 14px; background: var(--ch-accent-soft-gradient); }
.trace-user-label { display: flex; justify-content: space-between; gap: 12px; color: var(--ch-accent-soft-text); font-size: 13px; font-weight: 700; }
.trace-user-label time { color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: 11px; font-weight: 400; }
.trace-user-card p { margin: 8px 0 0; color: var(--ch-text); font-size: 14px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
.role-chapter { margin: 0 4px 16px; border: 1px solid var(--ch-border); border-radius: 16px; background: var(--ch-surface); overflow: hidden; }
.role-chapter > summary { display: flex; align-items: center; gap: 10px; padding: 14px; cursor: pointer; list-style: none; user-select: none; }
.role-chapter > summary::-webkit-details-marker, .model-call > summary::-webkit-details-marker, .request-block > summary::-webkit-details-marker, .thinking-block > summary::-webkit-details-marker, .tools-schema > summary::-webkit-details-marker, .tool-arguments > summary::-webkit-details-marker, .tool-result > summary::-webkit-details-marker { display: none; }
.role-avatar { display: grid; width: 30px; height: 30px; place-items: center; border-radius: 10px; background: var(--ch-accent-soft); color: var(--ch-accent); font-weight: 700; }
.role-heading { display: grid; gap: 2px; min-width: 0; }
.role-heading strong { font-size: 16px; }
.role-heading small { color: var(--ch-text-muted); font-size: 12px; }
.chapter-caret { margin-left: auto; color: var(--ch-text-muted); font-size: 18px; transition: transform var(--ch-duration-fast) var(--ch-ease); }
.role-chapter:not([open]) .chapter-caret, .model-call:not([open]) .call-caret { transform: rotate(-90deg); }
.call-list { padding: 0 10px 10px; }
.model-call { margin-top: 8px; border: 1px solid var(--ch-border); border-left: 4px solid var(--ch-accent); border-radius: 12px; overflow: hidden; background: var(--ch-surface); }
.model-call > summary { display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; gap: 6px 8px; align-items: center; padding: 12px; cursor: pointer; list-style: none; }
.call-time { color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: 11px; }
.call-model { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ch-text-secondary); font-size: 13px; font-weight: 600; }
.finish-chip { display: inline-flex; align-items: center; min-height: 22px; padding: 2px 7px; border-radius: var(--ch-radius-pill); font-family: var(--ch-font-mono); font-size: 11px; line-height: 1; white-space: nowrap; background: var(--ch-surface-2); color: var(--ch-text-muted); }
.finish-stop { background: var(--ch-success-soft); color: var(--ch-success-text); }
.finish-tool_calls { background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); }
.finish-length { background: var(--ch-warning-soft); color: var(--ch-warning-text); }
.finish-请求中 { background: var(--ch-info-soft); color: var(--ch-info-text); }
.call-caret { color: var(--ch-text-muted); transition: transform var(--ch-duration-fast) var(--ch-ease); }
.call-summary { grid-column: 1 / -1; overflow: hidden; color: var(--ch-text-muted); font-size: 13px; line-height: 1.4; text-overflow: ellipsis; white-space: nowrap; }
.call-details { padding: 0 12px 12px; }
.request-block { margin-top: 4px; border: 1px solid var(--ch-border); border-radius: 10px; background: var(--ch-surface); overflow: hidden; }
.request-block > summary { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 10px 12px; cursor: pointer; list-style: none; font-size: 13px; font-weight: 700; }
.request-block > summary small { color: var(--ch-text-muted); font-size: 11px; font-weight: 400; }
.request-content { border-top: 1px solid var(--ch-border); }
.request-message { display: grid; grid-template-columns: 54px minmax(0, 1fr); gap: 8px; padding: 9px 12px; border-bottom: 1px solid var(--ch-border); }
.message-role { align-self: start; padding: 3px 5px; border-radius: 6px; background: var(--ch-surface-2); color: var(--ch-accent-soft-text); font-family: var(--ch-font-mono); font-size: 10px; text-align: center; }
pre { margin: 0; font-family: var(--ch-font-mono); white-space: pre-wrap; word-break: break-word; }
.request-message pre { max-height: 120px; overflow: auto; color: var(--ch-text-secondary); font-size: 11px; line-height: 1.55; }
.tools-schema { padding: 9px 12px; color: var(--ch-text-muted); font-size: 12px; }
.tools-schema summary, .thinking-block summary, .tool-arguments summary, .tool-result summary { cursor: pointer; list-style: none; }
.tools-schema pre { max-height: 180px; margin-top: 8px; overflow: auto; color: var(--ch-text-secondary); font-size: 11px; }
.response-block { margin-top: 10px; padding: 12px; border: 1px solid var(--ch-accent-border); border-radius: 12px; background: var(--ch-accent-soft-gradient); }
.response-block.pending { border-style: dashed; }
.response-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.response-head strong { color: var(--ch-accent-soft-text); font-size: 14px; }
.thinking-block { margin-top: 10px; border-radius: 8px; background: color-mix(in srgb, var(--ch-surface) 75%, transparent); color: var(--ch-text-secondary); font-size: 12px; }
.thinking-block summary { padding: 8px 10px; }
.thinking-block pre { max-height: 140px; overflow: auto; padding: 0 10px 10px; font-size: 11px; line-height: 1.55; }
.response-content { max-height: 240px; margin-top: 10px; overflow: auto; color: var(--ch-text); font-size: 12px; line-height: 1.65; }
.empty-response, .no-tools { margin: 10px 0 0; color: var(--ch-text-muted); font-size: 12px; }
.tool-results { margin-top: 12px; }
.tool-results-title { display: block; margin-bottom: 8px; color: var(--ch-accent-soft-text); font-family: var(--ch-font-mono); font-size: 12px; font-weight: 700; }
.tool-row { margin-top: 8px; padding: 10px; border: 1px solid var(--ch-accent-border); border-radius: 10px; background: var(--ch-surface-glass-strong); }
.tool-row-head { display: flex; align-items: baseline; gap: 7px; min-width: 0; }
.tool-row-head strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--ch-text); font-size: 13px; }
.tool-row-head small { overflow: hidden; color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
.tool-running { margin-left: auto; color: var(--ch-accent-soft-text); font-size: 11px; white-space: nowrap; }
.tool-arguments { margin-top: 7px; color: var(--ch-text-muted); font-size: 11px; }
.tool-arguments pre, .tool-result pre { max-height: 160px; margin-top: 6px; overflow: auto; padding: 8px; border-radius: 7px; background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: 11px; line-height: 1.5; }
.tool-result { margin-top: 7px; padding: 8px; border-radius: 8px; background: var(--ch-success-soft); color: var(--ch-success-text); font-size: 11px; }
.tool-result summary { display: flex; justify-content: space-between; font-weight: 700; }
.tool-result pre { background: color-mix(in srgb, var(--ch-surface) 66%, transparent); }
@media (max-width: 780px) { .console-header { padding: 16px 16px 0; } .trace-body { padding: 12px 8px 24px; } }
</style>
