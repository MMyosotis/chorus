const VIRTUAL_CARD_KINDS = new Set(['hil', 'confirmed', 'product', 'running', 'recovery'])

export function findLastConversationEntryIndex(entries) {
  let entryIndex = entries.length - 1
  while (entryIndex >= 0 && VIRTUAL_CARD_KINDS.has(entries[entryIndex].kind)) entryIndex -= 1
  return entryIndex
}
