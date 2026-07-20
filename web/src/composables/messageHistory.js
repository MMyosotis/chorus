// 助手历史消息规整：后端拉回的多轮助手消息合并成单气泡，
// 与流式一气泡一回合对齐。纯工具轮（无正文）不独立成泡，直接丢弃。

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
  // 同一回合的助手轮次正文合并进一个气泡，纯工具轮（无正文）跳过
  const result = []
  let segBubble = null

  for (const m of raw) {
    if (m.role !== 'assistant') {
      result.push({ role: m.role, content: m.content, created_at: m.created_at ?? Date.now() / 1000 })
      segBubble = null
      continue
    }
    const hasContent = !!(m.content && m.content.trim())
    if (segBubble) {
      if (hasContent) segBubble.content += '\n\n' + m.content
    } else if (hasContent) {
      segBubble = normalizeAssistant({ role: 'assistant', content: m.content })
      result.push(segBubble)
    }
  }
  return result
}
