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

function waitsForIntentConfirmation(toolItems) {
  return toolItems.some((item) =>
    item.name === 'update_intent_state' &&
    item.arguments?.intent_status === 'ready_to_confirm'
  )
}

function waitsForOptionSelection(toolItems) {
  // present_options 参数错误时会返回 Reply 并进入模型重试，不能把它误当成
  // 已成功挂起的选项卡宿主，否则会渲染一个无正文、无卡片的空气泡。
  return toolItems.some((item) => {
    if (item.name !== 'present_options') return false
    const args = item.arguments || {}
    return (
      typeof args.question === 'string' &&
      args.question.trim() !== '' &&
      Array.isArray(args.options) &&
      args.options.length >= 3 &&
      args.options.every((option) =>
        typeof option?.label === 'string' && option.label.trim() !== '' &&
        typeof option?.description === 'string' && option.description.trim() !== ''
      )
    )
  })
}

function hostsHilCard(toolItems) {
  return waitsForIntentConfirmation(toolItems) || waitsForOptionSelection(toolItems)
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
    // 一条展示气泡可以承载同一交互链路里的多条持久化消息。
    // 保留所有来源 ID，供 HIL 留档卡定位到这个气泡。
    messageIds: msg.id ? [msg.id] : [],
    // 等待用户确认或选择的轮次即使已有正文，也须在历史重载后保留续写标记；
    // 否则续写会另起一个无正文气泡。
    suspended: (!text && toolItems.length > 0) || hostsHilCard(toolItems),
  }
}

export function mergeAssistantHistory(raw) {
  // 一次用户交互中的所有助手轮次合并进一个气泡；HIL 挂起/续跑是同一交互链路，
  // 不能把它当成新的气泡边界。
  const result = []
  let segBubble = null

  for (const m of raw) {
    if (m.role !== 'assistant') {
      result.push({ id: m.id || null, role: m.role, content: m.content, created_at: m.created_at ?? Date.now() / 1000 })
      segBubble = null
      continue
    }
    const hasContent = !!(m.content && m.content.trim())
    const hasTools = Array.isArray(m.tools) && m.tools.length > 0
    const hilHost = hostsHilCard(m.tools || [])
    if (segBubble) {
      if (hasContent) {
        segBubble.content += (segBubble.content ? '\n\n' : '') + m.content
      }
      if (hasTools) segBubble.tools.items.push(...m.tools.map(mapToolItem))
      if (m.id && !segBubble.messageIds.includes(m.id)) segBubble.messageIds.push(m.id)
      // 最近一轮若挂起，后续 resume 必须复用这一气泡；普通续写才解除挂起状态。
      segBubble.suspended = hilHost || (!hasContent && hasTools)
    } else if (hasContent || hasTools) {
      segBubble = normalizeAssistant({ role: 'assistant', content: m.content, tools: m.tools, id: m.id })
      result.push(segBubble)
    }
  }
  return result
}

export function containsMessageId(message, messageId) {
  return message.id === messageId || message.messageIds?.includes(messageId)
}
