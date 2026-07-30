<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { getSkillFile } from '../api.js'
import { renderPostCardHTML, renderInline } from '../composables/renderPostCard.js'
import { bindShell } from '../composables/bindShell.js'

const props = defineProps({
  card: { type: Object, required: true },
  previewRef: { type: String, default: '' },
  stylesheetRef: { type: String, default: '' },
})

const previewHost = ref(null)
const error = ref('')
let previewRoot = null

function resolveResource(ref, fallbackPath) {
  const [name, ...path] = String(ref || '').split('/')
  return name && path.length
    ? { name, path: path.join('/') }
    : { name: 'web-blog', path: fallbackPath }
}

// 极简 key: value 行解析，不引 yaml 库
function parseYaml(text) {
  const cfg = {}
  for (const line of String(text || '').split('\n')) {
    const m = line.match(/^\s*(\w+)\s*:\s*(.+?)\s*$/)
    if (m) cfg[m[1]] = m[2]
  }
  return cfg
}

function renderPreview(html, css, card, format) {
  const tags = card.tags || []
  const firstParagraph = (card.sections || []).find((section) => section.kind === 'paragraph' && section.text)?.text || ''
  const slots = {
    title: renderInline(card.title, format),
    cover_url: card.cover?.url || '',
    summary: renderInline(card.summary || firstParagraph, format),
    body: renderPostCardHTML(card, { format }),
    tags,
    has_tags: tags.length > 0,
  }
  const bound = bindShell(html, slots)
  if (!previewHost.value) return
  previewRoot ||= previewHost.value.attachShadow({ mode: 'open' })
  previewRoot.innerHTML = `<style>${css} :host { display: block; margin: 0; padding: 0; } .preview-document { display: block; width: 100%; margin: 0 !important; padding: 0 !important; }</style><div class="preview-document">${bound}</div>`
}

async function load() {
  error.value = ''
  const preview = resolveResource(props.previewRef, 'preview/desktop.html')
  const stylesheet = resolveResource(props.stylesheetRef, 'preview/desktop.css')
  try {
    const [html, css, yaml] = await Promise.all([
      getSkillFile(preview.name, preview.path),
      getSkillFile(stylesheet.name, stylesheet.path),
      getSkillFile(preview.name, 'platform.yaml'),
    ])
    const format = parseYaml(yaml).format || 'markdown'
    await nextTick()
    renderPreview(html, css, props.card, format)
  } catch (e) {
    error.value = `平台外壳加载失败：${e.message}`
  }
}

onMounted(() => {
  load()
})
watch(() => [props.previewRef, props.stylesheetRef, props.card], load)
</script>

<template>
  <div class="platform-shell">
    <div v-if="error" class="platform-error">{{ error }}</div>
    <div
      v-else
      ref="previewHost"
      class="platform-preview-host"
    ></div>
  </div>
</template>

<style scoped>
.platform-shell { width: 100%; }
.platform-preview-host { width: 100%; display: block; background: var(--ch-surface); }
.platform-error { padding: 24px; color: var(--ch-danger); font-size: 14px; text-align: center; border: 1px dashed var(--ch-border-strong); }
</style>
