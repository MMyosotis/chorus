<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  blocks: { type: Array, default: () => [] },
  compact: { type: Boolean, default: false },
})

function stripOuterBold(text) {
  const match = text.match(/^\*\*([\s\S]+)\*\*$/)
  return match ? match[1].trim() : text
}

function looksLikeTitle(text) {
  return text.length > 0 && text.length <= 48 && !/[\u3002！？!?;；:：]$/.test(text)
}

function splitLeadingTitle(text) {
  const space = text.indexOf(' ')
  if (space <= 0) return null
  const title = text.slice(0, space).trim()
  const rest = text.slice(space + 1).trim()
  return rest && looksLikeTitle(title) ? { title, rest } : null
}

function tagItems(text) {
  return stripOuterBold(text).match(/#[^\s#]+/g) || []
}

const normalizedBlocks = computed(() => {
  const result = []
  for (const [index, source] of (props.blocks || []).entries()) {
    const raw = String(source?.text || '').trim()
    if (!raw) continue

    if (/^(---|\*\*\*|___)$/.test(raw)) {
      result.push({ kind: 'divider', text: '' })
      continue
    }

    const tags = tagItems(raw)
    if (stripOuterBold(raw).startsWith('#') && tags.length) {
      result.push({ kind: 'tags', text: stripOuterBold(raw), items: tags })
      continue
    }

    if (source.kind === 'title') {
      result.push({ kind: 'title', text: stripOuterBold(raw) })
      continue
    }

    if (index === 0 && source.kind === 'paragraph') {
      const split = splitLeadingTitle(raw)
      if (split) {
        result.push({ kind: 'title', text: stripOuterBold(split.title) })
        result.push({ kind: 'paragraph', text: split.rest })
        continue
      }
      if (looksLikeTitle(stripOuterBold(raw))) {
        result.push({ kind: 'title', text: stripOuterBold(raw) })
        continue
      }
    }

    if (index === 0 && source.kind === 'heading') {
      result.push({ kind: 'title', text: stripOuterBold(raw) })
      continue
    }

    if (/^\*\*[\s\S]+\*\*$/.test(raw)) {
      result.push({ kind: 'heading', text: stripOuterBold(raw) })
      continue
    }

    if (source.kind === 'list') {
      result.push({ kind: 'list', text: raw, items: raw.split('\n').map((item) => item.trim()).filter(Boolean) })
      continue
    }

    result.push({ kind: source.kind || 'paragraph', text: raw })
  }
  return result
})

function renderInline(text) {
  return DOMPurify.sanitize(marked.parseInline(text || ''))
}
</script>

<template>
  <article class="script-proof" :class="{ compact }">
    <template v-for="(block, index) in normalizedBlocks" :key="`${index}:${block.kind}`">
      <h3 v-if="block.kind === 'title'" v-html="renderInline(block.text)"></h3>
      <h4 v-else-if="block.kind === 'heading'" v-html="renderInline(block.text)"></h4>
      <blockquote v-else-if="block.kind === 'quote'" v-html="renderInline(block.text)"></blockquote>
      <ul v-else-if="block.kind === 'list'">
        <li v-for="(item, itemIndex) in block.items" :key="itemIndex" v-html="renderInline(item)"></li>
      </ul>
      <hr v-else-if="block.kind === 'divider'">
      <div v-else-if="block.kind === 'tags'" class="script-tags">
        <span v-for="tag in block.items" :key="tag">{{ tag }}</span>
      </div>
      <p v-else v-html="renderInline(block.text)"></p>
    </template>
  </article>
</template>

<style scoped>
.script-proof { padding: 0 4px; }
.script-proof h3 { max-width: 680px; margin: 6px 0 22px; color: var(--ch-text); font: 700 28px/1.35 var(--ch-serif); letter-spacing: .01em; }
.script-proof h4 { margin: 22px 0 7px; color: var(--ch-text); font: 600 15px/1.55 var(--ch-serif); }
.script-proof p,
.script-proof li { color: var(--ch-body); font: 500 14px/1.95 var(--ch-serif); letter-spacing: .005em; }
.script-proof p { max-width: 680px; margin: 7px 0; }
.script-proof p:first-of-type::first-letter { float: left; margin: 6px 8px 0 0; color: var(--ch-warm); font: 700 42px/.86 var(--ch-serif); }
.script-proof :deep(strong) { color: var(--ch-text); font-weight: 600; }
.script-proof ul { max-width: 680px; margin: 10px 0 14px; padding-left: 22px; }
.script-proof li { margin: 3px 0; padding-left: 2px; }
.script-proof blockquote { max-width: 680px; margin: 20px 0; padding: 14px 18px; border: 0; border-top: 1px solid var(--ch-border-2); border-bottom: 1px solid var(--ch-border-2); color: var(--ch-text); font: 600 16px/1.75 var(--ch-serif); text-align: center; }
.script-proof hr { max-width: 680px; margin: 22px 0 18px; border: 0; border-top: 1px dashed var(--ch-border-2); }
.script-tags { max-width: 680px; display: flex; flex-wrap: wrap; gap: 6px 14px; margin-top: 16px; color: var(--ch-warm); font: 500 12px/1.7 var(--ch-serif); }
.script-tags span { white-space: nowrap; }

.script-proof.compact h3 { margin-bottom: 18px; font-size: 24px; line-height: 1.4; }
.script-proof.compact h4 { margin: 18px 0 6px; line-height: 1.5; }
.script-proof.compact p,
.script-proof.compact li { font-size: 13px; line-height: 1.85; }
.script-proof.compact blockquote { margin: 16px 0; padding: 10px 14px; font-size: 14px; line-height: 1.7; }
.script-proof.compact .script-tags { font-size: 11px; }
</style>
