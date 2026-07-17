// useTaskPolling 单例轮询：切会话停旧、流式时跳过、全终态自停并回调、getGraph 默认 null。
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

const getTaskGraph = vi.fn()
vi.mock('../api.js', () => ({ getTaskGraph }))

const { useTaskPolling } = await import('../composables/useTaskPolling.js')

function graph(active, tasks) {
  return { pipeline_id: 'p1', active, tasks: tasks || [] }
}

describe('useTaskPolling', () => {
  let polling

  beforeEach(() => {
    vi.useFakeTimers()
    getTaskGraph.mockReset()
    polling = useTaskPolling()
    polling.configure({
      isStreaming: () => false,
      reloadMessages: () => Promise.resolve(),
      onPipelineFinished: () => {},
    })
  })

  afterEach(() => {
    polling.stop()
    vi.useRealTimers()
  })

  it('getGraph 未拉取时返回 null', () => {
    expect(polling.getGraph('s1')).toBeNull()
  })

  it('start 立即拉一次图并写入 graphBySession', async () => {
    getTaskGraph.mockResolvedValue(graph(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')
    expect(getTaskGraph).toHaveBeenCalledWith('s1')
    expect(polling.getGraph('s1').active).toBe(true)
  })

  it('空 sessionId 不拉取', async () => {
    await polling.start('')
    expect(getTaskGraph).not.toHaveBeenCalled()
  })

  it('流式时跳过 reloadMessages，非流式时刷新消息', async () => {
    const reload = vi.fn(() => Promise.resolve())
    polling.configure({ isStreaming: (sid) => sid === 's1', reloadMessages: reload })
    getTaskGraph.mockResolvedValue(graph(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')
    expect(reload).not.toHaveBeenCalledWith('s1') // s1 流式 -> 不刷新

    getTaskGraph.mockResolvedValue(graph(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s2')
    expect(reload).toHaveBeenCalledWith('s2') // s2 非流式 -> 刷新
  })

  it('pipeline 完成翻转 active 时自停并回调', async () => {
    const finished = vi.fn()
    polling.configure({ isStreaming: () => false, reloadMessages: () => Promise.resolve(), onPipelineFinished: finished })
    // 首次 active=true
    getTaskGraph.mockResolvedValueOnce(graph(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')

    // 下一 tick：active 翻 false 且 finalize finished
    getTaskGraph.mockResolvedValueOnce(graph(false, [
      { agent_type: 'idea', status: 'finished' },
      { agent_type: 'finalize', status: 'finished' },
    ]))
    await vi.advanceTimersToNextTimerAsync()

    expect(finished).toHaveBeenCalledWith('s1')
    expect(polling.pollingSession.value).toBeNull()
  })

  it('切到新会话停旧轮询并切换 pollingSession', async () => {
    getTaskGraph.mockResolvedValue(graph(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')
    expect(polling.pollingSession.value).toBe('s1')

    await polling.start('s2')
    expect(polling.pollingSession.value).toBe('s2')
  })

  it('网络瞬时失败静默重试不抛', async () => {
    getTaskGraph.mockRejectedValue(new Error('network down'))
    await expect(polling.start('s1')).resolves.toBeUndefined()
  })
})
