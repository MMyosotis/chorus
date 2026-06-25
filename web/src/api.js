// 前端 API 抽离：所有 fetch 集中到这里
const BASE = '/api/sessions'
const DEBUG_BASE = '/api/debug'
const SETTINGS_BASE = '/api/settings'

export async function listSessions() {
  const res = await fetch(BASE)
  if (!res.ok) throw new Error(`list failed: ${res.status}`)
  const data = await res.json()
  return data.sessions || []
}

export async function createSession(title) {
  const res = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(title ? { title } : {}),
  })
  if (!res.ok) throw new Error(`create failed: ${res.status}`)
  return res.json()
}

export async function deleteSession(id) {
  const res = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`delete failed: ${res.status}`)
  return res.json()
}

export async function renameSession(id, title) {
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
    const err = new Error('session not found')
    err.status = 404
    throw err
  }
  if (!res.ok) throw new Error(`messages failed: ${res.status}`)
  const data = await res.json()
  return data.messages || []
}

export async function fetchTraces(id) {
  const res = await fetch(`${BASE}/${id}/traces`)
  if (res.status === 404) {
    const err = new Error('session not found')
    err.status = 404
    throw err
  }
  if (!res.ok) throw new Error(`traces failed: ${res.status}`)
  const data = await res.json()
  return data.traces || []
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

// —— 输入框下方模型选项栏 ——
export async function getModelLists() {
  const res = await fetch(`${SETTINGS_BASE}/models`)
  if (!res.ok) throw new Error(`getModelLists failed: ${res.status}`)
  return res.json()
}

export async function getOptions() {
  const res = await fetch(`${SETTINGS_BASE}/options`)
  if (!res.ok) throw new Error(`getOptions failed: ${res.status}`)
  return res.json()
}

export async function setOptions(patch) {
  const res = await fetch(`${SETTINGS_BASE}/options`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) throw new Error(`setOptions failed: ${res.status}`)
  return res.json()
}

// —— 任务图 / HIL（多智能体创作）——
const TASKS_BASE = '/api/tasks'

export async function getTaskGraph(sessionId) {
  const res = await fetch(`${TASKS_BASE}?session_id=${encodeURIComponent(sessionId)}`)
  if (!res.ok) throw new Error(`getTaskGraph failed: ${res.status}`)
  return res.json()
}

export async function getTaskSteps(taskId) {
  const res = await fetch(`${TASKS_BASE}/${encodeURIComponent(taskId)}/steps`)
  if (res.status === 404) {
    const err = new Error('task not found')
    err.status = 404
    throw err
  }
  if (!res.ok) throw new Error(`getTaskSteps failed: ${res.status}`)
  const data = await res.json()
  return data.steps || []
}

export async function confirmTask(taskId, selected) {
  const res = await fetch(`${TASKS_BASE}/${encodeURIComponent(taskId)}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(selected == null ? {} : { selected }),
  })
  if (!res.ok) {
    const err = new Error(`confirm failed: ${res.status}`)
    err.status = res.status
    try { err.detail = (await res.json()).detail } catch { err.detail = '' }
    throw err
  }
  return res.json()
}

export async function retryTask(taskId, feedback) {
  const res = await fetch(`${TASKS_BASE}/${encodeURIComponent(taskId)}/retry`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ feedback: feedback || {} }),
  })
  if (!res.ok) {
    const err = new Error(`retry failed: ${res.status}`)
    err.status = res.status
    try { err.detail = (await res.json()).detail } catch { err.detail = '' }
    throw err
  }
  return res.json()
}

export async function cancelPipeline(sessionId) {
  const res = await fetch(`${BASE}/${encodeURIComponent(sessionId)}/pipeline:cancel`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = new Error(`cancel failed: ${res.status}`)
    err.status = res.status
    try { err.detail = (await res.json()).detail } catch { err.detail = '' }
    throw err
  }
  return res.json()
}

