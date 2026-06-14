// trace store：单例 reactive，模块级共享给 App.vue 和 ConsolePanel.vue
//
// 数据形态：tracesByConv = { [convId]: TraceItem[] }
// TraceItem 是后端 SSE/REST 返回的 trace 事件原文（含 phase / iteration / message_id / ts / payload）。
//
// 数据来源：完全来自后端 SQLite。
// - 进入会话或刷新页面时调 loadFromServer(convId) 拉历史 trace 灌进 store
// - 流式期间收到 SSE 'trace' 事件时由 App.vue 调 addTrace 追加（与库内一致，后端先写库再 yield）

import { reactive } from 'vue'

import { fetchTraces } from '../api.js'

const tracesByConv = reactive({})
// 已经从后端拉过的会话集合，避免每次切换重复拉取
const loadedConvs = new Set()

export function useTraceStore() {
  return {
    tracesByConv,

    addTrace(convId, item) {
      if (!convId) return
      const list = tracesByConv[convId] || (tracesByConv[convId] = [])
      list.push(item)
    },

    clearTrace(convId) {
      if (!convId) return
      tracesByConv[convId] = []
      loadedConvs.delete(convId)
    },

    getTraces(convId) {
      return tracesByConv[convId] || []
    },

    async loadFromServer(convId) {
      if (!convId || loadedConvs.has(convId)) return
      try {
        const list = await fetchTraces(convId)
        tracesByConv[convId] = Array.isArray(list) ? list : []
        loadedConvs.add(convId)
      } catch {
        tracesByConv[convId] = tracesByConv[convId] || []
      }
    },
  }
}
