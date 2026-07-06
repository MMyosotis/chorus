// trace 单例 store：跨组件共享，按会话聚合 trace 事件。
// 数据全部来自后端 SQLite——进会话拉历史，流式时追加 SSE 推送的事件。

import { reactive } from 'vue'

import { fetchTraces } from '../api.js'

const tracesBySession = reactive({})
const loadedSessions = new Set()

export function useTraceStore() {
  return {
    tracesBySession,

    addTrace(sessionId, item) {
      if (!sessionId) return
      const list = tracesBySession[sessionId] || (tracesBySession[sessionId] = [])
      list.push(item)
    },

    clearTrace(sessionId) {
      if (!sessionId) return
      tracesBySession[sessionId] = []
      loadedSessions.delete(sessionId)
    },

    getTraces(sessionId) {
      return tracesBySession[sessionId] || []
    },

    async loadFromServer(sessionId) {
      if (!sessionId || loadedSessions.has(sessionId)) return
      try {
        const list = await fetchTraces(sessionId)
        tracesBySession[sessionId] = Array.isArray(list) ? list : []
        loadedSessions.add(sessionId)
      } catch {
        tracesBySession[sessionId] = tracesBySession[sessionId] || []
      }
    },

    async pollFromServer(sessionId) {
      // 重复拉取并按时间与来源去重合并
      if (!sessionId) return
      try {
        const list = await fetchTraces(sessionId)
        const cur = tracesBySession[sessionId] || (tracesBySession[sessionId] = [])
        const seen = new Set(cur.map((t) => `${t.created_at}|${t.phase}|${t.message_id || ''}|${t.task_id || ''}`))
        for (const t of list) {
          const key = `${t.created_at}|${t.phase}|${t.message_id || ''}|${t.task_id || ''}`
          if (!seen.has(key)) {
            cur.push(t)
            seen.add(key)
          }
        }
        loadedSessions.add(sessionId)
      } catch {
        // 忽略，下轮重试
      }
    },
  }
}
