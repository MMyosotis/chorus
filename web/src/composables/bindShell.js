// mustache 风格槽位绑定：{{field}} 转义 / {{{field}}} 原始 HTML / {{#array}}…{{/array}} 循环（内用 {{.}} 或对象项 {{key}}）

function escapeHtml(text) {
  return String(text ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const LOOP_RE = /\{\{#(\w+)\}\}([\s\S]*?)\{\{\/\1\}\}/g
const RAW_RE = /\{\{\{(\w+)\}\}\}/g
const FIELD_RE = /\{\{(\w+)\}\}/g
const RAW_DOT_RE = /\{\{\{\.\}\}\}/g
const DOT_RE = /\{\{\.\}\}/g

function bindItem(inner, item) {
  if (item && typeof item === 'object') {
    return inner
      .replace(RAW_RE, (_, key) => (item[key] == null ? '' : String(item[key])))
      .replace(FIELD_RE, (_, key) => escapeHtml(item[key]))
  }
  return inner
    .replace(RAW_DOT_RE, () => (item == null ? '' : String(item)))
    .replace(DOT_RE, () => escapeHtml(item))
}

export function bindShell(templateHtml, slots = {}) {
  let out = templateHtml
  let prev
  do {
    prev = out
    out = out.replace(LOOP_RE, (_, name, inner) => {
      const val = slots[name]
      if (Array.isArray(val)) return val.map((item) => bindItem(inner, item)).join('')
      if (val) return bindItem(inner, val)
      return ''
    })
  } while (out !== prev)
  const raw = out.replace(RAW_RE, (_, name) => (slots[name] == null ? '' : String(slots[name])))
  return raw.replace(FIELD_RE, (_, name) => escapeHtml(slots[name]))
}
