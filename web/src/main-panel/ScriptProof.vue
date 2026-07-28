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
.script-proof { padding: 0; font-family: var(--ch-font-sans); }
.script-proof h3 { max-width: 680px; margin: 0 0 24px; color: var(--ch-text); font: 600 24px/1.3 var(--ch-font-sans); }
.script-proof h4 { margin: 24px 0 8px; color: var(--ch-text); font: 600 16px/1.5 var(--ch-font-sans); }
.script-proof p,
.script-proof li { color: var(--ch-text-secondary); font: 400 14px/1.6 var(--ch-font-sans); }
.script-proof p { max-width: 680px; margin: 8px 0; }
.script-proof :deep(strong) { color: var(--ch-text); font-weight: 600; }
.script-proof ul { max-width: 680px; margin: 16px 0; padding-left: 24px; }
.script-proof li { margin: 8px 0; padding-left: 0; }
.script-proof blockquote { max-width: 680px; margin: 24px 0; padding: 16px 20px; border: 0; border-radius: var(--ch-radius-list); background: var(--ch-muted-gradient); color: var(--ch-text); font: 500 16px/1.5 var(--ch-font-sans); text-align: left; }
.script-proof hr { max-width: 680px; margin: 24px 0; border: 0; border-top: 1px solid var(--ch-border); }
.script-tags { max-width: 680px; display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; color: var(--ch-text-secondary); font: 500 12px/1.5 var(--ch-font-sans); }
.script-tags span { white-space: nowrap; }

.script-proof.compact h3 { margin-bottom: 16px; font-size: 20px; line-height: 1.3; }
.script-proof.compact h4 { margin: 16px 0 8px; line-height: 1.5; }
.script-proof.compact p,
.script-proof.compact li { font-size: 14px; line-height: 1.6; }
.script-proof.compact blockquote { margin: 16px 0; padding: 16px; font-size: 14px; line-height: 1.5; }
.script-proof.compact .script-tags { font-size: 12px; }
</style>
