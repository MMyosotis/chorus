// 前端 API 抽离：所有 fetch 集中到这里
const BASE = '/api/conversations'
const DEBUG_BASE = '/api/debug'

export async function listConversations() {
  const res = await fetch(BASE)
  if (!res.ok) throw new Error(`list failed: ${res.status}`)
  const data = await res.json()
  return data.conversations || []
}

export async function createConversation(title) {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(title ? { title } : {}),
  })
  if (!res.ok) throw new Error(`create failed: ${res.status}`)
  return res.json()
}

export async function deleteConversation(id) {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`delete failed: ${res.status}`)
  return res.json()
}

export async function renameConversation(id, title) {
  const res = await fetch(`${BASE}/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })
  if (!res.ok) throw new Error(`rename failed: ${res.status}`)
  return res.json()
}

export async function fetchMessages(id) {
  const res = await fetch(`${BASE}/${id}/messages`)
  if (res.status === 404) {
    const err = new Error('conversation not found')
    err.status = 404
    throw err
  }
  if (!res.ok) throw new Error(`messages failed: ${res.status}`)
  const data = await res.json()
  return data.messages || []
}

/**
 * 流式聊天：内部封装 fetch + ReadableStream 解析。
 * onEvent 收到每个 SSE 事件 dict。
 * 返回 { done } —— done 是 Promise，流结束后 resolve。
 */
export function streamChat(id, message, onEvent) {
  const ctrl = new AbortController()
  const done = (async () => {
    let response
    try {
      response = await fetch(`${BASE}/${id}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
        signal: ctrl.signal,
      })
    } catch (e) {
      onEvent({ type: 'error', content: e.message })
      return
    }

    if (!response.ok) {
      let detail = `${response.status}`
      try {
        const data = await response.json()
        detail = data.detail || detail
      } catch {}
      onEvent({ type: 'error', content: detail })
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done: rdone, value } = await reader.read()
        if (rdone) break
        buffer += decoder.decode(value, { stream: true })

        const parts = buffer.split('\n\n')
        buffer = parts.pop()

        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data: ')) continue
          try {
            const payload = JSON.parse(line.slice(6))
            onEvent(payload)
          } catch {
            // 忽略解析失败
          }
        }
      }
    } catch (e) {
      onEvent({ type: 'error', content: e.message })
    }
  })()

  return { abort: () => ctrl.abort(), done }
}

export async function getTestMode() {
  const res = await fetch(`${DEBUG_BASE}/test-mode`)
  if (!res.ok) throw new Error(`getTestMode failed: ${res.status}`)
  const data = await res.json()
  return !!data.enabled
}

export async function setTestMode(enabled) {
  const res = await fetch(`${DEBUG_BASE}/test-mode`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: !!enabled }),
  })
  if (!res.ok) throw new Error(`setTestMode failed: ${res.status}`)
  const data = await res.json()
  return !!data.enabled
}

export async function getInitialTestMode() {
  const res = await fetch(`${DEBUG_BASE}/test-mode/initial`)
  if (!res.ok) throw new Error(`getInitialTestMode failed: ${res.status}`)
  const data = await res.json()
  return !!data.enabled
}
