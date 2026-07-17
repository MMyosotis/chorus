// 任务图快照到对话区虚拟卡的投影规则。纯函数无依赖，
// 运行卡原址刷新由调用方按种类区分处理。

export function planTaskCards(graph) {
  const tasks = (graph && graph.tasks) || []
  const plan = []
  const confirmedProofs = tasks.filter((t) => t.status === 'finished' && t.agent_type !== 'finalize')
  if (confirmedProofs.length) {
    plan.push({
      kind: 'proof-register',
      tasks: confirmedProofs,
      id: `proof-register:${confirmedProofs.map((t) => t.id).join(':')}`,
      role: 'assistant',
    })
  }
  const runningTask = tasks.find((t) => t.status === 'running')
  if (runningTask) {
    plan.push({ kind: 'running', task: runningTask, id: 'running:' + runningTask.id, role: 'assistant' })
  }
  for (const t of tasks) {
    if (t.status === 'awaiting_confirm') {
      plan.push({ kind: 'hil', task: t, id: 'hil:' + t.id, role: 'assistant' })
    } else if (t.status === 'failed') {
      plan.push({ kind: 'recovery', task: t, id: 'recovery:' + t.id, role: 'assistant' })
    } else if (t.agent_type === 'finalize' && t.status === 'finished') {
      plan.push({ kind: 'postcard', task: t, id: 'postcard:' + t.id, role: 'assistant' })
    }
  }
  return plan
}

export function planIntentCard(state) {
  if (state && state.intent_status === 'ready_to_confirm') {
    return { kind: 'intent-confirm', state, id: 'intent-confirm', role: 'assistant' }
  }
  return null
}
