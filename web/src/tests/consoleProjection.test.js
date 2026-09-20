import { test, expect } from 'vitest'
import {
  BYPASS_PURPOSE_LABELS,
  buildBypassCalls,
  buildModelCalls,
  buildSessionStats,
  buildTimeline,
  buildUserInputs,
  displayToolContent,
  parseTaggedContent,
  toolCallArguments,
} from '../composables/consoleProjection.js'

function requestTrace(at, messageId, messages) {
  return { phase: 'model_request', created_at: at, message_id: messageId, source: 'supervisor', payload: { model: 'm', messages, tools: [] } }
}

function responseTrace(at, messageId, extra = {}) {
  return { phase: 'model_response', created_at: at, message_id: messageId, source: 'supervisor', payload: { content: 'ok', duration_ms: 100, ...extra } }
}

function bypassTrace(at, purpose, extra = {}) {
  return { phase: 'bypass_call', created_at: at, message_id: null, source: 'supervisor', task_id: null, payload: { purpose, model: 'm', prompt: 'p', max_tokens: 512, status: 'success', ...extra } }
}

function userTrace(at, content = '问') {
  return { phase: 'user_input', created_at: at, message_id: `u${at}`, source: 'supervisor', payload: { content } }
}

const roleFor = (source, taskId) => ({ key: `${source}:${taskId || ''}`, label: source })

test('buildModelCalls 按消息聚合同轮的请求响应与工具轨迹', () => {
  const calls = buildModelCalls([
    responseTrace(3, 'm1'),
    { phase: 'tool_result', created_at: 2, message_id: 'm1', payload: { tool_call_id: 'c1', content: 'r' } },
    requestTrace(1, 'm1', [{ role: 'user', content: '问' }]),
  ])
  expect(calls).toHaveLength(1)
  expect(calls[0].request.payload.messages).toEqual([{ role: 'user', content: '问' }])
  expect(calls[0].response.payload.content).toBe('ok')
  expect(calls[0].toolResults.get('c1').payload.content).toBe('r')
})

test('buildBypassCalls 只取旁路轨迹并按时间排序', () => {
  const bypasses = buildBypassCalls([
    bypassTrace(2, 'title'),
    requestTrace(1, 'm1', []),
    bypassTrace(1, 'summary'),
  ])
  expect(bypasses.map((call) => call.payload.purpose)).toEqual(['summary', 'title'])
  expect(bypasses[0]).toMatchObject({ source: 'supervisor', task_id: null })
  expect(bypasses[0].key).toBe('bypass:1:supervisor::summary')
})

test('buildTimeline 首轮前的旁路并入第一轮不占轮次', () => {
  const calls = buildModelCalls([
    requestTrace(2, 'm1', [{ role: 'user', content: '问' }]),
    responseTrace(3, 'm1'),
  ])
  const bypasses = buildBypassCalls([bypassTrace(1, 'memory_recall')])
  const timeline = buildTimeline(calls, bypasses, [], roleFor)

  expect(timeline.map((item) => item.kind)).toEqual(['user', 'bypass', 'loop'])
  expect(new Set(timeline.map((item) => item.turn))).toEqual(new Set([1]))
})

test('buildTimeline 轮间与收尾后的旁路继承当前轮次', () => {
  const calls = buildModelCalls([
    requestTrace(2, 'm1', [{ role: 'user', content: '问一' }]),
    responseTrace(3, 'm1'),
    requestTrace(4, 'm2', [{ role: 'user', content: '问二' }]),
    responseTrace(5, 'm2'),
  ])
  const bypasses = buildBypassCalls([
    bypassTrace(3.5, 'summary'),
    bypassTrace(6, 'title'),
  ])
  const timeline = buildTimeline(calls, bypasses, [], roleFor)

  const summaryItem = timeline.find((item) => item.kind === 'bypass' && item.item.payload.purpose === 'summary')
  const titleItem = timeline.find((item) => item.kind === 'bypass' && item.item.payload.purpose === 'title')
  expect(summaryItem.turn).toBe(1)
  expect(titleItem.turn).toBe(2)
})

test('buildTimeline 只有旁路轨迹时不增加对话轮次', () => {
  const timeline = buildTimeline([], buildBypassCalls([bypassTrace(1, 'title')]), [], roleFor)
  expect(timeline).toHaveLength(1)
  expect(timeline[0]).toMatchObject({ kind: 'bypass', turn: 0 })
})

test('buildTimeline 使用独立用户输入的真实时间', () => {
  const traces = [
    userTrace(1, '真实输入'),
    bypassTrace(2, 'memory_recall'),
    requestTrace(3, 'm1', [{ role: 'user', content: '真实输入' }]),
    responseTrace(4, 'm1'),
  ]
  const timeline = buildTimeline(
    buildModelCalls(traces),
    buildBypassCalls(traces),
    buildUserInputs(traces),
    roleFor,
  )

  expect(timeline.map((item) => item.kind)).toEqual(['user', 'bypass', 'loop'])
  expect(timeline[0]).toMatchObject({ created_at: 1, message: { text: '真实输入' } })
})

test('buildSessionStats 折算旁路用量与费用', () => {
  const calls = buildModelCalls([
    requestTrace(1, 'm1', [{ role: 'user', content: '问' }]),
    responseTrace(2, 'm1', { usage: { input_tokens: 10, output_tokens: 5, total_tokens: 15 }, cost_cny: 0.1 }),
  ])
  const bypasses = buildBypassCalls([
    bypassTrace(3, 'title', { usage: { input_tokens: 7, output_tokens: 3, total_tokens: 10 }, cost_cny: 0.2 }),
  ])
  const stats = buildSessionStats(calls, bypasses, 1)

  expect(stats).toMatchObject({
    callCount: 1,
    bypassCount: 1,
    inputTokens: 17,
    outputTokens: 8,
    totalTokens: 25,
  })
  expect(stats.costCny).toBeCloseTo(0.3)
})

test('buildSessionStats 双空返回空、仅旁路可成统计', () => {
  expect(buildSessionStats([], [], 0)).toBeNull()
  const stats = buildSessionStats([], buildBypassCalls([bypassTrace(1, 'suggestion')]), 0)
  expect(stats).toMatchObject({ bypassCount: 1, callCount: 0, turnCount: 0 })
})

test('旁路用途标签覆盖全部已知用途', () => {
  const known = ['title', 'summary', 'suggestion', 'aside', 'memory_extract', 'memory_merge', 'memory_recall']
  for (const purpose of known) expect(BYPASS_PURPOSE_LABELS[purpose]).toBeTruthy()
})

test('toolCallArguments 美化 JSON 参数字符串并原样保留非 JSON', () => {
  const parsed = toolCallArguments({ function: { arguments: '{"style":"治愈","image_count":3}' } })
  expect(parsed).toBe('{\n  "style": "治愈",\n  "image_count": 3\n}')
  expect(toolCallArguments({ function: { arguments: 'plain text' } })).toBe('plain text')
  expect(toolCallArguments({ function: {} })).toBe('')
})

test('parseTaggedContent 读取新的意图标签和子 agent 注入标签', () => {
  const parsed = parseTaggedContent('<intent_state>状态</intent_state>用户输入<base_card>底稿</base_card>')
  expect(parsed.text).toBe('用户输入')
  expect(parsed.injections).toEqual([
    { label: '意图状态', content: '状态' },
    { label: '底稿', content: '底稿' },
  ])
})

test('displayToolContent 去掉工具结果和错误标签', () => {
  expect(displayToolContent('<tool_result>\n{"ok":true}\n</tool_result>')).toBe('{"ok":true}')
  expect(displayToolContent('<error>\n失败\n</error>')).toBe('失败')
})
