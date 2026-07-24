// 任务图快照到右栏创作产出段的投影规则。纯函数无副作用，便于单测。

import { ROLE_ORDER } from '../team-panel/roleMeta.js'

function pickIdeaTitle(artifacts) {
  const candidates = artifacts && Array.isArray(artifacts.candidates) ? artifacts.candidates : []
  if (!candidates.length) return ''
  const picked = artifacts.selected != null
    ? candidates.find((candidate) => candidate.index === artifacts.selected)
    : null
  return (picked || candidates[0]).title || ''
}

function scriptStats(artifacts) {
  const blocks = artifacts && Array.isArray(artifacts.blocks) ? artifacts.blocks : []
  const charCount = artifacts && Number.isFinite(artifacts.char_count)
    ? artifacts.char_count
    : blocks.reduce((sum, block) => sum + (block.text ? block.text.length : 0), 0)
  return { charCount, blockCount: blocks.length }
}

function imageList(artifacts) {
  return artifacts && Array.isArray(artifacts.images) ? artifacts.images : []
}

function finalizeSummary(artifacts) {
  const data = artifacts || {}
  return {
    cover: data.cover || null,
    title: data.title || '',
    previewRef: (data.meta && data.meta.preview_ref) || null,
  }
}

export function planArtifacts(tasks) {
  const list = Array.isArray(tasks) ? tasks : []
  const finishedByType = new Map()
  for (const task of list) {
    if (!task || task.status !== 'finished' || !task.agent_type) continue
    if (!finishedByType.has(task.agent_type)) finishedByType.set(task.agent_type, task)
  }
  const rows = []
  for (const agentType of ROLE_ORDER) {
    const task = finishedByType.get(agentType)
    if (!task) continue
    if (agentType === 'idea') {
      rows.push({ kind: 'idea', task, title: pickIdeaTitle(task.artifacts) })
    } else if (agentType === 'script') {
      rows.push({ kind: 'script', task, ...scriptStats(task.artifacts) })
    } else if (agentType === 'image') {
      rows.push({ kind: 'image', task, images: imageList(task.artifacts) })
    } else if (agentType === 'finalize') {
      rows.push({ kind: 'finalize', task, ...finalizeSummary(task.artifacts) })
    }
  }
  return rows
}
