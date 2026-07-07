// 角色元数据与状态徽章映射，新增状态仅改此处。

export const ROLE_LABELS = {
  idea: '选题官',
  script: '文案',
  image: '配图',
  finalize: '汇总',
}

export const ROLE_ORDER = ['idea', 'script', 'image', 'finalize']

export const ROLE_TAG = {
  idea: '选题洞察',
  script: '文案撰写',
  image: '配图生成',
  finalize: '成品整合',
}

export function stepOf(agentType) {
  return ROLE_ORDER.indexOf(agentType) + 1
}

export const STATUS_BADGE = {
  pending: { label: '待命', cls: 'idle' },
  running: { label: '工作中', cls: 'running' },
  awaiting_confirm: { label: '等你确认', cls: 'waiting' },
  finished: { label: '已完成', cls: 'done' },
  failed: { label: '失败', cls: 'failed' },
  cancelled: { label: '已取消', cls: 'cancelled' },
}

export function badgeOf(status) {
  return STATUS_BADGE[status] || { label: status, cls: 'idle' }
}
