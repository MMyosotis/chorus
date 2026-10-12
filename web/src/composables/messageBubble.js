export function shouldUseBareMode({ role, content, active, recaps, suspended }) {
  return role === 'assistant' && !content && (active || recaps.length > 0 || suspended)
}
