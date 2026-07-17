// roleMeta 纯映射：状态/角色 -> 徽章与标签，新增状态仅改源码此处。
import { describe, it, expect } from 'vitest'

import {
  ROLE_LABELS,
  ROLE_ORDER,
  ROLE_TAG,
  STATUS_BADGE,
  stepOf,
  badgeOf,
} from '../team-panel/roleMeta.js'

describe('roleMeta 角色映射', () => {
  it('ROLE_LABELS 覆盖四角色', () => {
    expect(ROLE_LABELS.idea).toBe('选题官')
    expect(ROLE_LABELS.finalize).toBe('汇总编辑')
  })

  it('ROLE_ORDER 定序，stepOf 据此编号', () => {
    expect(ROLE_ORDER).toEqual(['idea', 'script', 'image', 'finalize'])
    expect(stepOf('idea')).toBe(1)
    expect(stepOf('finalize')).toBe(4)
    expect(stepOf('unknown')).toBe(0)
  })

  it('ROLE_TAG 给每角色职能标签', () => {
    for (const role of ROLE_ORDER) {
      expect(ROLE_TAG[role]).toBeTruthy()
    }
  })
})

describe('roleMeta 状态徽章', () => {
  it('已知状态返回 label 与 cls', () => {
    expect(STATUS_BADGE.running.label).toBe('工作中')
    expect(STATUS_BADGE.running.cls).toBe('running')
    expect(STATUS_BADGE.awaiting_confirm.label).toBe('等你确认')
  })

  it('badgeOf 未知状态降级返回原状态作 label', () => {
    const badge = badgeOf('weird_status')
    expect(badge.label).toBe('weird_status')
    expect(badge.cls).toBe('idle')
  })

  it('badgeOf 已知状态等价于直查表', () => {
    expect(badgeOf('finished')).toEqual(STATUS_BADGE.finished)
  })
})
