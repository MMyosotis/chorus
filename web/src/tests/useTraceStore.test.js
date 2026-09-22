// useTraceStore 单例：按会话缓存后端成品视图，refresh 整表替换。
import { describe, beforeEach, expect, it, vi } from 'vitest'

const fetchTraceView = vi.fn()
vi.mock('../api.js', () => ({ fetchTraceView }))

describe('useTraceStore', () => {
  let store

  beforeEach(async () => {
    fetchTraceView.mockReset()
    const { useTraceStore } = await import('../composables/useTraceStore.js')
    store = useTraceStore()
    for (const sessionId of Object.keys(store.viewsBySession)) delete store.viewsBySession[sessionId]
  })

  it('refresh 整表替换对应会话视图', async () => {
    const view = { agents: [{ key: 'supervisor', label: '主编' }], stats: null, turns: [] }
    fetchTraceView.mockResolvedValue(view)
    await store.refresh('s1', 'all')
    expect(store.getView('s1')).toStrictEqual(view)
    expect(fetchTraceView).toHaveBeenCalledWith('s1', 'all')
  })

  it('空会话标识被忽略', async () => {
    await store.refresh('', 'all')
    expect(fetchTraceView).not.toHaveBeenCalled()
    expect(store.getView('')).toBeNull()
  })

  it('拉取失败保留原视图不抛', async () => {
    const view = { agents: [], stats: null, turns: [] }
    fetchTraceView.mockResolvedValueOnce(view)
    await store.refresh('s1', 'all')
    fetchTraceView.mockRejectedValueOnce(new Error('network'))
    await store.refresh('s1', 'all')
    expect(store.getView('s1')).toStrictEqual(view)
  })
})
