// 任务卡投影规则单测。

import { test, expect } from 'vitest'
import { planTaskCards, planIntentCard } from '../composables/taskCardProjection.js'

test('planTaskCards 无图返回空', () => {
  expect(planTaskCards(null)).toEqual([])
  expect(planTaskCards(undefined)).toEqual([])
})

test('planTaskCards 空任务返回空', () => {
  expect(planTaskCards({ tasks: [] })).toEqual([])
})

test('planTaskCards 待确认归校样卡', () => {
  const plan = planTaskCards({ tasks: [{ id: 't1', status: 'awaiting_confirm', agent_type: 'idea' }] })
  expect(plan).toHaveLength(1)
  expect(plan[0]).toMatchObject({ kind: 'hil', id: 'hil:t1' })
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

test('planIntentCard 非就绪态返回空', () => {
  expect(planIntentCard(null)).toBeNull()
  expect(planIntentCard({ intent_status: 'capturing' })).toBeNull()
})

test('planIntentCard 就绪态返回确认卡', () => {
  const state = { intent_status: 'ready_to_confirm', goal: 'x' }
  const card = planIntentCard(state)
  expect(card).toMatchObject({ kind: 'intent-confirm', id: 'intent-confirm', role: 'assistant' })
  expect(card.state).toBe(state)
})

test.each(['confirmed', 'dispatched'])('planIntentCard %s 状态保留只读确认卡', (intentStatus) => {
  const state = { intent_status: intentStatus, goal: 'x' }
  const card = planIntentCard(state)
  expect(card).toMatchObject({ kind: 'intent-confirm', id: 'intent-confirm', role: 'assistant' })
  expect(card.state).toBe(state)
})
