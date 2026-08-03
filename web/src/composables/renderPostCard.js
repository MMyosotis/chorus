// PostCard 成品 markdown 渲染单一来源。
// 标题固定来自 front matter，正文按标准 markdown 渲染为 rc-* class HTML。
import { Marked } from 'marked'
import DOMPurify from 'dompurify'

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function renderImageFigure({ href, title, text }) {
  const alt = escapeHtml(text || '')
  const titleAttr = title ? ` title="${escapeHtml(title)}"` : ''
  return `<figure class="rc-image"><img src="${escapeHtml(href || '')}" alt="${alt}"${titleAttr} loading="lazy">${alt ? `<figcaption>${alt}</figcaption>` : ''}</figure>\n`
}

const markedInstance = new Marked()
markedInstance.use({
  renderer: {
    heading({ tokens, depth }) {
      const text = this.parser.parseInline(tokens)
      if (depth === 1) return ''
      return `<h${depth} class="rc-heading">${text}</h${depth}>\n`
    },
    paragraph({ tokens }) {
      // 纯图片段落不包 p，避免 figure 嵌套
      if (tokens.length === 1 && tokens[0].type === 'image') {
        return renderImageFigure(tokens[0])
      }
      return `<p class="rc-paragraph">${this.parser.parseInline(tokens)}</p>\n`
    },
    list(token) {
      const tag = token.ordered ? 'ol' : 'ul'
      const cls = token.ordered ? 'rc-list rc-list--ordered' : 'rc-list'
      const items = (token.items || [])
        .map((item) => `<li>${this.parser.parseInline(item.tokens[0]?.tokens || item.tokens)}</li>`)
        .join('')
      return `<${tag} class="${cls}">${items}</${tag}>\n`
    },
    blockquote({ tokens }) {
      return `<blockquote class="rc-quote">${this.parser.parse(tokens)}</blockquote>\n`
    },
    image({ href, title, text }) {
      return renderImageFigure({ href, title, text })
    },
    hr() {
      return '<hr class="rc-divider">'
    },
    code({ text }) {
      return `<pre class="rc-code"><code>${escapeHtml(text)}</code></pre>\n`
    },
  },
})

export function renderInline(text, format = 'markdown') {
  if (format === 'plain_text') return escapeHtml(text).replace(/\n/g, '<br>')
  return DOMPurify.sanitize(markedInstance.parseInline(text || ''))
}

export function stripFrontMatter(markdown) {
  const source = String(markdown || '')
  const lines = source.split('\n')
  if (lines[0].trim() !== '---') return { front: [], body: source }
  let end = -1
  for (let i = 1; i < lines.length; i += 1) {
    if (lines[i].trim() === '---') { end = i; break }
  }
  if (end === -1) return { front: [], body: source }
  return { front: lines.slice(1, end), body: lines.slice(end + 1).join('\n').replace(/^\n+/, '') }
}

function parseFrontMatterArray(lines) {
  const fm = {}
  for (const line of lines) {
    const idx = line.indexOf(':')
    if (idx <= 0) continue
    const key = line.slice(0, idx).trim()
    let value = line.slice(idx + 1).trim()
    // 标签数组形如 [话题1, 话题2]
    const arrMatch = value.match(/^\[(.*)\]$/)
    if (arrMatch) {
      value = arrMatch[1].split(',').map((item) => item.trim()).filter(Boolean)
    }
    fm[key] = value
  }
  return fm
}

export function parseFrontMatter(markdown) {
  const { front } = stripFrontMatter(markdown)
  return parseFrontMatterArray(front)
}

function stripLegacyFirstH1(markdown) {
  // 兼容历史卡片；新产物校验已禁止正文使用一级标题。
  const source = String(markdown || '')
  const lines = source.split('\n')
  let h1Line = -1
  for (let i = 0; i < lines.length; i += 1) {
    if (/^#\s+/.test(lines[i])) { h1Line = i; break }
  }
  if (h1Line === -1) return source
  // 去掉 H1 行及其后紧跟的空行
  let end = h1Line + 1
  while (end < lines.length && lines[end].trim() === '') end += 1
  return lines.slice(0, h1Line).concat(lines.slice(end)).join('\n').replace(/^\n+/, '')
}

export function imageUrls(card) {
  const markdown = card && typeof card.markdown === 'string' ? card.markdown : ''
  return markdown.split('\n').flatMap((line) => {
    const match = line.match(/!\[[^\]]*\]\((.*)\)/)
    return match?.[1]?.trim() ? [match[1].trim()] : []
  })
}

export function firstImageUrl(card) {
  return imageUrls(card)[0] || ''
}

export function plainTextPostContent(card) {
  const markdown = card && typeof card.markdown === 'string' ? card.markdown : ''
  const { body } = stripFrontMatter(markdown)
  return stripLegacyFirstH1(body)
    .replace(/<img\b[^>]*>/gi, '')
    .replace(/^\s*!\[[^\]]*\]\([^\n]*\)\s*$/gm, '')
    .replace(/!\[[^\]]*\]\([^)]+\)/g, '')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/^\s{0,3}#{1,6}\s+/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*(?:[-+*]|\d+\.)\s+/gm, '')
    .replace(/(\*\*|__|~~|`)/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
}

export function firstParagraphText(markdown) {
  const { body } = stripFrontMatter(markdown)
  const stripped = stripLegacyFirstH1(body)
  for (const block of markedInstance.Lexer.lex(stripped)) {
    if (block.type === 'paragraph' && block.tokens) {
      const text = block.tokens.map((token) => token.text || '').join('')
      return String(text).replace(/\n/g, ' ').trim()
    }
  }
  return ''
}

export function renderPostCardHTML(card, { format = 'markdown' } = {}) {
  const markdown = card && typeof card.markdown === 'string' ? card.markdown : ''
  if (format === 'plain_text') {
    const { body } = stripFrontMatter(markdown)
    return escapeHtml(stripLegacyFirstH1(body)).replace(/\n\n/g, '<br><br>').replace(/\n/g, '<br>')
  }
  const { body } = stripFrontMatter(markdown)
  const stripped = stripLegacyFirstH1(body)
  return DOMPurify.sanitize(markedInstance.parse(stripped))
}
