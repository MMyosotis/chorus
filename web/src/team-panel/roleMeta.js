// 角色元数据 + status→徽章映射（spec 3.2/6.7：加状态只改这一处）。

export const ROLE_LABELS = {
  idea: '选题官',
  script: '文案',
  image: '配图',
  finalize: '汇总',
}

export const ROLE_ORDER = ['idea', 'script', 'image', 'finalize']

// status → { label, cls }（cls 用于 CSS 徽章色）
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
