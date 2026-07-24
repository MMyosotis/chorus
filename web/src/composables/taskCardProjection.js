// 任务图快照到对话区虚拟卡的投影规则。纯函数无依赖，
// 运行卡原址刷新由调用方按种类区分处理。

export function planTaskCards(graph) {
  const tasks = (graph && graph.tasks) || []
  const plan = []
  for (const task of tasks) {
    if (task.status === 'finished' && task.agent_type !== 'finalize') {
      plan.push({ kind: 'confirmed', task, id: 'confirmed:' + task.id, role: 'assistant' })
    }
  }
  const runningTask = tasks.find((task) => task.status === 'running')
  if (runningTask) {
    plan.push({ kind: 'running', task: runningTask, id: 'running:' + runningTask.id, role: 'assistant' })
  }
  for (const task of tasks) {
    if (task.status === 'awaiting_confirm') {
      plan.push({ kind: 'hil', task, id: 'hil:' + task.id, role: 'assistant' })
    } else if (task.status === 'failed') {
      plan.push({ kind: 'recovery', task, id: 'recovery:' + task.id, role: 'assistant' })
    } else if (task.agent_type === 'finalize' && task.status === 'finished') {
      plan.push({ kind: 'postcard', task, id: 'postcard:' + task.id, role: 'assistant' })
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
