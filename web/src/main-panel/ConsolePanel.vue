<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ChevronDown, PanelLeft } from '@lucide/vue'
import {
  BYPASS_PURPOSE_LABELS,
  buildBypassCalls,
  buildModelCalls,
  buildSessionStats,
  buildTimeline,
  buildUserInputs,
  messageText,
  parseUserContent,
  shortJson,
  toolCallArguments,
  toolsFor,
} from '../composables/consoleProjection.js'
import { ROLE_FULL, ROLE_LABELS, ROLE_SHORT } from '../team-panel/roleMeta.js'

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

function agentNameFor(source, taskId) {
  if (source === 'supervisor' || !source) return ROLE_LABELS.chief
  if (source === 'scheduler') return '调度器'
  const task = taskById.value.get(taskId)
  return task?.display_name || task?.agent_name || ROLE_FULL[task?.agent_type] || '子代理'
}

const modelCalls = computed(() => buildModelCalls(traces.value))

const bypassCalls = computed(() => buildBypassCalls(traces.value))

const userInputs = computed(() => buildUserInputs(traces.value))

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
  for (const call of [...modelCalls.value, ...bypassCalls.value]) {
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

const visibleBypass = computed(() => {
  if (activeAgent.value === 'all') return bypassCalls.value
  return bypassCalls.value.filter((call) => roleFor(call.source, call.task_id).key === activeAgent.value)
})

const visibleUserInputs = computed(() => {
  if (activeAgent.value === 'all') return userInputs.value
  return userInputs.value.filter((item) => roleFor(item.source, null).key === activeAgent.value)
})

const timelineAll = computed(() => buildTimeline(modelCalls.value, bypassCalls.value, userInputs.value, roleFor))

const timeline = computed(() => {
  if (activeAgent.value === 'all') return timelineAll.value
  return buildTimeline(visibleCalls.value, visibleBypass.value, visibleUserInputs.value, roleFor)
})

const sessionStats = computed(() => buildSessionStats(
  modelCalls.value,
  bypassCalls.value,
  timelineAll.value.filter((item) => item.kind === 'loop').at(-1)?.turn || 0,
))

const turnGroups = computed(() => {
  const groups = []
  for (const item of timeline.value) {
    if (!groups.length || groups.at(-1).turn !== item.turn) {
      groups.push({ turn: item.turn, items: [], start: item.created_at, end: item.created_at })
    }
    const group = groups.at(-1)
    group.items.push(item)
    let end = item.created_at
    if (item.kind === 'loop') end += (item.call.response?.payload?.duration_ms || 0) / 1000
    if (item.kind === 'bypass') end += (item.item.payload?.duration_ms || 0) / 1000
    group.end = Math.max(group.end, end)
  }
  for (const group of groups) {
    group.callCount = group.items.filter((entry) => entry.kind === 'loop').length
    group.toolCount = group.items.filter((entry) => entry.kind === 'toolback').reduce((sum, entry) => sum + entry.tools.length, 0)
    group.durationMs = (group.end - group.start) * 1000
    const loop = group.items.find((entry) => entry.kind === 'loop')
    const bypassItem = group.items.find((entry) => entry.kind === 'bypass')
    group.agentName = loop
      ? agentNameFor(loop.call.source, loop.call.task_id)
      : (bypassItem ? agentNameFor(bypassItem.item.source, bypassItem.item.task_id) : '—')
  }
  return groups
})

function userParsed(message) {
  return parseUserContent(messageText(message))
}

function bypassPurposeLabel(purpose) {
  return BYPASS_PURPOSE_LABELS[purpose] || purpose || '旁路调用'
}

function fmtTs(value) {
  if (!value) return ''
  const date = new Date(value * 1000)
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  const ss = String(date.getSeconds()).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

function historyPreview(message) {
  if (message.role === 'user') return userParsed(message).text
  if (message.role === 'assistant' && !message.content) {
    if (message.reasoning_content) return '无正文 · think'
    const count = (message.tool_calls || []).length
    if (count) return `无正文 · ${count} 个工具调用`
  }
  if (message.role === 'tool') {
    const meta = toolMetaById.value.get(message.tool_call_id)
    if (meta) return meta.name
  }
  return messageText(message)
}

function messageRoleLabel(role) {
  if (role === 'system') return 'sys'
  if (role === 'assistant') return 'ass'
  return role || 'message'
}

function fmtSeconds(totalMs) {
  return `${(totalMs / 1000).toFixed(1)}s`
}

function fmtSecondsZh(totalMs) {
  return `${(totalMs / 1000).toFixed(1)}秒`
}

function fmtDuration(durationMs) {
  if (durationMs == null) return ''
  return durationMs >= 1000 ? fmtSeconds(durationMs) : `${durationMs} ms`
}

function fmtTokens(value) {
  return new Intl.NumberFormat('zh-CN').format(value)
}

function fmtCost(value) {
  return `¥${Number(value).toFixed(4)}`
}

function callStatus(call) {
  if (!call.response) return 'pending'
  return call.response.payload?.status || 'success'
}

function callStatusLabel(call) {
  return ({ success: '成功', error: '失败', pending: '进行中' })[callStatus(call)]
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

      <div v-if="sessionStats" class="session-overview">
        <h3 class="overview-title">会话总览</h3>
        <div class="overview-grid">
          <span class="overview-item"><span class="overview-label">总耗时</span><span class="overview-value">{{ fmtDuration(sessionStats.durationMs) }}</span></span>
          <span class="overview-item"><span class="overview-label">对话轮次</span><span class="overview-value">{{ sessionStats.turnCount }} 轮</span></span>
          <span class="overview-item"><span class="overview-label">模型调用</span><span class="overview-value">{{ sessionStats.callCount }} 次</span></span>
          <span class="overview-item"><span class="overview-label">工具执行</span><span class="overview-value">{{ sessionStats.toolCount }} 次</span></span>
          <span class="overview-item"><span class="overview-label">旁路调用</span><span class="overview-value">{{ sessionStats.bypassCount }} 次</span></span>
          <span class="overview-item"><span class="overview-label">总费用</span><span class="overview-value">{{ sessionStats.costCny != null ? fmtCost(sessionStats.costCny) : '未配置' }}</span></span>
          <span class="overview-item"><span class="overview-label">输入 Token</span><span class="overview-value">{{ fmtTokens(sessionStats.inputTokens) }}</span></span>
          <span class="overview-item"><span class="overview-label">输出 Token</span><span class="overview-value">{{ fmtTokens(sessionStats.outputTokens) }}</span></span>
          <span class="overview-item"><span class="overview-label">Token 总计</span><span class="overview-value">{{ fmtTokens(sessionStats.totalTokens) }}</span></span>
        </div>
      </div>

      <details v-for="group in turnGroups" :key="group.turn" class="turn-group" open>
        <summary>
          <span v-if="group.turn" class="turn-index">{{ group.turn }}</span>
          <span class="turn-title">{{ group.turn ? `第 ${group.turn} 轮对话` : '旁路调用' }}</span>
          <span class="turn-agent">{{ group.agentName }}</span>
          <span class="turn-meta">{{ fmtDuration(group.durationMs) }} · {{ fmtTs(group.start) }}</span>
          <ChevronDown class="block-caret" aria-hidden="true" />
        </summary>
        <div class="turn-items">
          <template v-for="(item, itemIndex) in group.items" :key="`${item.kind}:${item.created_at}:${item.role?.key || item.message?.key || item.item?.key || itemIndex}`">
            <details v-if="item.kind === 'user'" class="trace-block type-user">
              <summary>
                <span class="block-head">
                  <span class="block-pill">用户输入</span>
                  <ChevronDown class="block-caret end-caret" aria-hidden="true" />
                </span>
                <span class="block-main">{{ item.message.text }}</span>
              </summary>
              <div v-if="item.message.injections.length" class="user-detail">
                <div class="user-context-head">
                  <div class="context-tabs user-context-tabs" role="tablist" aria-label="模型上下文">
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
                </div>
                <pre v-if="activeContextTab(item.message.key) !== null" class="context-content">{{ item.message.injections[activeContextTab(item.message.key)].content }}</pre>
              </div>
            </details>

            <details v-else-if="item.kind === 'toolback'" class="trace-block type-toolback">
              <summary>
                <span class="block-head">
                  <span class="block-pill">工具结果</span>
                  <time v-if="item.total_ms" class="block-time">耗时 {{ fmtDuration(item.total_ms) }}</time>
                  <ChevronDown :class="['block-caret', { 'end-caret': !item.total_ms }]" aria-hidden="true" />
                </span>
                <span class="block-main">{{ item.tools.length }} 个工具结果</span>
              </summary>
              <div class="toolback-rows">
                <div class="toolback-list">
                  <details v-for="tool in item.tools" :key="tool.id" class="toolback-row">
                    <summary>
                      <code class="tool-name">{{ tool.name }}</code>
                      <span class="tool-result-meta">
                        <span class="tool-status" :class="`status-${tool.status}`">{{ tool.status === 'error' ? '失败' : '成功' }}</span>
                        <small class="tool-duration">{{ fmtDuration(tool.duration_ms) }}</small>
                      </span>
                      <ChevronDown class="block-caret" aria-hidden="true" />
                    </summary>
                    <pre>{{ tool.pretty ?? tool.content }}</pre>
                  </details>
                </div>
              </div>
            </details>

            <details v-else-if="item.kind === 'bypass'" class="trace-block type-bypass">
              <summary>
                <span class="block-head">
                  <span class="block-pill">旁路调用</span>
                  <span class="bypass-purpose">{{ bypassPurposeLabel(item.item.payload.purpose) }}</span>
                  <span class="call-status" :class="`status-${item.item.payload.status || 'success'}`">{{ item.item.payload.status === 'error' ? '失败' : '成功' }}</span>
                  <span v-if="item.item.payload.duration_ms != null" class="block-time">耗时 {{ fmtDuration(item.item.payload.duration_ms) }}</span>
                  <ChevronDown :class="['block-caret', { 'end-caret': item.item.payload.duration_ms == null }]" aria-hidden="true" />
                </span>
                <span class="call-metrics">
                  <span class="call-model"><span>模型：{{ item.item.payload.model || '—' }}</span><span>思考：—</span></span>
                  <span class="call-usage">
                    <span>输入：{{ item.item.payload.usage ? fmtTokens(item.item.payload.usage.input_tokens) : '—' }}</span>
                    <span>输出：{{ item.item.payload.usage ? fmtTokens(item.item.payload.usage.output_tokens) : '—' }}</span>
                    <span>额度：{{ item.item.payload.cost_cny != null ? fmtCost(item.item.payload.cost_cny) : '未配置' }}</span>
                  </span>
                </span>
              </summary>

              <div class="call-details bypass-details">
                <section class="region">
                  <header class="region-head">
                    <strong>请求</strong>
                    <small>{{ item.item.payload.model || '—' }} · 上限 {{ item.item.payload.max_tokens }} token</small>
                  </header>
                  <pre class="bypass-prompt">{{ item.item.payload.prompt }}</pre>
                </section>

                <section class="region">
                  <header class="region-head">
                    <strong>响应</strong>
                    <small v-if="item.item.payload.usage">输入 {{ fmtTokens(item.item.payload.usage.input_tokens) }} · 输出 {{ fmtTokens(item.item.payload.usage.output_tokens) }}<template v-if="item.item.payload.cost_cny != null"> · 额度 {{ fmtCost(item.item.payload.cost_cny) }}</template></small>
                  </header>
                  <pre v-if="item.item.payload.status === 'error'" class="bypass-error">{{ item.item.payload.error || '调用失败' }}</pre>
                  <pre v-else class="bypass-content">{{ item.item.payload.content || '（无输出）' }}</pre>
                </section>
              </div>
            </details>

            <details v-else class="trace-block type-loop">
              <summary>
                <span class="block-head">
                  <span class="block-pill">模型输出</span>
                  <span class="call-status" :class="`status-${callStatus(item.call)}`">{{ callStatusLabel(item.call) }}</span>
                  <span v-if="item.call.response?.payload?.duration_ms != null" class="block-time">耗时 {{ fmtDuration(item.call.response.payload.duration_ms) }}</span>
                  <ChevronDown class="block-caret" aria-hidden="true" />
                </span>
                <span class="call-metrics">
                  <span class="call-model"><span>模型：{{ item.call.request.payload?.model || '—' }}</span><span>思考：{{ (item.call.response?.payload?.thinking_segments || []).length ? fmtSecondsZh(thinkingTotal(item.call.response.payload.thinking_segments)) : '—' }}</span></span>
                  <span class="call-usage">
                    <span>输入：{{ item.call.response?.payload?.usage ? fmtTokens(item.call.response.payload.usage.input_tokens) : '—' }}</span>
                    <span>输出：{{ item.call.response?.payload?.usage ? fmtTokens(item.call.response.payload.usage.output_tokens) : '—' }}</span>
                    <span>额度：{{ item.call.response?.payload?.cost_cny != null ? fmtCost(item.call.response.payload.cost_cny) : '未配置' }}</span>
                  </span>
                </span>
              </summary>

              <div class="call-details">
                <section class="region">
                  <header class="region-head">
                    <strong>请求</strong>
                    <button class="raw-toggle" :class="{ active: isRawView(item.call.key, 'request') }" type="button" :aria-label="isRawView(item.call.key, 'request') ? '返回请求详情' : '查看请求原始 JSON'" @click="toggleRawView(item.call.key, 'request')">{{ isRawView(item.call.key, 'request') ? '返回详情' : '原始 JSON' }}</button>
                  </header>
                  <pre v-if="isRawView(item.call.key, 'request')" class="raw-json">{{ shortJson(item.call.request.payload) }}</pre>
                  <template v-else>
                    <div class="msg-list">
                      <details v-for="(message, index) in item.call.request.payload?.messages || []" :key="index" class="msg-row">
                        <summary>
                          <span class="msg-role" :class="`role-${message.role || 'message'}`">{{ messageRoleLabel(message.role) }}</span>
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
                          <template v-else-if="message.role === 'assistant'">
                            <pre v-if="messageText(message)">{{ messageText(message) }}</pre>
                            <div
                              v-if="message.reasoning_content || (message.tool_calls || []).length"
                              class="context-tabs mono-tabs"
                              role="tablist"
                              aria-label="思考与工具调用"
                            >
                              <button
                                v-if="message.reasoning_content"
                                type="button"
                                role="tab"
                                :aria-selected="activeContextTab(`${item.call.key}:${index}`) === 0"
                                :class="{ active: activeContextTab(`${item.call.key}:${index}`) === 0 }"
                                @click="selectContextTab(`${item.call.key}:${index}`, 0)"
                              >think</button>
                              <button
                                v-for="(toolCall, toolIndex) in message.tool_calls || []"
                                :key="toolCall.id"
                                type="button"
                                role="tab"
                                :aria-selected="activeContextTab(`${item.call.key}:${index}`) === toolIndex + 1"
                                :class="{ active: activeContextTab(`${item.call.key}:${index}`) === toolIndex + 1 }"
                                @click="selectContextTab(`${item.call.key}:${index}`, toolIndex + 1)"
                              >{{ toolCall.function?.name }}</button>
                            </div>
                            <pre
                              v-if="message.reasoning_content && activeContextTab(`${item.call.key}:${index}`) === 0"
                              class="context-content"
                            >{{ message.reasoning_content }}</pre>
                            <template v-for="(toolCall, toolIndex) in message.tool_calls || []" :key="toolCall.id">
                              <pre
                                v-if="activeContextTab(`${item.call.key}:${index}`) === toolIndex + 1"
                                class="context-content"
                              >{{ toolCallArguments(toolCall) }}</pre>
                            </template>
                          </template>
                          <template v-else>
                            <pre v-if="messageText(message)">{{ messageText(message) }}</pre>
                          </template>
                        </div>
                      </details>
                    </div>
                    <details v-if="(item.call.request.payload?.tools || []).length" class="schema-list">
                      <summary>工具定义 · {{ item.call.request.payload.tools.length }}<ChevronDown class="block-caret" aria-hidden="true" /></summary>
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
                    <button class="raw-toggle" :class="{ active: isRawView(item.call.key, 'response') }" type="button" :disabled="!item.call.response" :aria-label="isRawView(item.call.key, 'response') ? '返回响应详情' : '查看响应原始 JSON'" @click="toggleRawView(item.call.key, 'response')">{{ isRawView(item.call.key, 'response') ? '返回详情' : '原始 JSON' }}</button>
                  </header>
                  <p v-if="!item.call.response" class="pending-hint">模型请求已发出，等待响应…</p>
                  <pre v-else-if="isRawView(item.call.key, 'response')" class="raw-json">{{ shortJson(item.call.response.payload) }}</pre>
                  <template v-else>
                    <div v-if="hasAnyOutput(item.call)" class="part-list">
                      <details v-if="(item.call.response.payload?.thinking_segments || []).length" class="part-row">
                        <summary>
                          <span class="part-tag tag-thinking">think</span>
                          <span class="part-desc">{{ previewText(item.call.response.payload.thinking_segments.map((segment) => segment.text).join(' '), 72) }}</span>
                          <ChevronDown class="block-caret" aria-hidden="true" />
                        </summary>
                        <div class="part-body">
                          <div v-for="(segment, index) in item.call.response.payload.thinking_segments" :key="index" class="think-seg">
                            <pre>{{ segment.text }}</pre>
                          </div>
                        </div>
                      </details>
                      <details v-if="item.call.response.payload?.content" class="part-row">
                        <summary>
                          <span class="part-tag tag-content">正文</span>
                          <span class="part-desc">{{ previewText(item.call.response.payload.content, 72) }}</span>
                          <ChevronDown class="block-caret" aria-hidden="true" />
                        </summary>
                        <div class="part-body">
                          <p class="part-text">{{ item.call.response.payload.content }}</p>
                        </div>
                      </details>
                      <details v-for="tool in toolsFor(item.call)" :key="tool.id" class="part-row">
                        <summary>
                          <span class="part-tag tag-call">call</span>
                          <code class="part-tool-name">{{ tool.name }}</code>
                          <ChevronDown class="block-caret" aria-hidden="true" />
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
        </div>
      </details>
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
.trace-body { flex: 1; overflow-y: auto; scrollbar-width: none; padding: var(--ch-space-3) var(--ch-space-3) var(--ch-space-5); background: #fff; }
.trace-body::-webkit-scrollbar { display: none; }
.empty-hint { padding: 56px var(--ch-space-3); color: var(--ch-text-muted); text-align: center; line-height: 1.7; }
.trace-block > summary::-webkit-details-marker, .turn-group > summary::-webkit-details-marker, .toolback-row > summary::-webkit-details-marker, .msg-row > summary::-webkit-details-marker, .inject-fold > summary::-webkit-details-marker, .schema-list > summary::-webkit-details-marker, .part-row > summary::-webkit-details-marker { display: none; }
.trace-block { position: relative; interpolate-size: allow-keywords; margin: 0 0 var(--ch-space-3); border: 1px solid var(--ch-border); border-radius: var(--ch-radius-list); background: var(--ch-surface); overflow: visible; }
.trace-block::details-content { height: 0; overflow: clip; content-visibility: hidden; transition: height 0.25s ease, content-visibility 0.25s allow-discrete; }
.trace-block[open]::details-content { height: auto; content-visibility: visible; }
.trace-block > summary { position: relative; display: block; padding: var(--ch-space-3); cursor: pointer; list-style: none; }
.block-head { display: flex; align-items: center; gap: var(--ch-space-2); }
.block-head .block-time { margin-left: auto; }
.end-caret { margin-left: auto; }
.session-overview { margin: 0 0 var(--ch-space-3); padding: var(--ch-space-3); border: 1px solid var(--ch-border); border-radius: var(--ch-radius-list); }
.overview-title { margin: 0 0 var(--ch-space-2); color: var(--ch-text-secondary); font-size: var(--ch-text-sm); font-weight: var(--ch-font-bold); }
.overview-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--ch-space-1) var(--ch-space-3); }
.overview-item { display: flex; align-items: baseline; gap: var(--ch-space-2); min-width: 0; }
.overview-label { flex-shrink: 0; color: var(--ch-text-muted); font-size: var(--ch-text-xs); white-space: nowrap; }
.overview-value { color: var(--ch-text); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); white-space: nowrap; }
.turn-group { position: relative; interpolate-size: allow-keywords; margin: 0; }
.turn-group > summary { position: relative; display: flex; align-items: center; gap: 0; padding: var(--ch-space-2) var(--ch-space-2) var(--ch-space-2) calc(var(--ch-space-4) + 2px); line-height: 24px; cursor: pointer; list-style: none; }
.turn-index { position: absolute; z-index: 1; top: 50%; left: -6px; display: inline-flex; width: 24px; height: 24px; align-items: center; justify-content: center; border-radius: 6px; background: var(--ch-surface-2); color: var(--ch-text-faint); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); font-weight: var(--ch-font-semibold); line-height: 1; transform: translateY(-50%); }
.turn-group[open] .turn-index { background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); }
.turn-group[open] > summary { margin-bottom: var(--ch-space-2); }
.turn-group[open] > summary::after { content: ''; position: absolute; top: calc(50% + 12px); right: auto; bottom: calc(-1 * var(--ch-space-2)); left: 6px; width: 1px; background: var(--ch-border-strong); }
.turn-group[open]:has(+ .turn-group)::after { content: ''; position: absolute; z-index: 0; bottom: -20px; left: 6px; width: 1px; height: 20px; background: var(--ch-border-strong); }
.turn-group > summary > .block-caret { margin-left: var(--ch-space-2); }
.turn-title { color: var(--ch-text-secondary); font-size: var(--ch-text-sm); font-weight: var(--ch-font-bold); white-space: nowrap; }
.turn-agent { flex-shrink: 0; margin-left: auto; color: var(--ch-text-muted); font-size: var(--ch-text-xs); font-weight: var(--ch-font-medium); line-height: 1.4; white-space: nowrap; }
.turn-meta { display: inline-flex; align-items: center; flex-shrink: 1; min-width: 0; overflow: hidden; color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); white-space: nowrap; text-overflow: ellipsis; }
.turn-meta::before { content: '·'; flex-shrink: 0; margin: 0 var(--ch-space-2); }
.turn-group:not([open]) .block-caret { transform: rotate(-90deg); }
.turn-group:not([open]) > .turn-items { display: none; }
.turn-items { position: relative; padding: 0 0 0 calc(var(--ch-space-4) + 2px); }
.turn-items::before { content: ''; position: absolute; left: 6px; top: 0; bottom: 0; width: 1px; background: var(--ch-border-strong); }
.trace-block > summary::before { content: ''; position: absolute; z-index: 1; left: calc(-1 * var(--ch-space-4)); top: 50%; width: 7px; height: 7px; border-radius: 50%; transform: translateY(-50%); }
.trace-block.type-user > summary::before { background: var(--ch-dot-user); }
.trace-block.type-toolback > summary::before { background: var(--ch-dot-toolback); }
.trace-block.type-loop > summary::before { background: var(--ch-dot-model); }
.trace-block.type-bypass > summary::before { background: var(--ch-dot-bypass); }
.type-bypass { border-color: var(--ch-border); }
.type-bypass .block-pill, .bypass-purpose { background: var(--ch-muted-gradient); color: var(--ch-text-secondary); }
.bypass-purpose { display: inline-flex; min-height: 24px; align-items: center; overflow: hidden; padding: 0 var(--ch-space-2); border-radius: 4px; font-size: var(--ch-text-xs); font-weight: var(--ch-font-semibold); line-height: 1.4; white-space: nowrap; text-overflow: ellipsis; }
.bypass-details .region-head small { flex: 1; min-width: 0; overflow: hidden; color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); text-align: right; text-overflow: ellipsis; white-space: nowrap; }
.bypass-prompt, .bypass-content { max-height: 240px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.bypass-error { max-height: 240px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-danger-soft); color: var(--ch-danger-text); font-size: var(--ch-text-xs); line-height: 1.5; }
.type-loop .block-main { color: var(--ch-text-muted); font-size: var(--ch-text-xs); font-weight: 400; }
.block-pill { display: inline-flex; align-items: center; padding: var(--ch-space-1) var(--ch-space-2); border-radius: 4px; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); font-weight: var(--ch-font-semibold); line-height: 1.4; white-space: nowrap; }
.block-time { display: inline-flex; align-items: center; gap: var(--ch-space-1); color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); white-space: nowrap; }
.block-caret { flex-shrink: 0; width: 14px; height: 14px; stroke-width: 1.6; color: var(--ch-text-muted); transition: transform var(--ch-duration-fast) var(--ch-ease); }
.trace-block:not([open]) .block-caret { transform: rotate(-90deg); }
.block-main { display: block; overflow: hidden; margin-top: var(--ch-space-3); color: var(--ch-text); font-size: var(--ch-text-sm); font-weight: var(--ch-font-medium); line-height: 1.6; white-space: nowrap; text-overflow: ellipsis; }
.call-metrics { display: grid; gap: var(--ch-space-1); min-width: 0; margin-top: var(--ch-space-3); color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); line-height: 1.4; }
.call-metrics > span { display: inline-flex; align-items: center; white-space: nowrap; }
.call-model { gap: var(--ch-space-2); }
.call-usage { flex-wrap: wrap; gap: var(--ch-space-1) var(--ch-space-2); }
.call-status, .tool-status { display: inline-flex; align-items: center; padding: var(--ch-space-1); border-radius: 3px; font-size: 12px; font-weight: var(--ch-font-semibold); line-height: 1.4; white-space: nowrap; }
.status-success { padding: var(--ch-space-1) var(--ch-space-2); background: var(--ch-success-soft); color: var(--ch-success-text); }
.tool-status { padding: 0; border-radius: 0; background: transparent; font-size: var(--ch-text-xs); font-weight: 400; }
.tool-status.status-success { background: transparent; color: var(--ch-text-muted); }
.tool-status.status-error { background: transparent; color: var(--ch-danger-text); }
.tool-status.status-pending { background: transparent; color: var(--ch-info-text); }
.status-error { background: var(--ch-danger-soft); color: var(--ch-danger-text); }
.status-pending { background: var(--ch-info-soft); color: var(--ch-info-text); }
.user-detail { display: flex; flex-direction: column; gap: var(--ch-space-2); margin: 0 var(--ch-space-3); padding: var(--ch-space-3) 0; border-top: 1px solid var(--ch-border); }
.user-context-head { display: flex; align-items: center; gap: var(--ch-space-2); color: var(--ch-text-faint); font-size: var(--ch-text-xs); line-height: 1.4; }
.context-tabs.user-context-tabs { gap: var(--ch-space-2); }

.context-tabs.mono-tabs button { font-family: var(--ch-font-mono); }
.block-body-text, .msg-text, .part-text { margin: 0; max-height: 240px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
.context-tabs { display: flex; gap: var(--ch-space-2); }
.agent-tabs { flex-wrap: wrap; margin: 0 0 var(--ch-space-3); }
.context-tabs button { padding: var(--ch-space-1) var(--ch-space-2); border: 1px solid var(--ch-border); border-radius: 4px; background: var(--ch-surface); color: var(--ch-text-muted); font-size: var(--ch-text-xs); line-height: 1.4; cursor: pointer; }
.context-tabs button:hover { color: var(--ch-text-secondary); background: var(--ch-surface-2); }
.context-tabs button.active { border-color: transparent; background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); font-weight: var(--ch-font-semibold); }
.context-content { max-height: 160px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.user-detail .context-content { background: var(--ch-surface-2); }
.type-user .block-pill { background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); }
.type-user { border-color: var(--ch-border); background: var(--ch-surface); }
.type-user .block-main { color: var(--ch-text-muted); font-size: var(--ch-text-xs); font-weight: 400; }
.trace-block[open] .block-main { display: none; }
.type-user[open] .block-main { display: block; }
.type-toolback { border-color: var(--ch-border); background: var(--ch-surface); }
.type-toolback .block-pill { background: var(--ch-warning-soft); color: var(--ch-warning-text); }
.type-toolback .block-main { color: var(--ch-text-muted); font-size: var(--ch-text-xs); font-weight: 400; }
.type-toolback[open] .block-main { display: block; }
.type-loop { border-color: var(--ch-border); }
.type-loop .block-pill { background: color-mix(in srgb, var(--ch-info-soft) 65%, var(--ch-surface)); color: var(--ch-info-text); }
.call-details { margin: 0 var(--ch-space-3); padding: var(--ch-space-3) 0; border-top: 1px solid var(--ch-border); }
.toolback-rows { margin: 0 var(--ch-space-3) var(--ch-space-3); padding-top: var(--ch-space-3); border-top: 1px solid var(--ch-border); }
.toolback-list { overflow: hidden; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-btn); }
.toolback-row { font-size: var(--ch-text-xs); }
.toolback-row summary { display: flex; align-items: center; gap: var(--ch-space-2); padding: var(--ch-space-2); cursor: pointer; list-style: none; }
.toolback-row + .toolback-row { border-top: 1px solid var(--ch-border); }
.toolback-row .block-caret { margin-left: var(--ch-space-2); }
.toolback-row:not([open]) .block-caret { transform: rotate(-90deg); }
.toolback-row .tool-name { flex-shrink: 0; color: var(--ch-text-secondary); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); }
.toolback-row .tool-desc { flex: 1; min-width: 0; overflow: hidden; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); font-weight: 400; text-overflow: ellipsis; white-space: nowrap; }
.tool-result-meta { display: inline-flex; align-items: center; margin-left: auto; }
.toolback-row .tool-status { flex-shrink: 0; }
.toolback-row .tool-duration { flex-shrink: 0; color: var(--ch-text-muted); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); white-space: nowrap; }
.toolback-row .tool-duration::before { content: '·'; margin: 0 var(--ch-space-2); }
.toolback-row pre { max-height: 160px; margin: 0 var(--ch-space-2) var(--ch-space-2); overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
pre { margin: 0; font-family: var(--ch-font-mono); white-space: pre-wrap; word-break: break-word; }
.region + .region { margin-top: var(--ch-space-3); }
.region > * + * { margin-top: var(--ch-space-2); }
.region-head { display: flex; align-items: center; gap: var(--ch-space-2); }
.region-head strong { color: var(--ch-text-secondary); font-size: var(--ch-text-xs); font-weight: var(--ch-font-semibold); }
.region-head small { color: var(--ch-text-muted); font-size: var(--ch-text-xs); white-space: nowrap; }
.raw-toggle { display: inline-flex; align-items: center; gap: 2px; margin-left: auto; padding: 0; border: 0; background: transparent; color: var(--ch-text-faint); font-size: 11px; line-height: 1.4; cursor: pointer; }
.raw-toggle:hover, .raw-toggle.active { color: var(--ch-text-secondary); }
.raw-toggle:disabled { color: var(--ch-text-faint); cursor: not-allowed; }
.raw-json { max-height: 320px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.msg-list { overflow: hidden; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-btn); }
.msg-row + .msg-row { border-top: 1px solid var(--ch-border); }
.msg-row summary { display: flex; align-items: center; gap: var(--ch-space-2); padding: var(--ch-space-2); cursor: pointer; list-style: none; }
.msg-role { flex-shrink: 0; width: 56px; padding: 2px 0; border-radius: 4px; text-align: center; font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); line-height: 1.5; }
.role-user, .role-assistant, .role-system, .role-tool { background: var(--ch-surface-2); color: var(--ch-text-secondary); }
.msg-preview { flex: 1; min-width: 0; overflow: hidden; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); white-space: nowrap; text-overflow: ellipsis; }
.msg-detail { display: flex; flex-direction: column; gap: var(--ch-space-2); padding: 0 var(--ch-space-2) var(--ch-space-2); }
.msg-detail pre { max-height: 160px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.msg-detail .msg-text, .msg-detail pre { border-radius: 4px; }
.schema-list { overflow: hidden; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-btn); background: var(--ch-surface); }
.schema-list summary { display: flex; align-items: center; padding: var(--ch-space-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); cursor: pointer; list-style: none; }
.schema-list .block-caret { margin-left: auto; }
.schema-list:not([open]) .block-caret { transform: rotate(-90deg); }
.schema-list[open] summary { border-bottom: 1px solid var(--ch-border); }
.schema-row { display: flex; align-items: center; gap: var(--ch-space-2); min-width: 0; padding: var(--ch-space-2); }
.schema-row + .schema-row { border-top: 1px solid var(--ch-border); }
.schema-row code { flex-shrink: 0; padding: 2px var(--ch-space-1); border-radius: 4px; background: var(--ch-surface-2); color: var(--ch-text-secondary); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); }
.schema-row span { min-width: 0; overflow: hidden; color: var(--ch-text-muted); font-size: var(--ch-text-xs); white-space: nowrap; text-overflow: ellipsis; }
.part-list { overflow: hidden; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-btn); }
.part-row + .part-row { border-top: 1px solid var(--ch-border); }
.part-row summary { display: flex; align-items: center; gap: var(--ch-space-2); padding: var(--ch-space-2); cursor: pointer; list-style: none; }
.part-row .block-caret { margin-left: auto; }
.part-row:not([open]) .block-caret { transform: rotate(-90deg); }
.part-row[open] .part-desc, .msg-row[open] .msg-preview, .toolback-row[open] .tool-desc { display: none; }
.part-tag { flex-shrink: 0; width: 56px; padding: 2px 0; border-radius: 4px; text-align: center; font-size: var(--ch-text-xs); line-height: 1.5; }
.tag-thinking, .tag-content, .tag-call { background: var(--ch-surface-2); color: var(--ch-text-secondary); }
.part-tool-name { flex-shrink: 0; color: var(--ch-text-secondary); font-family: var(--ch-font-mono); font-size: var(--ch-text-xs); }
.part-desc { flex: 1; min-width: 0; overflow: hidden; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); white-space: nowrap; text-overflow: ellipsis; }
.part-body { display: flex; flex-direction: column; gap: var(--ch-space-2); padding: 0 var(--ch-space-2) var(--ch-space-2); }
.part-code { max-height: 160px; overflow: auto; padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.think-seg { padding: var(--ch-space-2); border-radius: var(--ch-radius-btn); background: var(--ch-surface-2); }
.think-seg pre { max-height: 144px; margin: 0; overflow: auto; color: var(--ch-text-secondary); font-size: var(--ch-text-xs); line-height: 1.5; }
.pending-hint, .empty-line { margin: 0; color: var(--ch-text-muted); font-size: var(--ch-text-xs); }
@media (max-width: 780px) { .console-header { padding: var(--ch-space-3) var(--ch-space-3) 0; } .trace-body { padding: var(--ch-space-3) var(--ch-space-2) var(--ch-space-4); } }
</style>
