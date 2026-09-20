// 建图挂起边界判定单测。

import { test, expect } from 'vitest'
import { isPlanResumeBoundary } from '../composables/messageHistory.js'

test('isPlanResumeBoundary 识别建图挂起边界', () => {
  expect(isPlanResumeBoundary({
    suspended: true,
    tools: [{ name: 'create_plan' }],
  })).toBe(true)
  expect(isPlanResumeBoundary({
    suspended: true,
    tools: { items: [{ name: 'create_plan' }] },
  })).toBe(true)
  expect(isPlanResumeBoundary({
    suspended: false,
    tools: [{ name: 'create_plan' }],
  })).toBe(false)
  expect(isPlanResumeBoundary({
    suspended: true,
    tools: [{ name: 'update_intent_state' }],
  })).toBe(false)
})
