// trace store：单例 reactive，模块级共享给 App.vue 和 ConsolePanel.vue
//
// 数据形态：tracesByConv = { [convId]: TraceItem[] }
// TraceItem 直接来自 SSE 事件（type === 'trace' / 'tool_call' / 'tool_result'），保留原 payload。
//
// 持久化策略：
// - localStorage key: little-kitty:traces:v1
// - 节流写入（500ms debounce），避免高频 trace 流入时频繁同步
// - 每会话最多保留 MAX_PER_CONV 条，环形丢弃最早
// - 持久化时对 >256KB 的字符串字段降维（替换为占位符），内存版仍完整
// - 写入抛 QuotaExceededError 时按 LRU 丢弃最旧会话直到能写入

import { reactive } from 'vue'

const STORAGE_KEY = 'little-kitty:traces:v1'
const MAX_PER_CONV = 50
const PERSIST_DEBOUNCE_MS = 500
const MAX_PERSIST_FIELD_BYTES = 256 * 1024

function loadFromStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

// 递归遍历 obj，把超长字符串替换为占位符，避免撑爆 localStorage 配额。
function shrinkForPersist(obj) {
  if (typeof obj === 'string') {
    if (obj.length > MAX_PERSIST_FIELD_BYTES) {
      return {
        __truncated: true,
        size: obj.length,
        head: obj.slice(0, 200),
      }
    }
    return obj
  }
  if (Array.isArray(obj)) return obj.map(shrinkForPersist)
  if (obj && typeof obj === 'object') {
    const out = {}
    for (const [k, v] of Object.entries(obj)) out[k] = shrinkForPersist(v)
    return out
  }
  return obj
}

const tracesByConv = reactive(loadFromStorage())
let persistTimer = null

function persistNow() {
  try {
    const compact = {}
    for (const [convId, list] of Object.entries(tracesByConv)) {
      compact[convId] = list.map(shrinkForPersist)
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(compact))
  } catch (e) {
    if (e && (e.name === 'QuotaExceededError' || e.code === 22)) {
      // 按会话 LRU 丢弃：先按最近一条 ts 排序，丢最旧的，直到写入成功
      const entries = Object.entries(tracesByConv)
        .map(([id, list]) => [id, list, list.length ? list[list.length - 1].ts || 0 : 0])
        .sort((a, b) => a[2] - b[2])
      while (entries.length > 0) {
        const [oldestId] = entries.shift()
        delete tracesByConv[oldestId]
        try {
          const compact = {}
          for (const [id, list] of Object.entries(tracesByConv)) {
            compact[id] = list.map(shrinkForPersist)
          }
          localStorage.setItem(STORAGE_KEY, JSON.stringify(compact))
          return
        } catch {
          // 继续丢
        }
      }
      // 全丢光还不行就放弃
      try {
        localStorage.removeItem(STORAGE_KEY)
      } catch {}
    } else {
      // 其他错误忽略，下次再试
      console.warn('trace persist failed', e)
    }
  }
}

function schedulePersist() {
  if (persistTimer) return
  persistTimer = setTimeout(() => {
    persistTimer = null
    persistNow()
  }, PERSIST_DEBOUNCE_MS)
}

export function useTraceStore() {
  return {
    tracesByConv,

    addTrace(convId, item) {
      if (!convId) return
      const list = tracesByConv[convId] || (tracesByConv[convId] = [])
      list.push(item)
      if (list.length > MAX_PER_CONV) {
        list.splice(0, list.length - MAX_PER_CONV)
      }
      schedulePersist()
    },

    clearTrace(convId) {
      if (!convId) return
      tracesByConv[convId] = []
      schedulePersist()
    },

    getTraces(convId) {
      return tracesByConv[convId] || []
    },
  }
}
