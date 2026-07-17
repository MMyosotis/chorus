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

test('mergeAssistantHistory 无正文轮工具累积到下一条有正文助手', () => {
  const raw = [
    { role: 'assistant', content: '', tools: [{ name: 'search', display: '搜索' }] },
    { role: 'assistant', content: '结果', tools: [] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(1)
  expect(out[0].content).toBe('结果')
  expect(out[0].tools.items).toHaveLength(1)
  expect(out[0].tools.items[0].name).toBe('search')
})

test('mergeAssistantHistory 中间用户消息打断合并', () => {
  const raw = [
    { role: 'assistant', content: '', tools: [{ name: 'search' }] },
    { role: 'user', content: '插话' },
    { role: 'assistant', content: '回复', tools: [] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(3)
  expect(out[0].content).toBe('')
  expect(out[0].tools.items).toHaveLength(1)
  expect(out[1].role).toBe('user')
  expect(out[2].content).toBe('回复')
})

test('mergeAssistantHistory 同气泡后续轮工具与正文追加', () => {
  const raw = [
    { role: 'assistant', content: '首段', tools: [{ name: 'a' }] },
    { role: 'assistant', content: '次段', tools: [{ name: 'b' }] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(1)
  expect(out[0].content).toBe('首段\n\n次段')
  expect(out[0].tools.items.map((it) => it.name)).toEqual(['a', 'b'])
})

test('mergeAssistantHistory 尾部待落工具 flush 成空正文气泡', () => {
  const raw = [
    { role: 'user', content: '问' },
    { role: 'assistant', content: '', tools: [{ name: 'tail' }] },
  ]
  const out = mergeAssistantHistory(raw)
  expect(out).toHaveLength(2)
  expect(out[1].content).toBe('')
  expect(out[1].tools.items[0].name).toBe('tail')
})
