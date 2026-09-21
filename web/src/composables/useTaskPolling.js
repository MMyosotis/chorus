// 每会话视图轮询：subagent/scheduler 后台只写库不连 SSE，前端定时拉会话视图驱动团队栏与卡片。
// 任务图始终同步；流式时气泡由 SSE 推进，跳过整体套用。全任务终态即自停。

import { reactive, ref } from 'vue'

import { fetchSessionView } from '../api.js'

const POLL_INTERVAL = 1500

const graphBySession = reactive({})
const pollingSession = ref(null)
let timer = null
let isStreamingFn = () => false
let onViewFn = () => Promise.resolve()
let lastErrorSignature = null

export function useTaskPolling() {
  return {
    graphBySession,
    pollingSession,

    configure({ isStreaming, onView }) {
      isStreamingFn = isStreaming || isStreamingFn
      onViewFn = onView || onViewFn
    },

    getGraph(sessionId) {
      return graphBySession[sessionId] || null
    },

    start(sessionId) {
      if (!sessionId) return Promise.resolve()
      // 切到新会话：停旧轮询
      if (pollingSession.value !== sessionId) {
        stopInternal()
        pollingSession.value = sessionId
      }
      if (timer) return Promise.resolve() // 已在跑
      const firstTick = tick() // 立即跑一次
      timer = setInterval(tick, POLL_INTERVAL)
      return firstTick
    },

    stop() {
      stopInternal()
      pollingSession.value = null
    },

    // 确认/重跑后立即拉一次视图，不等下一轮周期，避免旧状态多亮一个轮询间隔
    refresh(sessionId) {
      if (pollingSession.value === sessionId && timer) {
        tick()
        return
      }
      this.start(sessionId)
    },
  }
}

function stopInternal() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

async function tick() {
  const sid = pollingSession.value
  if (!sid) return
  try {
    const view = await fetchSessionView(sid)
    graphBySession[sid] = view.graph
    lastErrorSignature = null
    if (!isStreamingFn(sid)) {
      await onViewFn(sid, view)
    }
    // 空闲即自停（含启动时就无活跃任务的会话）
    if (!view.graph.active) {
      stopInternal()
      pollingSession.value = null
    }
  } catch (error) {
    // 网络瞬时失败静默重试；后端错误去重暴露，不再无声吞掉
    const message = error?.message || ''
    if (!/failed: \d{3}/i.test(message)) return
    const signature = `${sid}:${message}`
    if (lastErrorSignature === signature) return
    lastErrorSignature = signature
    console.error('[task polling]', message)
  }
}
