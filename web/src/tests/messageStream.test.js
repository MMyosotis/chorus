import { expect, test } from 'vitest'
import { findLastConversationEntryIndex } from '../composables/messageStream.js'

test('后端视图中的助手气泡仍是可续写的真实消息', () => {
  const entries = [
    { kind: 'user', role: 'user' },
    { kind: 'assistant', role: 'assistant', suspended: true },
    { kind: 'running', role: 'assistant' },
  ]

  expect(findLastConversationEntryIndex(entries)).toBe(1)
})

test('尾部任务卡会被跳过，找到前面的助手气泡', () => {
  const entries = [
    { kind: 'user', role: 'user' },
    { kind: 'assistant', role: 'assistant', suspended: true },
    { kind: 'hil', role: 'assistant' },
    { kind: 'confirmed', role: 'assistant' },
  ]

  expect(findLastConversationEntryIndex(entries)).toBe(1)
})
