import { describe, expect, it } from 'vitest'

import { splitStyleTags } from '../team-panel/styleTags.js'

describe('splitStyleTags', () => {
  it('按常见中英文标点拆分风格标签', () => {
    expect(splitStyleTags('真实、克制，有观察感;温暖｜松弛/自然\n生活化。')).toEqual([
      '真实',
      '克制',
      '有观察感',
      '温暖',
      '松弛',
      '自然',
      '生活化',
    ])
  })

  it('过滤空标签并保持首次出现顺序去重', () => {
    expect(splitStyleTags('真实，， 克制、真实；')).toEqual(['真实', '克制'])
  })

  it('兼容数组与空值', () => {
    expect(splitStyleTags(['真实、克制', '温暖'])).toEqual(['真实', '克制', '温暖'])
    expect(splitStyleTags(null)).toEqual([])
  })
})
