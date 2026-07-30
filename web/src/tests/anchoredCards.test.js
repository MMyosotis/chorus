import { expect, test } from 'vitest'
import { insertAnchoredCard, replaceAnchoredCards } from '../composables/anchoredCards.js'

test('虚拟卡按 message id 插入对应助手消息之后', () => {
  const list = [
    { id: 'm1', role: 'assistant', content: '第一轮' },
    { id: 'm2', role: 'assistant', content: '第二轮' },
  ]
  replaceAnchoredCards(list, (item) => item.kind === 'option', [
    { id: 'option:p1', kind: 'option', anchorMessageId: 'm1' },
    { id: 'option:p2', kind: 'option', anchorMessageId: 'm2' },
  ])
  expect(list.map((item) => item.id)).toEqual(['m1', 'option:p1', 'm2', 'option:p2'])
})

test('找不到锚点的卡片不插入到错误位置', () => {
  const list = [{ id: 'm1', role: 'assistant', content: '第一轮' }]
  replaceAnchoredCards(list, (item) => item.kind === 'option', [
    { id: 'option:legacy', kind: 'option', anchorMessageId: 'missing' },
  ])
  expect(list.map((item) => item.id)).toEqual(['m1'])
})

test('虚拟卡可锚定到合并气泡中的后续消息', () => {
  const list = [{ id: 'm1', messageIds: ['m1', 'm2'], role: 'assistant' }]

  insertAnchoredCard(list, { id: 'option:p2', kind: 'option', anchorMessageId: 'm2' })

  expect(list).toHaveLength(2)
  expect(list[1]).toMatchObject({ id: 'option:p2', anchorMessageId: 'm2' })
})
