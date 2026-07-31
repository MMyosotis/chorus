// 创作产出投影规则单测。

import { test, expect } from 'vitest'
import { planArtifacts } from '../composables/artifactsProjection.js'

test('planArtifacts 非数组返回空', () => {
  expect(planArtifacts(null)).toEqual([])
  expect(planArtifacts(undefined)).toEqual([])
})

test('planArtifacts 无已完成任务返回空', () => {
  expect(planArtifacts([
    { id: 'r', status: 'running', agent_type: 'script' },
    { id: 'h', status: 'awaiting_confirm', agent_type: 'idea' },
  ])).toEqual([])
})

test('planArtifacts 选题取已选候选标题', () => {
  const rows = planArtifacts([{
    id: 'a', status: 'finished', agent_type: 'idea',
    artifacts: { candidates: [
      { index: 0, title: '甲标题' },
      { index: 1, title: '乙标题' },
    ], selected: 1 },
  }])
  expect(rows).toHaveLength(1)
  expect(rows[0]).toMatchObject({ kind: 'idea', title: '乙标题' })
})

test('planArtifacts 选题无选中落首条', () => {
  const rows = planArtifacts([{
    id: 'a', status: 'finished', agent_type: 'idea',
    artifacts: { candidates: [{ index: 0, title: '甲标题' }] },
  }])
  expect(rows[0].title).toBe('甲标题')
})

test('planArtifacts 文案优先用 char_count', () => {
  const rows = planArtifacts([{
    id: 'b', status: 'finished', agent_type: 'script',
    artifacts: { char_count: 320, markdown: '## 一\n\n## 二\n\n## 三' },
  }])
  expect(rows[0]).toMatchObject({ kind: 'script', charCount: 320, blockCount: 3 })
})

test('planArtifacts 文案无 char_count 取 markdown 长度', () => {
  const markdown = '## 小节\n\n正文段落'
  const rows = planArtifacts([{
    id: 'b', status: 'finished', agent_type: 'script',
    artifacts: { markdown },
  }])
  expect(rows[0]).toMatchObject({ kind: 'script', charCount: markdown.length, blockCount: 1 })
})

test('planArtifacts 配图取图片列表', () => {
  const rows = planArtifacts([{
    id: 'c', status: 'finished', agent_type: 'image',
    artifacts: { images: [{ url: 'u1' }, { url: 'u2' }] },
  }])
  expect(rows[0]).toMatchObject({ kind: 'image' })
  expect(rows[0].images).toHaveLength(2)
})

test('planArtifacts 定稿取标题', () => {
  const rows = planArtifacts([{
    id: 'd', status: 'finished', agent_type: 'finalize',
    artifacts: { markdown: '# 终稿\n\n正文', meta: { title: '终稿' } },
  }])
  expect(rows[0]).toMatchObject({ kind: 'finalize', title: '终稿' })
})

test('planArtifacts 按角色顺序输出', () => {
  const rows = planArtifacts([
    { id: 'd', status: 'finished', agent_type: 'finalize', artifacts: {} },
    { id: 'a', status: 'finished', agent_type: 'idea', artifacts: { candidates: [{ index: 0, title: 'T' }] } },
    { id: 'c', status: 'finished', agent_type: 'image', artifacts: { images: [] } },
    { id: 'b', status: 'finished', agent_type: 'script', artifacts: { char_count: 1, markdown: '## x' } },
  ])
  expect(rows.map((row) => row.kind)).toEqual(['idea', 'script', 'image', 'finalize'])
})

test('planArtifacts 同类型多任务取首条', () => {
  const rows = planArtifacts([
    { id: 'a1', status: 'finished', agent_type: 'idea', artifacts: { candidates: [{ index: 0, title: '一' }] } },
    { id: 'a2', status: 'finished', agent_type: 'idea', artifacts: { candidates: [{ index: 0, title: '二' }] } },
  ])
  expect(rows).toHaveLength(1)
  expect(rows[0].task.id).toBe('a1')
})
