// 将虚拟卡片插在其触发的助手消息之后。

import { containsMessageId } from './messageHistory.js'

export function replaceAnchoredCards(list, shouldRemove, cards) {
  for (let index = list.length - 1; index >= 0; index--) {
    if (shouldRemove(list[index])) list.splice(index, 1)
  }
  for (const card of cards) insertAnchoredCard(list, card)
}

export function insertAnchoredCard(list, card) {
  const anchorIndex = list.findIndex((message) => containsMessageId(message, card.anchorMessageId))
  if (anchorIndex < 0) return
  let insertIndex = anchorIndex + 1
  while (list[insertIndex]?.anchorMessageId === card.anchorMessageId) insertIndex++
  list.splice(insertIndex, 0, card)
}
