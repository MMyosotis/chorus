// useTraceStore 单例：按会话聚合 trace，pollFromServer 按时间/来源去重合并。
import { describe, it, expect, beforeEach, vi } from 'vitest'

const fetchTraces = vi.fn()
vi.mock('../api.js', () => ({ fetchTraces }))

const { useTraceStore } = await import('../composables/useTraceStore.js')

function traceItem(createdAt, phase, messageId, taskId) {
  return { created_at: createdAt, phase, message_id: messageId, task_id: taskId, payload: {} }
}

describe('useTraceStore', () => {
  let store

  beforeEach(() => {
    fetchTraces.mockReset()
    store = useTraceStore()
    store.clearTrace('s1')
    store.clearTrace('s2')
  })

  it('addTrace 累积到对应会话', () => {
    store.addTrace('s1', traceItem(1, 'model_request', 'm1', null))
    store.addTrace('s1', traceItem(2, 'model_response', 'm1', null))
    expect(store.getTraces('s1')).toHaveLength(2)
    expect(store.getTraces('s2')).toHaveLength(0)
  })

  it('空 sessionId 被忽略', () => {
    store.addTrace('', traceItem(1, 'x', 'm', null))
    store.clearTrace('')
    expect(store.getTraces('')).toHaveLength(0)
  })

  it('clearTrace 清空并允许重新加载', async () => {
    fetchTraces.mockResolvedValue([traceItem(1, 'model_request', 'm1', null)])
    await store.loadFromServer('s1')
    expect(store.getTraces('s1')).toHaveLength(1)

    store.clearTrace('s1')
    expect(store.getTraces('s1')).toHaveLength(0)

    fetchTraces.mockResolvedValue([traceItem(1, 'model_request', 'm1', null)])
    await store.loadFromServer('s1') // clearTrace 后 loadedSessions 已删，可重拉
    expect(store.getTraces('s1')).toHaveLength(1)
  })

  it('loadFromServer 首次拉取后标记已加载，二次不重复拉', async () => {
    fetchTraces.mockResolvedValue([traceItem(1, 'model_request', 'm1', null)])
    await store.loadFromServer('s1')
    await store.loadFromServer('s1')
    expect(fetchTraces).toHaveBeenCalledTimes(1)
  })

  it('pollFromServer 去重合并：已有条目不重复入列', async () => {
    fetchTraces.mockResolvedValue([
      traceItem(1, 'model_request', 'm1', null),
      traceItem(2, 'model_response', 'm1', null),
    ])
    await store.loadFromServer('s1')
    expect(store.getTraces('s1')).toHaveLength(2)

    // 二次拉取含一条新 + 两条旧
    fetchTraces.mockResolvedValue([
      traceItem(1, 'model_request', 'm1', null),
      traceItem(2, 'model_response', 'm1', null),
      traceItem(3, 'tool_call', 'm1', null),
    ])
    await store.pollFromServer('s1')
    expect(store.getTraces('s1')).toHaveLength(3)
    expect(store.getTraces('s1')[2].phase).toBe('tool_call')
  })

  it('pollFromServer 同时间不同来源视为不同条目', async () => {
    fetchTraces.mockResolvedValue([traceItem(1, 'model_request', 'm1', null)])
    await store.loadFromServer('s1')

    fetchTraces.mockResolvedValue([
      traceItem(1, 'model_request', 'm1', null),
      traceItem(1, 'model_request', 'm1', 't1'), // 同时间但 task_id 不同
    ])
    await store.pollFromServer('s1')
    expect(store.getTraces('s1')).toHaveLength(2)
  })

  it('loadFromServer 失败时降级为空列表不抛', async () => {
    fetchTraces.mockRejectedValue(new Error('network'))
    await store.loadFromServer('s1')
    expect(store.getTraces('s1')).toHaveLength(0)
  })
})
