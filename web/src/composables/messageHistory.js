// 助手历史消息规整：后端拉回的多轮助手消息合并成单气泡，
// 与流式一气泡一回合对齐。挂起轮（无正文但有工具）保留作确认卡宿主，续写轮合并进同气泡。

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
  const text = (msg.content || '').trim()
  return {
    role: 'assistant',
    content: msg.content || '',
    thinking: { state: 'idle' },
    tools: { state: 'idle', items: toolItems.map(mapToolItem) },
    created_at: msg.created_at ?? Date.now() / 1000,
    id: msg.id || null,
    // 无正文但有工具：挂起轮，作确认卡宿主，resume 据此复用气泡续写
    suspended: !text && toolItems.length > 0,
  }
}

export function mergeAssistantHistory(raw) {
  // 同一回合的助手轮次正文合并进一个气泡，挂起轮（无正文但有工具）保留作宿主
  const result = []
  let segBubble = null

  for (const m of raw) {
    if (m.role !== 'assistant') {
      result.push({ role: m.role, content: m.content, created_at: m.created_at ?? Date.now() / 1000 })
      segBubble = null
      continue
    }
    const hasContent = !!(m.content && m.content.trim())
    const hasTools = Array.isArray(m.tools) && m.tools.length > 0
    if (segBubble) {
      if (hasContent) {
        segBubble.content += (segBubble.content ? '\n\n' : '') + m.content
        segBubble.suspended = false
      }
      if (hasTools) segBubble.tools.items.push(...m.tools.map(mapToolItem))
    } else if (hasContent || hasTools) {
      segBubble = normalizeAssistant({ role: 'assistant', content: m.content, tools: m.tools, id: m.id })
      result.push(segBubble)
    }
  }
  return result
}
