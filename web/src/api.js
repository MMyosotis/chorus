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

export function confirmIntent(id, onEvent) {
  return streamSessionEventSource(`${BASE}/${id}/intent:confirm`, { method: 'POST' }, onEvent)
}

export function reopenIntent(id, onEvent) {
  return streamSessionEventSource(`${BASE}/${id}/intent:reopen`, { method: 'POST' }, onEvent)
}

export function chooseOption(id, body, onEvent) {
  return streamSessionEventSource(`${BASE}/${id}/option:choose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, onEvent)
}

export async function fetchSessionView(id) {
  const res = await fetch(`${BASE}/${id}/view`)
  if (res.status === 404) {
    const err = new Error('session not found')
    err.status = 404
    throw err
  }
  if (!res.ok) throw new Error(`session view failed: ${res.status}`)
  return res.json()
}

export function resumeSession(id, onEvent) {
  return streamSessionEventSource(`${BASE}/${id}/resume`, { method: 'POST' }, onEvent)
}

export function streamChat(id, message, onEvent) {
  return streamSessionEventSource(`${BASE}/${id}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  }, onEvent)
}

export async function suggestMessages(id) {
  const res = await fetch(`${BASE}/${id}/suggestions`, { method: 'POST' })
  if (res.status === 404) {
    const err = new Error('session not found')
    err.status = 404
    throw err
  }
  if (!res.ok) throw new Error(`suggestions failed: ${res.status}`)
  const data = await res.json()
  return data.suggestions || []
}

function streamSessionEventSource(url, options, onEvent) {
  const ctrl = new AbortController()
  const done = (async () => {
    let response
    try {
      response = await fetch(url, {
        ...options,
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

const TASKS_BASE = '/api/tasks'

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
    body: JSON.stringify({ feedback: feedback || '' }),
  })
  if (!res.ok) {
    const err = new Error(`retry failed: ${res.status}`)
    err.status = res.status
    try { err.detail = (await res.json()).detail } catch { err.detail = '' }
    throw err
  }
  return res.json()
}

export async function editTask(taskId, payload) {
  const res = await fetch(`${TASKS_BASE}/${encodeURIComponent(taskId)}/edit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = new Error(`edit failed: ${res.status}`)
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

const SKILLS_BASE = '/api/skills'

export async function listSkills() {
  const res = await fetch(SKILLS_BASE)
  if (!res.ok) throw new Error(`listSkills failed: ${res.status}`)
  const data = await res.json()
  return data.skills || []
}

export async function getSkillFile(name, path) {
  const res = await fetch(`${SKILLS_BASE}/${encodeURIComponent(name)}/files/${path}`)
  if (!res.ok) {
    const err = new Error(`getSkillFile failed: ${res.status}`)
    err.status = res.status
    throw err
  }
  return res.text()
}

const MEMORY_BASE = '/api/memory'

export async function listMemories() {
  const res = await fetch(MEMORY_BASE)
  if (!res.ok) throw new Error(`listMemories failed: ${res.status}`)
  const data = await res.json()
  return data.memories || []
}

export async function createMemory(body) {
  const res = await fetch(MEMORY_BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`createMemory failed: ${res.status}`)
  return res.json()
}

export async function updateMemory(id, body) {
  const res = await fetch(`${MEMORY_BASE}/${encodeURIComponent(id)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`updateMemory failed: ${res.status}`)
  return res.json()
}

export async function deleteMemory(id) {
  const res = await fetch(`${MEMORY_BASE}/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(`deleteMemory failed: ${res.status}`)
  return res.json()
}
