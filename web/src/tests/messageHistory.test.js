// 助手历史合并规则单测。

import { test, expect } from 'vitest'
import { mapToolItem, normalizeAssistant, mergeAssistantHistory } from '../composables/messageHistory.js'

test('mapToolItem 正常映射', () => {
  const out = mapToolItem({ name: 'load_skill', arguments: { x: 1 }, duration_ms: 5, content: 'c', display: 'd' })
  expect(out).toEqual({ name: 'load_skill', arguments: { x: 1 }, duration_ms: 5, content: 'c', display: 'd' })
})

test('mapToolItem 缺省补齐', () => {
  const out = mapToolItem({ name: 'search' })
  expect(out).toEqual({ name: 'search', arguments: {}, duration_ms: null, content: '', display: 'search' })
})

test('normalizeAssistant 工具映射并补结构', () => {
  const out = normalizeAssistant({ role: 'assistant', content: 'hi', tools: [{ name: 't' }] })
  expect(out.role).toBe('assistant')
  expect(out.content).toBe('hi')
  expect(out.thinking).toEqual({ state: 'idle' })
  expect(out.tools.state).toBe('idle')
  expect(out.tools.items[0]).toEqual({ name: 't', arguments: {}, duration_ms: null, content: '', display: 't' })
})

test('normalizeAssistant 正文与工具缺省', () => {
  const out = normalizeAssistant({})
  expect(out.content).toBe('')
  expect(out.tools.items).toEqual([])
  expect(typeof out.created_at).toBe('number')
})

test('mergeAssistantHistory 空入空出', () => {
  expect(mergeAssistantHistory([])).toEqual([])
})

test('mergeAssistantHistory 段内无正文工具轮不累积到后续有正文助手', () => {
  const raw = [
    { role: 'assistant', content: '', tools: [{ name: 'search', display: '搜索' }] },
    { role: 'assistant', content: '结果', tools: [] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(1)
  expect(out[0].content).toBe('结果')
  expect(out[0].tools.items).toHaveLength(0)
})

test('mergeAssistantHistory 中间用户消息打断合并', () => {
  const raw = [
    { role: 'assistant', content: '', tools: [{ name: 'search' }] },
    { role: 'user', content: '插话' },
    { role: 'assistant', content: '回复', tools: [] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(2)
  expect(out[0].role).toBe('user')
  expect(out[0].content).toBe('插话')
  expect(out[1].role).toBe('assistant')
  expect(out[1].content).toBe('回复')
})

test('mergeAssistantHistory 同气泡后续轮正文追加', () => {
  const raw = [
    { role: 'assistant', content: '首段', tools: [{ name: 'a' }] },
    { role: 'assistant', content: '次段', tools: [{ name: 'b' }] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(1)
  expect(out[0].content).toBe('首段\n\n次段')
  expect(out[0].tools.items).toHaveLength(0)
})

test('mergeAssistantHistory 尾部无正文工具轮丢弃不独立成泡', () => {
  const raw = [
    { role: 'user', content: '问' },
    { role: 'assistant', content: '答', tools: [{ name: 'a' }] },
    { role: 'assistant', content: '', tools: [{ name: 'tail' }] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(2)
  expect(out[1].role).toBe('assistant')
  expect(out[1].content).toBe('答')
  expect(out[1].tools.items).toHaveLength(0)
})

test('mergeAssistantHistory 无正文工具轮前无助手则丢弃不画空泡', () => {
  const raw = [
    { role: 'user', content: '问' },
    { role: 'assistant', content: '', tools: [{ name: 'only_tool' }] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(1)
  expect(out[0].role).toBe('user')
})

test('mergeAssistantHistory 跨用户段的无正文工具轮不并入前段助手', () => {
  const raw = [
    { role: 'assistant', content: '答', tools: [{ name: 'a' }] },
    { role: 'user', content: '再问' },
    { role: 'assistant', content: '', tools: [{ name: 'b' }] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(2)
  expect(out[0].content).toBe('答')
  expect(out[0].tools.items).toHaveLength(0)
  expect(out[1].role).toBe('user')
})

test('mergeAssistantHistory 段内无正文工具轮跨用户消息均丢弃', () => {
  const raw = [
    { role: 'assistant', content: '首答', tools: [{ name: 'a' }] },
    { role: 'assistant', content: '', tools: [{ name: 'b' }] },
    { role: 'user', content: '再问' },
    { role: 'assistant', content: '再答', tools: [{ name: 'c' }] },
    { role: 'assistant', content: '', tools: [{ name: 'd' }] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(3)
  expect(out[0].content).toBe('首答')
  expect(out[0].tools.items).toHaveLength(0)
  expect(out[1].role).toBe('user')
  expect(out[2].content).toBe('再答')
  expect(out[2].tools.items).toHaveLength(0)
})
