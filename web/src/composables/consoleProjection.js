export const BYPASS_PURPOSE_LABELS = {
  title: '生成标题',
  summary: '历史摘要',
  suggestion: '输入建议',
  aside: '任务旁白',
  memory_extract: '记忆提取',
  memory_merge: '记忆整理',
  memory_recall: '记忆召回',
}

const INJECTION_LABELS = {
  memory_summary: '记忆摘要',
  available_skills: '可用技能',
  recalled_memories: '记忆召回',
  intent_state: '意图状态',
  role: '角色',
  step_note: '本步交待',
  intent: '创作意图',
  base_card: '底稿',
  dependency_artifacts: '前置产物',
  prior_artifact: '上轮产物',
  user_feedback: '用户反馈',
  recent_chat: '近期对话',
  error: '错误',
}
const INJECTION_PATTERN = new RegExp(
  `<(${Object.keys(INJECTION_LABELS).join('|')})>[\\s\\S]*?<\\/\\1>`,
  'g',
)
const TOOL_CONTENT_PATTERN = /^<(tool_result|error)>\s*([\s\S]*?)\s*<\/\1>$/

export function parseTaggedContent(raw) {
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

export function displayToolContent(raw) {
  if (typeof raw !== 'string') return raw
  return raw.replace(TOOL_CONTENT_PATTERN, '$2')
}

export function messageText(message) {
  return typeof message.content === 'string' ? message.content : shortJson(message.content)
}

export function toolCallArguments(toolCall) {
  const raw = toolCall?.function?.arguments
  if (typeof raw !== 'string') return ''
  return parseMaybeJson(raw) || raw
}

export function buildModelCalls(traces) {
  const byMessage = new Map()
  const ordered = [...traces].sort((a, b) => (a.created_at || 0) - (b.created_at || 0))

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
}

export function buildBypassCalls(traces) {
  return traces
    .filter((trace) => trace.phase === 'bypass_call')
    .map((trace) => ({
      key: `bypass:${trace.created_at}:${trace.source || 'supervisor'}:${trace.task_id || ''}:${trace.payload?.purpose || ''}`,
      created_at: trace.created_at || 0,
      source: trace.source || 'supervisor',
      task_id: trace.task_id || null,
      payload: trace.payload || {},
    }))
    .sort((a, b) => a.created_at - b.created_at)
}

export function buildUserInputs(traces) {
  return traces
    .filter((trace) => trace.phase === 'user_input')
    .map((trace) => {
      const key = trace.message_id || `user:${trace.created_at}`
      return {
        created_at: trace.created_at || 0,
        source: trace.source || 'supervisor',
        message: { key, ...parseTaggedContent(trace.payload?.content || '') },
      }
    })
    .sort((a, b) => a.created_at - b.created_at)
}

export function buildTimeline(calls, bypassCalls, userInputs, roleFor) {
  const events = []
  for (const call of calls) events.push({ at: call.created_at || 0, call })
  for (const item of bypassCalls) events.push({ at: item.created_at, bypass: item })
  for (const item of userInputs) events.push({ at: item.created_at, user: item })
  events.sort((a, b) => a.at - b.at || (a.call ? -1 : 1))

  const result = []
  const pendingBypass = []
  let previous = null
  let currentTurn = 0
  let explicitUserPending = false

  for (const event of events) {
    if (event.user) {
      currentTurn += 1
      explicitUserPending = true
      result.push({ kind: 'user', created_at: event.at, message: event.user.message, turn: currentTurn })
      continue
    }

    if (event.bypass) {
      const item = { kind: 'bypass', created_at: event.at, item: event.bypass, turn: currentTurn }
      if (currentTurn) result.push(item)
      else pendingBypass.push(item)
      continue
    }

    const call = event.call
    const messages = call.request?.payload?.messages || []
    const continuesAfterTool = messages.at(-1)?.role === 'tool'
    if (continuesAfterTool && previous) {
      const tools = resultTools(previous)
      const totalMs = tools.reduce((sum, tool) => sum + (tool.duration_ms || 0), 0)
      if (tools.length) result.push({ kind: 'toolback', created_at: call.created_at, tools, turn: currentTurn, total_ms: totalMs })
    } else {
      if (!explicitUserPending) {
        currentTurn += 1
        const user = userInputFor(call)
        if (user) result.push({ kind: 'user', created_at: call.created_at, message: user, turn: currentTurn })
      }
      for (const item of pendingBypass) result.push({ ...item, turn: currentTurn })
      pendingBypass.length = 0
    }
    explicitUserPending = false

    result.push({ kind: 'loop', created_at: call.created_at, role: roleFor(call.source, call.task_id), call, turn: currentTurn })
    previous = call
  }
  return [...result, ...pendingBypass]
}

export function buildSessionStats(calls, bypassCalls, turnCount) {
  if (!calls.length && !bypassCalls.length) return null
  const first = Math.min(
    calls.length ? calls[0].created_at : Infinity,
    bypassCalls.length ? bypassCalls[0].created_at : Infinity,
  )
  let lastEnd = first
  let toolCount = 0
  let costCny = null
  let inputTokens = 0
  let outputTokens = 0
  let totalTokens = 0
  for (const call of calls) {
    lastEnd = Math.max(lastEnd, call.created_at, call.response?.created_at || 0)
    for (const trace of call.toolResults.values()) {
      toolCount += 1
      lastEnd = Math.max(lastEnd, trace.created_at || 0)
    }
    const payload = call.response?.payload
    if (payload?.cost_cny != null) costCny = (costCny ?? 0) + payload.cost_cny
    if (payload?.usage) {
      inputTokens += payload.usage.input_tokens || 0
      outputTokens += payload.usage.output_tokens || 0
      totalTokens += payload.usage.total_tokens ?? ((payload.usage.input_tokens || 0) + (payload.usage.output_tokens || 0))
    }
  }
  for (const bypass of bypassCalls) {
    const payload = bypass.payload
    lastEnd = Math.max(lastEnd, bypass.created_at)
    if (payload?.cost_cny != null) costCny = (costCny ?? 0) + payload.cost_cny
    if (payload?.usage) {
      inputTokens += payload.usage.input_tokens || 0
      outputTokens += payload.usage.output_tokens || 0
      totalTokens += payload.usage.total_tokens ?? ((payload.usage.input_tokens || 0) + (payload.usage.output_tokens || 0))
    }
  }
  return {
    durationMs: (lastEnd - first) * 1000,
    turnCount,
    callCount: calls.length,
    bypassCount: bypassCalls.length,
    toolCount,
    costCny,
    inputTokens,
    outputTokens,
    totalTokens,
  }
}

export function resultTools(call) {
  return toolsFor(call)
    .filter((tool) => tool.result)
    .map((tool) => {
      const content = displayToolContent(tool.result.payload?.content)
      return {
        id: tool.id,
        name: tool.name,
        display: tool.display,
        duration_ms: tool.result.payload?.duration_ms,
        status: tool.result.payload?.status || 'success',
        content,
        pretty: parseMaybeJson(content),
      }
    })
}

export function toolsFor(call) {
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

export function userInputFor(call) {
  const messages = call.request?.payload?.messages || []
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]
    if (message.role !== 'user') continue
    const raw = typeof message.content === 'string' ? message.content : shortJson(message.content)
    if (!raw) return null
    const parsed = parseTaggedContent(raw)
    if (!parsed.text) return null
    return { key: `${index}:${raw}`, text: parsed.text, injections: parsed.injections }
  }
  return null
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

export function shortJson(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value || '')
  }
}
