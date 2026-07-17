// 助手历史消息规整：后端拉回的多轮助手消息合并成单气泡，
// 与流式一气泡一回合对齐。纯函数无依赖。

export function mapToolItem(it) {
  return {
    name: it.name,
    arguments: it.arguments || {},
    duration_ms: it.duration_ms ?? null,
    content: it.content || '',
    display: it.display || it.name,
  }
}

export function normalizeAssistant(msg) {
  const toolItems = Array.isArray(msg.tools) ? msg.tools : []
  return {
    role: 'assistant',
    content: msg.content || '',
    thinking: { state: 'idle' },
    tools: { state: 'idle', items: toolItems.map(mapToolItem) },
    created_at: msg.created_at ?? Date.now() / 1000,
  }
}

export function mergeAssistantHistory(raw) {
  // 同一回合的助手轮次合并进一个气泡
  const result = []
  let pendingTools = []
  let segBubble = null

  const flushPending = () => {
    if (!pendingTools.length) return
    result.push(normalizeAssistant({ role: 'assistant', content: '', tools: pendingTools }))
    pendingTools = []
  }

  for (const m of raw) {
    if (m.role !== 'assistant') {
      flushPending()
      result.push({ role: m.role, content: m.content, created_at: m.created_at ?? Date.now() / 1000 })
      segBubble = null
      continue
    }
    const tools = Array.isArray(m.tools) ? m.tools : []
    const hasContent = !!(m.content && m.content.trim())
    if (segBubble) {
      for (const it of tools) segBubble.tools.items.push(mapToolItem(it))
      if (hasContent) segBubble.content += '\n\n' + m.content
    } else if (hasContent) {
      segBubble = normalizeAssistant({ role: 'assistant', content: m.content, tools: [...pendingTools, ...tools] })
      result.push(segBubble)
      pendingTools = []
    } else {
      pendingTools.push(...tools)
    }
  }
  flushPending()
  return result
}
