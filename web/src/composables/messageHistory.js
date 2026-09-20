// 会话视图与流式气泡的形状边界：建图挂起气泡是流水线边界的判定。
// 工具列表视图给数组、流式给 { items }，两种形状都要认。

export function isPlanResumeBoundary(message) {
  const tools = Array.isArray(message?.tools) ? message.tools : message.tools?.items || []
  return !!(message?.suspended && tools.some((item) => item.name === 'create_plan'))
}
