import { expect, test } from 'vitest'
import { shouldUseBareMode } from '../composables/messageBubble.js'

test('挂起且无正文的助手气泡保持透明外壳', () => {
  expect(shouldUseBareMode({
    role: 'assistant',
    content: '',
    active: false,
    recaps: [],
    suspended: true,
  })).toBe(true)
})

test('挂起气泡已有正文时保留普通内容外壳', () => {
  expect(shouldUseBareMode({
    role: 'assistant',
    content: '已收到，我继续处理。',
    active: false,
    recaps: [],
    suspended: true,
  })).toBe(false)
})

test('用户消息不进入助手透明模式', () => {
  expect(shouldUseBareMode({
    role: 'user',
    content: '',
    active: false,
    recaps: [],
    suspended: true,
  })).toBe(false)
})
