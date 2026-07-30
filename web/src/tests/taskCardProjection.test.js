// 任务卡投影规则单测。

import { test, expect } from 'vitest'
import { planTaskCards, planIntentCard, planIntentCards, planOptionCard, planOptionCards } from '../composables/taskCardProjection.js'

test('planTaskCards 无图返回空', () => {
  expect(planTaskCards(null)).toEqual([])
  expect(planTaskCards(undefined)).toEqual([])
})

test('planTaskCards 空任务返回空', () => {
  expect(planTaskCards({ tasks: [] })).toEqual([])
})

test('planTaskCards 待确认归校样卡', () => {
  const plan = planTaskCards({ tasks: [{ id: 't1', message_id: 'm1', status: 'awaiting_confirm', agent_type: 'idea' }] })
  expect(plan).toHaveLength(1)
  expect(plan[0]).toMatchObject({ kind: 'hil', id: 'hil:t1', anchorMessageId: 'm1' })
  expect(plan[0].task.id).toBe('t1')
})

test('planTaskCards 失败归恢复卡', () => {
  const plan = planTaskCards({ tasks: [{ id: 't2', status: 'failed', agent_type: 'image' }] })
  expect(plan[0]).toMatchObject({ kind: 'recovery', id: 'recovery:t2' })
})

test('planTaskCards 定稿成品归成品卡', () => {
  const plan = planTaskCards({ tasks: [{ id: 't3', status: 'finished', agent_type: 'finalize' }] })
  expect(plan[0]).toMatchObject({ kind: 'postcard', id: 'postcard:t3' })
})

test('planTaskCards 运行中归运行卡', () => {
  const plan = planTaskCards({ tasks: [{ id: 't4', status: 'running', agent_type: 'script' }] })
  expect(plan[0]).toMatchObject({ kind: 'running', id: 'running:t4' })
})

test('planTaskCards 已完成非定稿各自成卡', () => {
  const plan = planTaskCards({
    tasks: [
      { id: 'a', status: 'finished', agent_type: 'idea' },
      { id: 'b', status: 'finished', agent_type: 'script' },
    ],
  })
  expect(plan.map((card) => card.kind)).toEqual(['confirmed', 'confirmed'])
  expect(plan.map((card) => card.id)).toEqual(['confirmed:a', 'confirmed:b'])
  expect(plan[0].task.id).toBe('a')
})

test('planTaskCards 定稿成品不进确认卡', () => {
  const plan = planTaskCards({ tasks: [{ id: 'f', status: 'finished', agent_type: 'finalize' }] })
  expect(plan.find((card) => card.kind === 'confirmed')).toBeUndefined()
})

test('planTaskCards 混合任务按顺序投影', () => {
  const plan = planTaskCards({
    tasks: [
      { id: 'r', status: 'running', agent_type: 'image' },
      { id: 'h', status: 'awaiting_confirm', agent_type: 'idea' },
      { id: 'p1', status: 'finished', agent_type: 'idea' },
      { id: 'd', status: 'finished', agent_type: 'finalize' },
    ],
  })
  expect(plan.map((card) => card.kind)).toEqual(['confirmed', 'running', 'hil', 'postcard'])
})

test('planIntentCard 无留档返回空', () => {
  expect(planIntentCard(null)).toBeNull()
  expect(planIntentCard(undefined)).toBeNull()
})

test('planIntentCard 待确认留档返回确认卡', () => {
  const confirmation = { confirmation_id: 'c1', message_id: 'm1', status: 'open', topic: 'x' }
  const card = planIntentCard(confirmation)
  expect(card).toMatchObject({ kind: 'intent-confirm', id: 'intent-confirm:c1', role: 'assistant', anchorMessageId: 'm1' })
  expect(card.state).toBe(confirmation)
})

test('planIntentCards 已作答与待确认都保留为留档卡', () => {
  const confirmations = [
    { confirmation_id: 'c1', status: 'answered', topic: 'a' },
    { confirmation_id: 'c2', status: 'open', topic: 'b' },
  ]
  expect(planIntentCards(confirmations)).toMatchObject([
    { kind: 'intent-confirm', id: 'intent-confirm:c1', state: confirmations[0] },
    { kind: 'intent-confirm', id: 'intent-confirm:c2', state: confirmations[1] },
  ])
})

test('planOptionCard 无提问返回空', () => {
  expect(planOptionCard(null)).toBeNull()
  expect(planOptionCard(undefined)).toBeNull()
})

test('planOptionCard 有提问返回选项卡', () => {
  const prompt = { message_id: 'm1', question: '选哪个方向', options: [], allow_custom: true }
  const card = planOptionCard(prompt)
  expect(card).toMatchObject({ kind: 'option', id: 'option:open', role: 'assistant', anchorMessageId: 'm1' })
  expect(card.prompt).toBe(prompt)
})

test('planOptionCards 已回答的选项保留为留档卡', () => {
  const prompts = [
    { prompt_id: 'p1', status: 'answered', question: '选哪个方向', options: [], allow_custom: true },
    { prompt_id: 'p2', status: 'open', question: '下一步', options: [], allow_custom: true },
  ]
  expect(planOptionCards(prompts)).toMatchObject([
    { kind: 'option', id: 'option:p1', prompt: prompts[0] },
    { kind: 'option', id: 'option:p2', prompt: prompts[1] },
  ])
})
