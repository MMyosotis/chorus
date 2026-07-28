const STYLE_TAG_SEPARATOR = /[,，、;；|｜/／\n\r。!?！？·•]+/u

export function splitStyleTags(value) {
  if (value === null || value === undefined) return []

  const source = Array.isArray(value) ? value : [value]
  const tags = source
    .flatMap((item) => String(item).split(STYLE_TAG_SEPARATOR))
    .map((item) => item.trim())
    .filter(Boolean)

  return [...new Set(tags)]
}
