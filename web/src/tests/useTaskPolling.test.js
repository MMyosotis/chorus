// useTaskPolling 单例轮询：切会话停旧、流式时跳过视图套用、全终态自停并回调、getGraph 默认 null。
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

const fetchSessionView = vi.fn()
vi.mock('../api.js', () => ({ fetchSessionView }))

const { useTaskPolling } = await import('../composables/useTaskPolling.js')

function view(active, tasks) {
  return {
    bubbles: [],
    graph: { pipeline_id: 'p1', active, tasks: tasks || [] },
    intent_state: null,
    stage: '自由对话',
    needs_resume: false,
  }
}

describe('useTaskPolling', () => {
  let polling

  beforeEach(() => {
    vi.useFakeTimers()
    fetchSessionView.mockReset()
    polling = useTaskPolling()
    polling.configure({
      isStreaming: () => false,
      onView: () => Promise.resolve(),
      onSettled: () => {},
    })
  })

  afterEach(() => {
    polling.stop()
    vi.useRealTimers()
  })

  it('getGraph 未拉取时返回 null', () => {
    expect(polling.getGraph('s1')).toBeNull()
  })

  it('start 立即拉一次视图并写入 graphBySession', async () => {
    fetchSessionView.mockResolvedValue(view(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')
    expect(fetchSessionView).toHaveBeenCalledWith('s1')
    expect(polling.getGraph('s1').active).toBe(true)
  })

  it('空 sessionId 不拉取', async () => {
    await polling.start('')
    expect(fetchSessionView).not.toHaveBeenCalled()
  })

  it('流式时跳过视图套用，非流式时套用', async () => {
    const onView = vi.fn(() => Promise.resolve())
    polling.configure({ isStreaming: (sid) => sid === 's1', onView })
    fetchSessionView.mockResolvedValue(view(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')
    expect(onView).not.toHaveBeenCalled() // s1 流式 -> 不套用

    fetchSessionView.mockResolvedValue(view(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s2')
    expect(onView).toHaveBeenCalledWith('s2', expect.objectContaining({ graph: expect.anything() }))
  })

  it('任务图始终写入 graphBySession，即使流式跳过套用', async () => {
    polling.configure({ isStreaming: () => true })
    fetchSessionView.mockResolvedValue(view(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')
    expect(polling.getGraph('s1').tasks).toHaveLength(1)
  })

  it('pipeline 全部完成翻转 active 时自停并回调', async () => {
    const settled = vi.fn()
    polling.configure({ isStreaming: () => false, onView: () => Promise.resolve(), onSettled: settled })
    fetchSessionView.mockResolvedValueOnce(view(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')

    fetchSessionView.mockResolvedValueOnce(view(false, [
      { agent_type: 'idea', status: 'finished' },
      { agent_type: 'finalize', status: 'finished' },
    ]))
    await vi.advanceTimersToNextTimerAsync()

    expect(settled).toHaveBeenCalledWith('s1')
    expect(polling.pollingSession.value).toBeNull()
  })

  it('出现失败任务时不触发完成回调（取消路径由取消回调按铃）', async () => {
    const settled = vi.fn()
    polling.configure({ isStreaming: () => false, onView: () => Promise.resolve(), onSettled: settled })
    fetchSessionView.mockResolvedValueOnce(view(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')

    fetchSessionView.mockResolvedValueOnce(view(false, [
      { agent_type: 'idea', status: 'finished' },
      { agent_type: 'script', status: 'failed' },
    ]))
    await vi.advanceTimersToNextTimerAsync()

    expect(settled).not.toHaveBeenCalled()
  })

  it('含已取消任务时不触发完成回调', async () => {
    const settled = vi.fn()
    polling.configure({ isStreaming: () => false, onView: () => Promise.resolve(), onSettled: settled })
    fetchSessionView.mockResolvedValueOnce(view(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')

    fetchSessionView.mockResolvedValueOnce(view(false, [
      { agent_type: 'idea', status: 'finished' },
      { agent_type: 'script', status: 'cancelled' },
    ]))
    await vi.advanceTimersToNextTimerAsync()

    expect(settled).not.toHaveBeenCalled()
  })

  it('启动时已空闲则一轮后自停且不触发完成回调', async () => {
    const settled = vi.fn()
    polling.configure({ isStreaming: () => false, onView: () => Promise.resolve(), onSettled: settled })
    fetchSessionView.mockResolvedValue(view(false, [
      { agent_type: 'idea', status: 'finished' },
      { agent_type: 'finalize', status: 'finished' },
    ]))
    await polling.start('s1')

    expect(settled).not.toHaveBeenCalled()
    expect(polling.pollingSession.value).toBeNull()
    fetchSessionView.mockClear()
    await vi.advanceTimersByTimeAsync(3000)
    expect(fetchSessionView).not.toHaveBeenCalled() // 已自停不再发请求
  })

  it('切到新会话停旧轮询并切换 pollingSession', async () => {
    fetchSessionView.mockResolvedValue(view(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')
    expect(polling.pollingSession.value).toBe('s1')

    await polling.start('s2')
    expect(polling.pollingSession.value).toBe('s2')
  })

  it('refresh 在活跃轮询时立即拉取一次', async () => {
    fetchSessionView.mockResolvedValue(view(true, [{ agent_type: 'idea', status: 'running' }]))
    await polling.start('s1')
    fetchSessionView.mockClear()

    polling.refresh('s1')
    expect(fetchSessionView).toHaveBeenCalledWith('s1')
  })

  it('refresh 在无轮询时启动轮询', async () => {
    fetchSessionView.mockResolvedValue(view(true, [{ agent_type: 'idea', status: 'running' }]))
    polling.refresh('s1')
    await vi.advanceTimersToNextTimerAsync()
    expect(fetchSessionView).toHaveBeenCalledWith('s1')
    expect(polling.pollingSession.value).toBe('s1')
  })

  it('网络瞬时失败静默重试不抛', async () => {
    fetchSessionView.mockRejectedValue(new Error('network down'))
    await expect(polling.start('s1')).resolves.toBeUndefined()
  })
})
