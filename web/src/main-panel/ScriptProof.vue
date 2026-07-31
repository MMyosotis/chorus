<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  markdown: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})

const html = computed(() => DOMPurify.sanitize(marked.parse(props.markdown || '')))
</script>

<template>
  <article class="script-proof" :class="{ compact }" v-html="html"></article>
</template>

<style scoped>
.script-proof { padding: 0; font-family: var(--ch-font-sans); color: var(--ch-text); }
.script-proof :deep(h1) { max-width: 680px; margin: 0 0 24px; font: 600 24px/1.3 var(--ch-font-sans); }
.script-proof :deep(h2) { max-width: 680px; margin: 24px 0 8px; font: 600 16px/1.5 var(--ch-font-sans); }
.script-proof :deep(p) { max-width: 680px; margin: 8px 0; color: var(--ch-text-secondary); font: 400 14px/1.6 var(--ch-font-sans); }
.script-proof :deep(ul) { max-width: 680px; margin: 16px 0; padding-left: 24px; }
.script-proof :deep(li) { margin: 8px 0; color: var(--ch-text-secondary); font: 400 14px/1.6 var(--ch-font-sans); }
.script-proof :deep(blockquote) { max-width: 680px; margin: 24px 0; padding: 16px 20px; border: 0; border-radius: var(--ch-radius-list); background: var(--ch-muted-gradient); color: var(--ch-text); font: 500 16px/1.5 var(--ch-font-sans); }
.script-proof :deep(blockquote p) { margin: 0; color: inherit; font: inherit; }
.script-proof :deep(hr) { max-width: 680px; margin: 24px 0; border: 0; border-top: 1px solid var(--ch-border); }
.script-proof :deep(strong) { color: var(--ch-text); font-weight: 600; }
.script-proof :deep(img) { max-width: 100%; border-radius: var(--ch-radius-list); }

.script-proof.compact :deep(h1) { margin-bottom: 16px; font-size: 20px; line-height: 1.3; }
.script-proof.compact :deep(h2) { margin: 16px 0 8px; line-height: 1.5; }
.script-proof.compact :deep(p),
.script-proof.compact :deep(li) { font-size: 14px; line-height: 1.6; }
.script-proof.compact :deep(blockquote) { margin: 16px 0; padding: 16px; font-size: 14px; line-height: 1.5; }
</style>
