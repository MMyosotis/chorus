// trace 视图单例 store：按会话缓存后端成品视图，控制台打开时整表拉取。

import { reactive } from 'vue'

import { fetchTraceView } from '../api.js'

const viewsBySession = reactive({})

export function useTraceStore() {
  return {
    viewsBySession,

    getView(sessionId) {
      return viewsBySession[sessionId] || null
    },

    async refresh(sessionId, agentKey) {
      if (!sessionId) return
      try {
        viewsBySession[sessionId] = await fetchTraceView(sessionId, agentKey)
      } catch {
        // 忽略，下轮重试
      }
    },
  }
}
