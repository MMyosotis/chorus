// useTaskPolling：per-session task 图轮询，驱动主面板进度横幅/节拍气泡 + 右侧角色卡。
//
// subagent/scheduler 后台进度不连 SSE（只写库），前端靠 ~1.5s 轮询 GET /api/tasks 取图，
// 并在非流式时刷新 messages 拉回 progress 气泡 + friendly_reply。active=False（全终态）自停。
//
// 数据形态：graphBySession = { [sessionId]: { pipeline_id, active, tasks: [...] } }
// pollingSession：当前轮询中的 sessionId（单会话轮询，切走即停）。

import { reactive, ref } from 'vue'

import { getTaskGraph } from '../api.js'

const POLL_INTERVAL = 1500

const graphBySession = reactive({})
const pollingSession = ref(null)
let timer = null
// 由 App.vue 注入：流式中的会话集合，避免轮询刷新 messages 与 SSE 累积冲突
let isStreamingFn = () => false
// 由 App.vue 注入：用 fetchMessages 结果重建该会话消息列表
let reloadMessagesFn = () => Promise.resolve()

export function useTaskPolling() {
  return {
    graphBySession,
    pollingSession,

    configure({ isStreaming, reloadMessages }) {
      isStreamingFn = isStreaming || isStreamingFn
      reloadMessagesFn = reloadMessages || reloadMessagesFn
    },

    getGraph(sessionId) {
      return graphBySession[sessionId] || null
    },

    start(sessionId) {
      if (!sessionId) return
      // 切到新会话：停旧轮询
      if (pollingSession.value !== sessionId) {
        stopInternal()
        pollingSession.value = sessionId
      }
      if (timer) return // 已在跑
      tick() // 立即跑一次
      timer = setInterval(tick, POLL_INTERVAL)
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

async function tick() {
  const sid = pollingSession.value
  if (!sid) return
  try {
    const graph = await getTaskGraph(sid)
    graphBySession[sid] = graph
    // 非流式时刷新 messages（progress 气泡 + friendly_reply 落库后靠此取回）
    if (!isStreamingFn(sid)) {
      await reloadMessagesFn(sid)
    }
    if (!graph.active) {
      stopInternal()
      pollingSession.value = null
    }
  } catch {
    // 网络抖动忽略，下个 tick 重试
  }
}
