import { expect, test } from 'vitest'
import { visibleComposingUnits } from '../composables/taskProgress.js'

test('配图进度不超过意图中的目标张数', () => {
  expect(visibleComposingUnits('image', 7, 4)).toBe(4)
  expect(visibleComposingUnits('image', 3, 4)).toBe(3)
})

test('其他角色保留实际结构单元计数', () => {
  expect(visibleComposingUnits('script', 7, 4)).toBe(7)
})
