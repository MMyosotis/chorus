// PostCard 内容树 -> body HTML 片段：sections 渲染单一来源，供平台外壳槽位与直接渲染组件共用
import { marked } from 'marked'
import DOMPurify from 'dompurify'

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function renderInline(text, format = 'markdown') {
  if (format === 'plain_text') return escapeHtml(text).replace(/\n/g, '<br>')
  return DOMPurify.sanitize(marked.parseInline(text || ''))
}

function listItems(section) {
  return String(section.text || '').split('\n').map((item) => item.trim()).filter(Boolean)
}

function renderSection(section, format) {
  if (section.kind === 'heading') return `<h3 class="pc-heading">${renderInline(section.text, format)}</h3>`
  if (section.kind === 'paragraph') return `<p class="pc-paragraph">${renderInline(section.text, format)}</p>`
  if (section.kind === 'list') {
    const items = listItems(section).map((item) => `<li>${renderInline(item, format)}</li>`).join('')
    return `<ul class="pc-list">${items}</ul>`
  }
  if (section.kind === 'table' && section.table) {
    const head = section.table.headers.map((cell) => `<th>${renderInline(cell, format)}</th>`).join('')
    const body = section.table.rows
      .map((row) => `<tr>${row.map((cell) => `<td>${renderInline(cell, format)}</td>`).join('')}</tr>`)
      .join('')
    return `<div class="pc-table-wrap"><table class="pc-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`
  }
  if (section.kind === 'quote') return `<blockquote class="pc-quote">${renderInline(section.text, format)}</blockquote>`
  if (section.kind === 'divider') return `<hr class="pc-divider">`
  if (section.kind === 'image' && section.image && section.image.url) {
    const caption = section.image.caption
      ? `<figcaption>${escapeHtml(section.image.caption)}</figcaption>` : ''
    return `<figure class="pc-image"><img src="${escapeHtml(section.image.url)}" alt="${escapeHtml(section.image.caption || '')}" loading="lazy">${caption}</figure>`
  }
  return ''
}

export function renderPostCardHTML(card, { format = 'markdown' } = {}) {
  return (card.sections || []).map((section) => renderSection(section, format)).join('')
}
