// 任务图快照到对话区虚拟卡的投影规则。纯函数无依赖，
// 运行卡原址刷新由调用方按种类区分处理。

export function planTaskCards(graph) {
  const tasks = (graph && graph.tasks) || []
  const plan = []
  for (const task of tasks) {
    if (task.status === 'finished' && task.agent_type !== 'finalize') {
      plan.push({ kind: 'confirmed', task, id: 'confirmed:' + task.id, role: 'assistant', anchorMessageId: task.message_id })
    }
  }
  const runningTask = tasks.find((task) => task.status === 'running')
  if (runningTask) {
    plan.push({ kind: 'running', task: runningTask, id: 'running:' + runningTask.id, role: 'assistant', anchorMessageId: runningTask.message_id })
  }
  for (const task of tasks) {
    if (task.status === 'awaiting_confirm') {
      plan.push({ kind: 'hil', task, id: 'hil:' + task.id, role: 'assistant', anchorMessageId: task.message_id })
    } else if (task.status === 'failed') {
      plan.push({ kind: 'recovery', task, id: 'recovery:' + task.id, role: 'assistant', anchorMessageId: task.message_id })
    } else if (task.agent_type === 'finalize' && task.status === 'finished') {
      plan.push({ kind: 'postcard', task, id: 'postcard:' + task.id, role: 'assistant', anchorMessageId: task.message_id })
    }
  }
  return plan
}

export function planIntentCard(confirmation) {
  if (!confirmation) return null
  return {
    kind: 'intent-confirm',
    state: confirmation,
    id: `intent-confirm:${confirmation.confirmation_id || (confirmation.status === 'answered' ? 'answered' : 'open')}`,
    role: 'assistant',
    anchorMessageId: confirmation.message_id,
  }
}

export function planIntentCards(confirmations) {
  return (confirmations || []).map(planIntentCard).filter(Boolean)
}

export function planOptionCard(prompt) {
  if (!prompt) return null
  return {
    kind: 'option',
    prompt,
    id: `option:${prompt.prompt_id || (prompt.status === 'answered' ? 'answered' : 'open')}`,
    role: 'assistant',
    anchorMessageId: prompt.message_id,
  }
}

export function planOptionCards(prompts) {
  return (prompts || []).map(planOptionCard).filter(Boolean)
}
