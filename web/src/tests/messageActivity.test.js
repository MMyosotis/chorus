import { expect, test } from 'vitest'
import { resolveActivityState } from '../composables/messageActivity.js'

test('助手已有正文后再次思考，仍展示思考状态', () => {
  expect(resolveActivityState({
    role: 'assistant',
    active: true,
    thinking: { state: 'running' },
    tools: { state: 'idle', items: [] },
  })).toBe('thinking')
})

test('工具调用中的状态优先于思考状态', () => {
  expect(resolveActivityState({
    role: 'assistant',
    active: true,
    thinking: { state: 'running' },
    tools: { state: 'running', items: [{ duration_ms: null }] },
  })).toBe('tools')
})

test('非活跃消息不展示过程状态', () => {
  expect(resolveActivityState({
    role: 'assistant',
    active: false,
    thinking: { state: 'running' },
    tools: { state: 'running', items: [{ duration_ms: null }] },
  })).toBe('idle')
})

test('正文流式输出时不重复展示过程状态', () => {
  expect(resolveActivityState({
    role: 'assistant',
    active: true,
    content: '正在输出的正文',
    thinking: { state: 'idle' },
    tools: { state: 'idle', items: [] },
  })).toBe('idle')
})
