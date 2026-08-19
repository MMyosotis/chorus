<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { PanelLeft } from '@lucide/vue'
import { ROLE_SHORT } from '../team-panel/roleMeta.js'

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
  if (source === 'scheduler') return { key: 'scheduler', label: '调度' }
  const task = taskById.value.get(taskId)
  return {
    key: `task:${taskId || '?'}`,
    label: ROLE_SHORT[task?.agent_type] || '子代理',
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

const toolMetaById = computed(() => {
  const meta = new Map()
  for (const call of modelCalls.value) {
    for (const trace of call.toolResults.values()) {
      meta.set(trace.payload?.tool_call_id, trace.payload)
    }
  }
  return meta
})

const agents = computed(() => {
  const seen = new Map()
  for (const call of modelCalls.value) {
    const role = roleFor(call.source, call.task_id)
    if (!seen.has(role.key)) seen.set(role.key, role)
  }
  return [...seen.values()]
})

const activeAgent = ref('all')
watch(() => props.activeId, () => { activeAgent.value = 'all' })

const visibleCalls = computed(() => {
  if (activeAgent.value === 'all') return modelCalls.value
  return modelCalls.value.filter((call) => roleFor(call.source, call.task_id).key === activeAgent.value)
})

const timeline = computed(() => {
  const result = []
  let previous = null

  for (const call of visibleCalls.value) {
    const messages = call.request?.payload?.messages || []
    if (messages.at(-1)?.role === 'tool' && previous) {
      const tools = resultTools(previous)
      if (tools.length) result.push({ kind: 'toolback', created_at: call.created_at, tools })
    } else {
      const user = userInputFor(call)
      if (user) result.push({ kind: 'user', created_at: call.created_at, message: user })
    }

    result.push({ kind: 'loop', created_at: call.created_at, role: roleFor(call.source, call.task_id), call })
    previous = call
  }
  return result
})

function resultTools(call) {
  return toolsFor(call)
    .filter((tool) => tool.result)
    .map((tool) => {
      const content = tool.result.payload?.content
      return {
        id: tool.id,
        name: tool.name,
        display: tool.display,
        duration_ms: tool.result.payload?.duration_ms,
        content,
        pretty: parseMaybeJson(content),
      }
    })
}

const INJECTION_LABELS = { recalled_memories: '记忆召回', current_intent_state: '意图状态' }
const INJECTION_PATTERN = /<(recalled_memories|current_intent_state)>[\s\S]*?<\/\1>/g

function parseUserContent(raw) {
  const injections = []
  const text = raw.replace(INJECTION_PATTERN, (block) => {
    const tag = block.slice(1, block.indexOf('>'))
    const openTag = `<${tag}>`
    const closeTag = `</${tag}>`
    const content = block.slice(openTag.length, block.length - closeTag.length).trim()
    injections.push({ label: INJECTION_LABELS[tag] || tag, content })
    return ''
  }).trim()
  return { text, injections }
}

function userInputFor(call) {
  const messages = call.request?.payload?.messages || []
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role !== 'user') continue
    const raw = typeof message.content === 'string' ? message.content : shortJson(message.content)
    if (!raw) return null
    const parsed = parseUserContent(raw)
    if (!parsed.text) return null
    return { key: `${index}:${raw}`, text: parsed.text, injections: parsed.injections }
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
    display: tool.name === 'update_intent_state' ? '' : tool.display,
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

function messageText(message) {
  return typeof message.content === 'string' ? message.content : shortJson(message.content)
}

function userParsed(message) {
  return parseUserContent(messageText(message))
}

function historyPreview(message) {
  if (message.role === 'user') return userParsed(message).text
  if (message.role === 'assistant' && !message.content) {
    const count = (message.tool_calls || []).length
    if (count) return `无正文 · ${count} 个工具调用`
  }
  if (message.role === 'tool') {
    const meta = toolMetaById.value.get(message.tool_call_id)
    if (meta) return `${meta.name} · ${meta.duration_ms} ms`
  }
  return messageText(message)
}

function fmtSeconds(totalMs) {
  return `${(totalMs / 1000).toFixed(1)}s`
}

function fmtDuration(durationMs) {
  if (durationMs == null) return ''
  return durationMs >= 1000 ? fmtSeconds(durationMs) : `${durationMs} ms`
}

function parseMaybeJson(content) {
  if (typeof content !== 'string') return null
  const trimmed = content.trim()
  if (!trimmed.startsWith('{') && !trimmed.startsWith('[')) return null
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2)
  } catch {
    return null
  }
}

function thinkingTotal(segments) {
  return segments.reduce((sum, segment) => sum + (segment.duration_ms || 0), 0)
}

function hasAnyOutput(call) {
  const response = call.response?.payload
  return Boolean(response?.content)
    || (response?.tool_calls || []).length > 0
    || (response?.thinking_segments || []).length > 0
}

const rawViews = reactive({})
const contextTabs = reactive({})

function isRawView(key, region) {
  return Boolean(rawViews[`${key}:${region}`])
}

function toggleRawView(key, region) {
  rawViews[`${key}:${region}`] = !rawViews[`${key}:${region}`]
}

function activeContextTab(key) {
  return contextTabs[key] ?? null
}

function selectContextTab(key, index) {
  contextTabs[key] = activeContextTab(key) === index ? null : index
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
      <div v-if="agents.length" class="context-tabs agent-tabs">
        <button type="button" :class="{ active: activeAgent === 'all' }" @click="activeAgent = 'all'">全部</button>
        <button v-for="agent in agents" :key="agent.key" type="button" :class="{ active: activeAgent === agent.key }" @click="activeAgent = agent.key">{{ agent.label }}</button>
      </div>
      <div v-if="!timeline.length" class="empty-hint">暂无执行轨迹。发送一条消息后，这里会展示模型调用过程。</div>

      <template v-for="(item, itemIndex) in timeline" :key="`${item.kind}:${item.created_at}:${item.role?.key || item.message?.key || itemIndex}`">
        <details v-if="item.kind === 'user'" class="trace-block type-user">
          <summary>
            <span class="block-head">
              <span class="block-pill">用户输入</span>
              <time class="block-time">{{ fmtTs(item.created_at) }}</time>
              <span class="block-caret">⌄</span>
            </span>
            <span class="block-main">{{ item.message.text }}</span>
          </summary>
          <div class="user-detail">
            <p class="block-body-text">{{ item.message.text }}</p>
            <div v-if="item.message.injections.length" class="context-tabs" role="tablist" aria-label="模型上下文">
              <button
                v-for="(injection, index) in item.message.injections"
                :key="index"
                type="button"
                role="tab"
                :aria-selected="activeContextTab(item.message.key) === index"
                :class="{ active: activeContextTab(item.message.key) === index }"
                @click="selectContextTab(item.message.key, index)"
              >{{ injection.label }}</button>
            </div>
            <pre v-if="activeContextTab(item.message.key) !== null" class="context-content">{{ item.message.injections[activeContextTab(item.message.key)].content }}</pre>
          </div>
        </details>

        <details v-else-if="item.kind === 'toolback'" class="trace-block type-toolback">
          <summary>
            <span class="block-head">
              <span class="block-pill">工具结果</span>
              <time class="block-time">{{ fmtTs(item.created_at) }}</time>
              <span class="block-caret">⌄</span>
            </span>
            <span class="block-main">{{ item.tools.map((tool) => tool.display).filter(Boolean).join(' · ') || `${item.tools.length} 个工具结果` }}</span>
          </summary>
          <div class="toolback-rows">
            <details v-for="tool in item.tools" :key="tool.id" class="toolback-row">
              <summary>
                <code class="tool-name">{{ tool.name }}</code>
                <strong v-if="tool.display" class="tool-desc">{{ tool.display }}</strong>
                <small class="tool-duration">{{ fmtDuration(tool.duration_ms) }}</small>
                <span class="block-caret">⌄</span>
              </summary>
              <pre>{{ tool.pretty ?? tool.content }}</pre>
            </details>
          </div>
        </details>

        <details v-else class="trace-block type-loop">
          <summary>
            <span class="block-head">
              <span class="block-pill">{{ item.role.label }}响应</span>
              <time class="block-time">{{ fmtTs(item.call.created_at) }}</time>
              <span class="block-caret">⌄</span>
            </span>
            <span class="block-main">{{ callSummary(item.call) }}</span>
          </summary>

          <div class="call-details">
            <section class="region">
              <header class="region-head">
                <strong>请求</strong>
                <small>{{ (item.call.request.payload?.messages || []).length }} 条消息 · {{ (item.call.request.payload?.tools || []).length }} 个工具</small>
                <button class="raw-toggle" type="button" @click="toggleRawView(item.call.key, 'request')">{{ isRawView(item.call.key, 'request') ? '可视化' : '原始 JSON' }}</button>
              </header>
              <pre v-if="isRawView(item.call.key, 'request')" class="raw-json">{{ shortJson(item.call.request.payload) }}</pre>
              <template v-else>
                <div class="msg-list">
                  <details v-for="(message, index) in item.call.request.payload?.messages || []" :key="index" class="msg-row">
                    <summary>
                      <span class="msg-role" :class="`role-${message.role || 'message'}`">{{ message.role || 'message' }}</span>
                      <span class="msg-preview">{{ historyPreview(message) }}</span>
                    </summary>
                    <div class="msg-detail">
                      <template v-if="message.role === 'user' && userParsed(message).injections.length">
                        <p class="msg-text">{{ userParsed(message).text }}</p>
                        <div class="context-tabs" role="tablist" aria-label="模型上下文">
                          <button
                            v-for="(injection, injectIndex) in userParsed(message).injections"
                            :key="injectIndex"
                            type="button"
                            role="tab"
                            :aria-selected="activeContextTab(`${item.call.key}:${index}`) === injectIndex"
                            :class="{ active: activeContextTab(`${item.call.key}:${index}`) === injectIndex }"
                            @click="selectContextTab(`${item.call.key}:${index}`, injectIndex)"
                          >{{ injection.label }}</button>
                        </div>
                        <pre v-if="activeContextTab(`${item.call.key}:${index}`) !== null" class="context-content">{{ userParsed(message).injections[activeContextTab(`${item.call.key}:${index}`)].content }}</pre>
                      </template>
                      <template v-else>
                        <pre v-if="messageText(message)">{{ messageText(message) }}</pre>
                        <ul v-if="(message.tool_calls || []).length" class="assistant-tools">
                          <li v-for="toolCall in message.tool_calls" :key="toolCall.id">{{ toolCall.function?.name }}</li>
                        </ul>
                      </template>
                    </div>
                  </details>
                </div>
                <details v-if="(item.call.request.payload?.tools || []).length" class="schema-list">
                  <summary>工具定义 · {{ item.call.request.payload.tools.length }}<span class="block-caret">⌄</span></summary>
                  <div v-for="tool in item.call.request.payload.tools" :key="tool.function?.name" class="schema-row">
                    <code>{{ tool.function?.name }}</code>
                    <span>{{ tool.function?.description }}</span>
                  </div>
                </details>
              </template>
            </section>

            <section class="region">
              <header class="region-head">
                <strong>响应</strong>
                <div class="response-meta">
                  <span v-if="item.call.request.payload?.model" class="model-chip">{{ item.call.request.payload.model }}</span>
                  <span class="finish-chip" :class="`finish-${finishReason(item.call)}`">{{ finishReason(item.call) }}</span>
                </div>
                <button class="raw-toggle" type="button" :disabled="!item.call.response" @click="toggleRawView(item.call.key, 'response')">{{ isRawView(item.call.key, 'response') ? '可视化' : '原始 JSON' }}</button>
              </header>
              <p v-if="!item.call.response" class="pending-hint">模型请求已发出，等待响应…</p>
              <pre v-else-if="isRawView(item.call.key, 'response')" class="raw-json">{{ shortJson(item.call.response.payload) }}</pre>
              <template v-else>
                <div v-if="hasAnyOutput(item.call)" class="part-list">
                  <details v-if="(item.call.response.payload?.thinking_segments || []).length" class="part-row">
                    <summary>
                      <span class="part-tag tag-thinking">思考</span>
                      <small class="part-note">{{ item.call.response.payload.thinking_segments.length }} 段 · {{ fmtSeconds(thinkingTotal(item.call.response.payload.thinking_segments)) }}</small>
                      <span class="block-caret">⌄</span>
                    </summary>
                    <div class="part-body">
                      <div v-for="(segment, index) in item.call.response.payload.thinking_segments" :key="index" class="think-seg">
                        <div class="seg-head">
                          <small>第 {{ index + 1 }} 段</small>
                          <time>{{ fmtSeconds(segment.duration_ms || 0) }}</time>
                        </div>
                        <pre>{{ segment.text }}</pre>
                      </div>
                    </div>
                  </details>
                  <details v-if="item.call.response.payload?.content" class="part-row">
                    <summary>
                      <span class="part-tag tag-content">正文</span>
                      <span class="part-desc">{{ previewText(item.call.response.payload.content, 72) }}</span>
                      <span class="block-caret">⌄</span>
                    </summary>
                    <div class="part-body">
                      <p class="part-text">{{ item.call.response.payload.content }}</p>
                    </div>
                  </details>
                  <details v-for="tool in toolsFor(item.call)" :key="tool.id" class="part-row">
                    <summary>
                      <span class="part-tag tag-tool">工具调用</span>
                      <code class="part-tool-name">{{ tool.name }}</code>
                      <span v-if="tool.display" class="part-desc">{{ tool.display }}</span>
                      <span class="block-caret">⌄</span>
                    </summary>
                    <div class="part-body">
                      <pre class="part-code">{{ shortJson(tool.arguments) }}</pre>
                    </div>
                  </details>
                </div>
                <p v-else class="empty-line">无输出</p>
              </template>
            </section>
          </div>
        </details>
      </template>
    </section>
  </aside>
</template>

<style scoped>
.console-panel { display: flex; flex-direction: column; width: 100%; height: 100%; overflow: hidden; background: #fff; color: var(--ch-text); }
.console-header { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; min-height: 28px; margin: 0; padding: var(--ch-space-4) var(--ch-space-3) 0; background: #fff; }
.sidebar-title { margin: 0; font-size: var(--ch-text-lg); font-weight: var(--ch-font-bold); letter-spacing: .3px; }
.sidebar-collapse { width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; padding: 0; border: 0; border-radius: var(--ch-radius-btn); background: transparent; color: var(--ch-text-faint); cursor: pointer; transition: background var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease); }
.sidebar-collapse:hover { background: var(--ch-surface-2); color: var(--ch-text); }
.sidebar-collapse :deep(svg) { width: 20px; height: 20px; transform: translateX(6px); fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.trace-body { flex: 1; overflow-y: auto; padding: var(--ch-space-3) var(--ch-space-3) var(--ch-space-5); background: #fff; }
.empty-hint { padding: 56px var(--ch-space-3); color: var(--ch-text-muted); text-align: center; line-height: 1.7; }
.trace-block > summary::-webkit-details-marker, .toolback-row > summary::-webkit-details-marker, .msg-row > summary::-webkit-details-marker, .inject-fold > summary::-webkit-details-marker, .schema-list > summary::-webkit-details-marker, .part-row > summary::-webkit-details-marker { display: none; }
.trace-block { margin: 0 0 var(--ch-space-3); border: 1px solid var(--ch-border); border-radius: var(--ch-radius-list); background: var(--ch-surface); overflow: hidden; }
.trace-block > summary { display: block; padding: var(--ch-space-3); cursor: pointer; list-style: none; }
.block-head { display: flex; align-items: center; gap: var(--ch-space-2); }
.block-head .block-time { margin-left: auto; }
.block-pill { display: inline-flex; align-items: center; padding: var(--ch-space-1) var(--ch-space-2); border-radius: 4px; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); font-weight: var(--ch-font-semibold); line-height: 1.4; white-space: nowrap; }
.block-time { color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); white-space: nowrap; }
.block-caret { color: var(--ch-text-muted); transition: transform var(--ch-duration-fast) var(--ch-ease); }
.trace-block:not([open]) .block-caret { transform: rotate(-90deg); }
.block-main { display: block; overflow: hidden; margin-top: var(--ch-space-2); color: var(--ch-text); font-size: var(--ch-text-sm); font-weight: var(--ch-font-medium); line-height: 1.6; white-space: nowrap; text-overflow: ellipsis; }
.user-detail { display: flex; flex-direction: column; gap: var(--ch-space-2); padding: var(--ch-space-2) var(--ch-space-3) var(--ch-space-3); }
.block-body-text, .msg-text, .part-text { margin: 0; max-height: 240px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
.context-tabs { display: flex; gap: var(--ch-space-2); }
.agent-tabs { flex-wrap: wrap; margin: 0 0 var(--ch-space-3); }
.context-tabs button { padding: var(--ch-space-1) var(--ch-space-2); border: 1px solid var(--ch-border); border-radius: 4px; background: var(--ch-surface); color: var(--ch-text-muted); font-size: var(--ch-text-xs); line-height: 1.4; cursor: pointer; }
.context-tabs button:hover { color: var(--ch-text-secondary); background: var(--ch-surface-2); }
.context-tabs button.active { border-color: var(--ch-accent-border); background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); font-weight: var(--ch-font-semibold); }
.context-content { max-height: 160px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.type-user .block-pill { background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); }
.type-user .block-main { color: var(--ch-text); }
.trace-block[open] .block-main { display: none; }
.trace-block[open] > summary { padding-bottom: 0; }
.type-toolback .block-pill { background: var(--ch-success-soft); color: var(--ch-success-text); }
.type-loop .block-pill { background: color-mix(in srgb, var(--ch-border) 60%, var(--ch-surface)); color: var(--ch-text-secondary); }
.finish-chip { display: inline-flex; align-items: center; padding: var(--ch-space-1) var(--ch-space-2); border: 1px solid var(--ch-border); border-radius: 4px; color: var(--ch-text-secondary); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); line-height: 1.4; white-space: nowrap; }
.finish-length { background: var(--ch-warning-soft); color: var(--ch-warning-text); }
.finish-请求中 { background: var(--ch-info-soft); color: var(--ch-info-text); }
.call-details { padding: var(--ch-space-2) var(--ch-space-3) var(--ch-space-3); }
.toolback-rows { margin: var(--ch-space-2) var(--ch-space-3) var(--ch-space-3); overflow: hidden; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-btn); }
.toolback-row { font-size: var(--ch-text-xs); }
.toolback-row summary { display: flex; align-items: center; gap: var(--ch-space-2); padding: var(--ch-space-2); cursor: pointer; list-style: none; }
.toolback-row + .toolback-row { border-top: 1px solid var(--ch-border); }
.toolback-row .block-caret { margin-left: auto; }
.toolback-row:not([open]) .block-caret { transform: rotate(-90deg); }
.toolback-row .tool-name { flex-shrink: 0; color: var(--ch-text-secondary); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); }
.toolback-row .tool-desc { flex: 1; min-width: 0; overflow: hidden; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); font-weight: 400; text-overflow: ellipsis; white-space: nowrap; }
.toolback-row .tool-duration { flex-shrink: 0; color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); white-space: nowrap; }
.toolback-row pre { max-height: 160px; margin: 0 var(--ch-space-2) var(--ch-space-2); overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
pre { margin: 0; font-family: var(--ch-font-mono); white-space: pre-wrap; word-break: break-word; }
.region + .region { margin-top: var(--ch-space-3); }
.region > * + * { margin-top: var(--ch-space-2); }
.region-head { display: flex; align-items: center; gap: var(--ch-space-2); }
.region-head strong { color: var(--ch-text-secondary); font-size: var(--ch-text-xs); font-weight: var(--ch-font-semibold); }
.region-head small { color: var(--ch-text-muted); font-size: var(--ch-text-xs); white-space: nowrap; }
.model-chip { display: inline-flex; align-items: center; padding: var(--ch-space-1) var(--ch-space-2); border: 1px solid var(--ch-border); border-radius: 4px; color: var(--ch-text-secondary); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); line-height: 1.4; white-space: nowrap; }
.response-meta { display: flex; align-items: center; gap: var(--ch-space-2); min-width: 0; }
.raw-toggle { margin-left: auto; padding: var(--ch-space-1) var(--ch-space-2); border: 1px solid var(--ch-border); border-radius: 4px; background: transparent; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.4; cursor: pointer; }
.raw-toggle:disabled { color: var(--ch-text-faint); cursor: not-allowed; }
.raw-json { max-height: 320px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.msg-list { overflow: hidden; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-btn); }
.msg-row + .msg-row { border-top: 1px solid var(--ch-border); }
.msg-row summary { display: flex; align-items: center; gap: var(--ch-space-2); padding: var(--ch-space-2); cursor: pointer; list-style: none; }
.msg-role { flex-shrink: 0; width: 56px; padding: 2px 0; border-radius: 4px; text-align: center; font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); line-height: 1.5; }
.role-user { background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); }
.role-assistant { background: var(--ch-surface-2); color: var(--ch-text-secondary); }
.role-system { background: var(--ch-surface-2); color: var(--ch-text-faint); }
.role-tool { background: var(--ch-success-soft); color: var(--ch-success-text); }
.msg-preview { flex: 1; min-width: 0; overflow: hidden; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); white-space: nowrap; text-overflow: ellipsis; }
.msg-detail { display: flex; flex-direction: column; gap: var(--ch-space-2); padding: 0 var(--ch-space-2) var(--ch-space-2); }
.msg-detail pre { max-height: 160px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.assistant-tools { margin: 0; padding: 0; list-style: none; color: var(--ch-text-secondary); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); }
.schema-list { overflow: hidden; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-btn); background: var(--ch-surface); }
.schema-list summary { display: flex; align-items: center; padding: var(--ch-space-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); cursor: pointer; list-style: none; }
.schema-list .block-caret { margin-left: auto; }
.schema-list:not([open]) .block-caret { transform: rotate(-90deg); }
.schema-list[open] summary { border-bottom: 1px solid var(--ch-border); }
.schema-row { display: flex; align-items: center; gap: var(--ch-space-2); min-width: 0; padding: var(--ch-space-2); }
.schema-row + .schema-row { border-top: 1px solid var(--ch-border); }
.schema-row code { flex-shrink: 0; padding: 2px var(--ch-space-1); border-radius: 4px; background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); }
.schema-row span { min-width: 0; overflow: hidden; color: var(--ch-text-muted); font-size: var(--ch-text-xs); white-space: nowrap; text-overflow: ellipsis; }
.part-list { overflow: hidden; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-btn); }
.part-row + .part-row { border-top: 1px solid var(--ch-border); }
.part-row summary { display: flex; align-items: center; gap: var(--ch-space-2); padding: var(--ch-space-2); cursor: pointer; list-style: none; }
.part-row .block-caret { margin-left: auto; }
.part-row:not([open]) .block-caret { transform: rotate(-90deg); }
.part-row[open] .part-desc, .msg-row[open] .msg-preview, .toolback-row[open] .tool-desc { display: none; }
.part-tag { flex-shrink: 0; width: 56px; padding: 2px 0; border-radius: 4px; text-align: center; font-size: var(--ch-text-xs); line-height: 1.5; }
.tag-thinking { background: var(--ch-info-soft); color: var(--ch-info-text); }
.tag-content { background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); }
.tag-tool { background: var(--ch-success-soft); color: var(--ch-success-text); }
.part-note { color: var(--ch-text-muted); font-size: var(--ch-text-xs); white-space: nowrap; }
.part-tool-name { flex-shrink: 0; color: var(--ch-text-secondary); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); }
.part-desc { flex: 1; min-width: 0; overflow: hidden; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); white-space: nowrap; text-overflow: ellipsis; }
.part-body { display: flex; flex-direction: column; gap: var(--ch-space-2); padding: 0 var(--ch-space-2) var(--ch-space-2); }
.part-code { max-height: 160px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.think-seg { padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); }
.seg-head { display: flex; align-items: baseline; justify-content: space-between; color: var(--ch-text-muted); font-size: var(--ch-text-xs); }
.seg-head time { font-family: var(--ch-font-mono); }
.think-seg pre { max-height: 144px; margin-top: var(--ch-space-2); overflow: auto; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.pending-hint, .empty-line { margin: 0; color: var(--ch-text-muted); font-size: var(--ch-text-xs); }
@media (max-width: 780px) { .console-header { padding: var(--ch-space-3) var(--ch-space-3) 0; } .trace-body { padding: var(--ch-space-3) var(--ch-space-2) var(--ch-space-4); } }
</style>
