export function resolveActivityState({ role, active, content, thinking, tools }) {
  if (role !== 'assistant' || !active) return 'idle'

  const toolItems = tools?.items || []
  const hasRunningTool = toolItems.some((item) => item.duration_ms == null)
  if (tools?.state === 'running' && hasRunningTool) return 'tools'
  if (thinking?.state === 'running') return 'thinking'
  return content ? 'idle' : 'preparing'
}
