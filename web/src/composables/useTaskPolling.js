// 每会话任务图轮询：subagent/scheduler 后台只写库不连 SSE，前端定时拉图驱动进度横幅与角色卡。
// 非流式时顺带刷新消息取回进度气泡，全任务终态即自停。

import { reactive, ref } from 'vue'

import { getTaskGraph } from '../api.js'

const POLL_INTERVAL = 1500

const graphBySession = reactive({})
const pollingSession = ref(null)
let timer = null
let isStreamingFn = () => false
let reloadMessagesFn = () => Promise.resolve()
let onPipelineFinishedFn = () => {}

export function useTaskPolling() {
  return {
    graphBySession,
    pollingSession,

    configure({ isStreaming, reloadMessages, onPipelineFinished }) {
      isStreamingFn = isStreaming || isStreamingFn
      reloadMessagesFn = reloadMessages || reloadMessagesFn
      onPipelineFinishedFn = onPipelineFinished || onPipelineFinishedFn
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
  }
}

function stopInternal() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function isPipelineFinished(graph) {
  const tasks = graph.tasks || []
  if (!tasks.length) return false
  const last = tasks[tasks.length - 1]
  return last.agent_type === 'finalize' && last.status === 'finished'
}

async function tick() {
  const sid = pollingSession.value
  if (!sid) return
  try {
    const graph = await getTaskGraph(sid)
    const wasActive = graphBySession[sid]?.active
    graphBySession[sid] = graph
    // 非流式时刷新消息，取回流式外落库的进度气泡
    if (!isStreamingFn(sid)) {
      await reloadMessagesFn(sid)
    }
    if (wasActive && !graph.active) {
      stopInternal()
      pollingSession.value = null
      if (isPipelineFinished(graph)) {
        onPipelineFinishedFn(sid)
      }
    }
  } catch {
    // 网络抖动忽略，下轮重试
  }
}
